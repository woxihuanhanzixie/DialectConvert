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
            {"role": "system", "content": _rewrite_system_prompt(target_dialect, dialect_style)},
            {"role": "user", "content": _rewrite_user_prompt(text, target_dialect=target_dialect, dialect_style=dialect_style)},
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
    req = urllib.request.Request(
        url=f"{base}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=cfg.timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))
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
        style = {
            "hongkong_colloquial": "偏香港日常口语，但不要过度俚语化。",
            "formal_safe": "保留粤语感，同时通用易懂，减少太跳脱的口头词。",
            "guangdong_general": "以广东通用粤语为主，自然、顺口、易懂，不要写得过于香港本地化。",
        }.get(dialect_style, "自然、通用、适合配音的粤语文本。")
        examples = (
            "普通话：这段时间 AI 的进步非常迅速，给开发者带来了更多可能。\n"
            "粤语：呢排 AI 进步真系好快，俾开发者带嚟多咗好多可能。\n"
            "普通话：如果牙齿被虫蛀掉了，就会造成不可逆的损伤。\n"
            "粤语：如果啲牙畀蛀牙蛀坏咗，伤到牙根，就会好难补救。"
        )
        name = "粤语"
    elif target_dialect == "sichuan":
        style = "以四川成都及川渝通用口语为基础，亲切、活泼、容易听懂。"
        examples = (
            "普通话：这段时间 AI 的进步非常迅速，给开发者带来了更多可能。\n"
            "四川话：这阵子 AI 进步硬是快得很，给开发者带来了更多可能噻。\n"
            "普通话：如果牙齿被虫蛀掉了，就会造成不可逆的损伤。\n"
            "四川话：要是牙齿遭虫蛀坏了，整到伤了根，就不太好补救了哈。"
        )
        name = "四川话"
    elif target_dialect == "minnan":
        style = "以通俗易懂的闽南语口语表达为主，可夹用常见汉字写法，优先服务 TTS 可读性。"
        examples = (
            "普通话：这段时间 AI 的进步非常迅速，给开发者带来了更多可能。\n"
            "闽南语：这阵仔 AI 进步真正足紧，予开发者带来阁较济可能喔。\n"
            "普通话：如果牙齿被虫蛀掉了，就会造成不可逆的损伤。\n"
            "闽南语：若是齿予虫蛀坏去，伤着齿根，就袂好补救喔。"
        )
        name = "闽南语"
    else:
        style = f"自然、顺口、适合直接配音的{dialect_label(target_dialect, dialect_style)}文本。"
        examples = ""
        name = dialect_label(target_dialect, dialect_style)

    return (
        f"你是专业方言改写助手。你的任务是把普通话改写成{name}发声文本，用于后续 TTS 直接朗读。\n"
        "必须遵守：\n"
        "1. 保留原意和事实，不补充新信息。\n"
        "2. 可以调整句式、拆句、合句，让它更像自然口语。\n"
        "3. 避免逐字直译，避免普通话书面腔。\n"
        "4. 输出必须适合直接 TTS 播报，节奏自然，不堆砌语气词。\n"
        "5. 只输出最终改写文本，不要解释，不要加标题，不要说“请提供文本”。\n"
        f"风格目标：{style}\n"
        f"参考例子：\n{examples}"
    )


def _rewrite_user_prompt(text: str, *, target_dialect: str, dialect_style: str) -> str:
    label = dialect_label(target_dialect, dialect_style)
    return (
        f"请把下面这段普通话文本改写成自然、流畅、适合直接配音的{label}发声文本。\n"
        "只输出改写后的文本，不要解释。\n\n"
        f"原文：{text}"
    )
