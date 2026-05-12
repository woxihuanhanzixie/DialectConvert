from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from .config import Step2Config
from .dialect_postprocess import postprocess_dialect_text
from .dialects import dialect_label, normalize_dialect_style


def rewrite_to_dialect(
    text: str,
    cfg: Step2Config,
    *,
    target_dialect: str = "yue",
    dialect_style: str = "guangdong_general",
) -> dict[str, Any]:
    dialect_style = normalize_dialect_style(target_dialect, dialect_style)
    payload = {
        "model": _model(cfg),
        "messages": [
            {
                "role": "system",
                "content": _rewrite_system_prompt(target_dialect, dialect_style),
            },
            {
                "role": "user",
                "content": _rewrite_user_prompt(text, target_dialect=target_dialect, dialect_style=dialect_style),
            },
        ],
        "stream": False,
    }

    t0 = time.perf_counter()
    err = ""
    for i in range(cfg.retry_count + 1):
        try:
            result = _post_chat(payload, cfg)
            content = result["choices"][0]["message"]["content"].strip()
            content = postprocess_dialect_text(content, target_dialect=target_dialect, dialect_style=dialect_style)
            return {
                "ok": True,
                "yue_text": content,
                "dialect_text": content,
                "degrade_mode": False,
                "llm_model": _model(cfg),
                "llm_latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                "llm_error": "",
                "target_dialect": target_dialect,
                "dialect_style": dialect_style,
            }
        except Exception as e:  # noqa: BLE001
            err = str(e)
            if i < cfg.retry_count:
                time.sleep(1 + i)

    fallback_text = postprocess_dialect_text(text, target_dialect=target_dialect, dialect_style=dialect_style)
    return {
        "ok": False,
        "yue_text": fallback_text,
        "dialect_text": fallback_text,
        "degrade_mode": True,
        "llm_model": _model(cfg),
        "llm_latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        "llm_error": err,
        "target_dialect": target_dialect,
        "dialect_style": dialect_style,
    }


def rewrite_to_cantonese(text: str, cfg: Step2Config) -> dict[str, Any]:
    return rewrite_to_dialect(text, cfg, target_dialect="yue", dialect_style=cfg.default_dialect_style)


def _post_chat(payload: dict[str, Any], cfg: Step2Config) -> dict[str, Any]:
    base, key = _base_and_key(cfg)
    if not key:
        raise ValueError("Missing API key for rewrite provider.")
    url = f"{base}/chat/completions"
    req = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=cfg.timeout_s) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {e.code}: {body}") from e


def _base_and_key(cfg: Step2Config) -> tuple[str, str]:
    if cfg.provider == "qwen":
        return cfg.qwen_base_url, cfg.qwen_api_key
    return cfg.deepseek_base_url, cfg.deepseek_api_key


def _model(cfg: Step2Config) -> str:
    if cfg.provider == "qwen":
        if not cfg.qwen_model:
            raise ValueError("QWEN_LLM_MODEL is required when provider=qwen.")
        return cfg.qwen_model
    return cfg.deepseek_model


def _rewrite_system_prompt(target_dialect: str, dialect_style: str) -> str:
    if target_dialect == "yue":
        return _yue_system_prompt(dialect_style)
    if target_dialect == "sichuan":
        return _sichuan_system_prompt(dialect_style)
    if target_dialect == "minnan":
        return _minnan_system_prompt(dialect_style)
    return (
        "你是方言改写助手。请把输入文本在不改变原意的前提下，重写成自然、顺口、适合直接配音的目标方言文本。"
        "允许顺句重写，但不要补充新信息。只输出最终文本。"
    )


def _rewrite_user_prompt(text: str, *, target_dialect: str, dialect_style: str) -> str:
    dialect_label = _dialect_label(target_dialect, dialect_style)
    return (
        f"请把下面这段文本重写成自然、流畅、适合直接配音的{dialect_label}。"
        "重点避免普通话直译感，宁可顺句重写，也不要生硬对词翻译。\n"
        f"{text}"
    )


def _dialect_label(target_dialect: str, dialect_style: str) -> str:
    return f"{dialect_label(target_dialect, dialect_style)}书写文本"


