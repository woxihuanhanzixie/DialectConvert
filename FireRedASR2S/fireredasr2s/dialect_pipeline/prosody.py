from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from typing import Any

from .config import Step2Config
from .pronunciation import apply_pronunciation_rules


def build_prosody_text(
    semantic_text: str,
    pronunciation_text: str,
    cfg: Step2Config,
    *,
    target_dialect: str = "yue",
    dialect_style: str = "guangdong_general",
) -> dict[str, Any]:
    rule_text, rule_hits = apply_prosody_rules(pronunciation_text, target_dialect=target_dialect)
    llm_text, llm_used, notes = llm_prosody_rewrite(
        semantic_text,
        rule_text,
        cfg,
        target_dialect=target_dialect,
        dialect_style=dialect_style,
    )
    protected_text, pronunciation_hits = apply_pronunciation_rules(
        llm_text or rule_text,
        target_dialect=target_dialect,
        dialect_style=dialect_style,
    )
    return {
        "prosody_text": protected_text,
        "prosody_mode": "rule_plus_llm",
        "prosody_rule_hits": rule_hits + [
            {
                "pattern": item["source"],
                "count": item["count"],
                "category": item.get("category", "generic"),
                "notes": f"保护发音词面:{item['pronunciation_form']}",
            }
            for item in pronunciation_hits
        ],
        "prosody_hit_categories": _collect_hit_categories(rule_hits, pronunciation_hits),
        "prosody_fallback_used": llm_used,
        "prosody_notes": notes,
    }


def apply_prosody_rules(text: str, *, target_dialect: str) -> tuple[str, list[dict[str, Any]]]:
    value = text.strip()
    hits: list[dict[str, Any]] = []
    if not value:
        return value, hits
    replacements = _prosody_replacements(target_dialect)
    if not replacements:
        return value, hits
    new_value = value
    for pattern, repl, note in replacements:
        updated, count = re.subn(pattern, repl, new_value)
        if count > 0:
            new_value = updated
            hits.append({"pattern": pattern, "count": count, "category": "connector", "notes": note})
    return new_value, hits


def _prosody_replacements(target_dialect: str) -> list[tuple[str, str, str]]:
    if target_dialect == "yue":
        return [
            (r"如果(.+?)，就会", r"如果\1，咁就会", "如果...就会 -> 如果...咁就会"),
            (r"如果(.+?)，就", r"如果\1，咁就", "如果...就 -> 如果...咁就"),
            (r"搞到(.+?)，好难", r"搞到\1，之后就好难", "因果断点补连接"),
            (r"然后", "跟住", "连接词更口语"),
            (r"所以", "所以话", "连接词更顺口"),
        ]
    if target_dialect == "sichuan":
        return [
            (r"如果(.+?)，就会", r"要是\1，就会", "如果...就会 -> 要是...就会"),
            (r"如果(.+?)，就", r"要是\1，就", "如果...就 -> 要是...就"),
            (r"然后(?!嘛)", "然后嘛", "连接词更口语"),
            (r"所以", "所以说嘛", "连接词更顺口"),
        ]
    if target_dialect == "minnan":
        return [
            (r"如果(.+?)，就会", r"若是\1，就会", "如果...就会 -> 若是...就会"),
            (r"如果(.+?)，就", r"若是\1，就", "如果...就 -> 若是...就"),
            (r"然后(?!阁)", "然后阁", "连接词更口语"),
            (r"所以", "所以讲", "连接词更顺口"),
        ]
    return []


def llm_prosody_rewrite(
    semantic_text: str,
    prosody_seed_text: str,
    cfg: Step2Config,
    *,
    target_dialect: str,
    dialect_style: str,
) -> tuple[str, bool, str]:
    payload = {
        "model": _model(cfg),
        "messages": [
            {
                "role": "system",
                "content": _prosody_system_prompt(target_dialect, dialect_style),
            },
            {
                "role": "user",
                "content": (
                    "语义文本：\n"
                    f"{semantic_text}\n\n"
                    "当前发音文本：\n"
                    f"{prosody_seed_text}\n\n"
                    "请输出更适合直接 TTS 播报的版本。"
                ),
            },
        ],
        "stream": False,
        "temperature": 0.2,
    }
    try:
        t0 = time.perf_counter()
        result = _post_chat(payload, cfg)
        content = result["choices"][0]["message"]["content"].strip()
        content = _clean_tts_text(content)
        return content or prosody_seed_text, True, f"llm_prosody:{round((time.perf_counter() - t0) * 1000, 2)}ms"
    except Exception as exc:  # noqa: BLE001
        return prosody_seed_text, False, f"rule_only:{exc}"


def _prosody_system_prompt(target_dialect: str, dialect_style: str) -> str:
    if target_dialect == "yue":
        style = "广东通用粤语" if dialect_style == "guangdong_general" else "粤语"
        return (
            "你是方言 TTS 韵律润色助手。任务不是改原意，而是把文本润成更适合语音合成直接朗读的版本。"
            f"目标风格是{style}。"
            "请重点处理句子之间的衔接、连接词、轻停顿和口语连贯性，让断点不要太生硬。"
            "要求："
            "1) 保持原意，不加入新事实；"
            "2) 可以微调连接词，例如“咁就、之后、跟住”等，让过渡更顺；"
            "3) 允许调整断句，把太硬的停顿改成更自然的口语节奏；"
            "4) 不要过度堆砌语气词；"
                    "5) 对专名和已经修好的发音词面要保留，例如美斯、居里、一样，不要改回普通话写法；"
                    "6) 只输出最终可直接给 TTS 的文本。"
        )
    if target_dialect == "sichuan":
        return (
            "你是方言 TTS 韵律润色助手。任务不是改原意，而是把文本润成更适合四川话语音合成直接朗读的版本。"
            "请重点处理句子之间的衔接、连接词、轻停顿和口语连贯性，让断点不要太生硬。"
            "要求：保持原意，不加入新事实；可以微调连接词，例如“要是、然后嘛、所以说嘛、哈”等；"
            "不要过度堆砌语气词；只输出最终可直接给 TTS 的文本。"
        )
    if target_dialect == "minnan":
        return (
            "你是方言 TTS 韵律润色助手。任务不是改原意，而是把文本润成更适合闽南语语音合成直接朗读的版本。"
            "请重点处理句子之间的衔接、连接词、轻停顿和口语连贯性，让断点不要太生硬。"
            "要求：保持原意，不加入新事实；可以微调连接词，例如“若是、然后阁、所以讲、啦”等；"
            "不要过度堆砌语气词；只输出最终可直接给 TTS 的文本。"
        )
    return (
        "你是方言 TTS 韵律润色助手。请把文本改成更适合直接语音合成朗读的版本，"
        "允许微调连接词和停顿，但不要改变原意。只输出最终文本。"
    )


def _post_chat(payload: dict[str, Any], cfg: Step2Config) -> dict[str, Any]:
    base, key = _base_and_key(cfg)
    if not key:
        raise ValueError("Missing API key for prosody provider.")
    req = urllib.request.Request(
        url=f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
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


def _clean_tts_text(text: str) -> str:
    value = text.strip().replace("\n", "")
    value = re.sub(r"^最终文本[:：]", "", value).strip()
    return value


def _collect_hit_categories(rule_hits: list[dict[str, Any]], pronunciation_hits: list[dict[str, Any]]) -> list[str]:
    categories = {str(item.get("category") or "generic") for item in rule_hits if item.get("count", 0)}
    categories.update(str(item.get("category") or "generic") for item in pronunciation_hits if item.get("count", 0))
    return sorted(categories)