def _yue_system_prompt(dialect_style: str) -> str:
    style_line = {
        "hongkong_colloquial": "风格目标：偏香港日常口语，可保留少量自然口头词，但不要过度俚语化。",
        "formal_safe": "风格目标：保持粤语感，同时保证通用易懂，减少太跳脱的口头词。",
        "guangdong_general": "风格目标：以广东通用粤语为主，优先自然、顺口、易懂，不要写得过于香港本地化。",
    }.get(dialect_style, "风格目标：输出自然、通用、适合配音的粤语文本。")
    return (
        "你是方言改写助手。你的任务不是逐字翻译，而是把普通话重写成自然、顺口、适合直接配音的粤语书写文本。"
        f"{style_line}"
        "改写要求："
        "1) 保留原意，可以在不改变事实的前提下调整句式、拆句、合句；"
        "2) 优先使用常见粤语书写：嘅、咗、喺、冇、唔、佢、呢、嗰、啲、而家、真系、好、要；"
        "3) 避免普通话味太重或书面腔太重的直译，例如“非常、事情、出现、对于、造成、不可逆、服务、但是、并且”；"
        "4) 输出要适合直接 TTS 播报，节奏自然，但不要堆砌语气词；"
        "5) 当前只输出单一版本的最终文本，不要解释。"
        "参考风格："
        "普通话：这段时间 AI 的进步非常迅速，给开发者带来了更多可能。"
        "粤语：呢排 AI 进步真系好快，俾开发者带嚟多咗唔少可能性。"
        "普通话：如果牙齿被虫蛀掉了，就会造成不可逆的损伤。"
        "粤语：如果啲牙畀虫蛀坏咗，搞到伤到根，就会好难补救。"
    )


def _sichuan_system_prompt(dialect_style: str) -> str:
    _ = dialect_style
    return (
        "你是方言改写助手。你的任务不是逐字翻译，而是把普通话重写成自然、顺口、适合直接配音的四川话书写文本。"
        "风格目标：以四川成都及川渝通用口语为基础，表达亲切、活泼、容易听懂，适合基础演示。"
        "改写要求："
        "1) 保留原意，可以在不改变事实的前提下调整句式、拆句、合句；"
        "2) 优先使用常见四川话口语写法：啥子、咋个、啷个、莫、要得、巴适、安逸、晓得、整、搞快点、得不得；"
        "3) 适度使用句尾词，例如噻、嘛、哈、哟、撒，但不要堆砌；"
        "4) 避免普通话书面腔太重的直译，让文本读起来像自然口语；"
        "5) 输出要适合直接 TTS 播报，当前只输出单一版本的最终文本，不要解释。"
        "参考风格："
        "普通话：这段时间 AI 的进步非常迅速，给开发者带来了更多可能。"
        "四川话：这阵子 AI 进步硬是快得很，给开发者带来了更多可能噻。"
        "普通话：如果牙齿被虫蛀掉了，就会造成不可逆的损伤。"
        "四川话：要是牙齿遭虫蛀坏了，整到伤了根，就不好补救了哈。"
    )


def _minnan_system_prompt(dialect_style: str) -> str:
    _ = dialect_style
    return (
        "你是方言改写助手。你的任务不是逐字翻译，而是把普通话重写成自然、顺口、适合直接配音的闽南语书写文本。"
        "风格目标：以通俗易懂的闽南语口语表达为主，允许夹用常见汉字写法，优先服务基础演示和 TTS 可读性。"
        "改写要求："
        "1) 保留原意，可以在不改变事实的前提下调整句式、拆句、合句；"
        "2) 优先使用常见闽南语口语写法：阮、汝、伊、毋、袂、欲、足、真正、有影、按呢、啥物、敢会；"
        "3) 适度使用口语句尾，例如啦、咧、喔、咧讲，但不要堆砌；"
        "4) 避免普通话书面腔太重的直译，让文本读起来更像自然口语；"
        "5) 输出要适合直接 TTS 播报，当前只输出单一版本的最终文本，不要解释。"
        "参考风格："
        "普通话：这段时间 AI 的进步非常迅速，给开发者带来了更多可能。"
        "闽南语：这阵仔 AI 进步真正足紧，予开发者带来阁较济可能啦。"
        "普通话：如果牙齿被虫蛀掉了，就会造成不可逆的损伤。"
        "闽南语：若是齿予虫蛀坏去，伤着齿根，就袂好补救喔。"
    )
