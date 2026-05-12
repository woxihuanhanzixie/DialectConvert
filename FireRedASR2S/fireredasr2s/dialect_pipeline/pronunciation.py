from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from .config import Step2Config
from .pronunciation_lexicon import get_pronunciation_rules

_YUE_HIGH_RISK_TERMS = (
    "同样",
    "这样",
    "那个",
    "这个",
    "什么",
    "为什么",
    "不是",
    "没有",
    "然后",
)

_HIGH_RISK_TERMS_BY_DIALECT = {
    "yue": _YUE_HIGH_RISK_TERMS,
    "sichuan": ("什么", "为什么", "没有", "可以", "这样", "非常", "事情"),
    "minnan": ("什么", "为什么", "不是", "没有", "可以", "这样", "事情"),
}


def build_pronunciation_text(
    semantic_text: str,
    cfg: Step2Config,
    *,
    target_dialect: str = "yue",
    dialect_style: str = "guangdong_general",
) -> dict[str, Any]:
    pronunciation_text, rule_hits = apply_pronunciation_rules(
        semantic_text,
        target_dialect=target_dialect,
        dialect_style=dialect_style,
    )
    fallback_used = False
    notes = "rule_only"
    if cfg.pronunciation_rag_enabled:
        rag_notes = rag_pronunciation_lookup(semantic_text, target_dialect=target_dialect, dialect_style=dialect_style)
        if rag_notes:
            notes = f"{notes}|rag_reserved"
    if cfg.pronunciation_llm_fallback and _should_use_llm_fallback(semantic_text, pronunciation_text, target_dialect):
        llm_text, llm_notes = llm_pronunciation_fallback(
            pronunciation_text,
            cfg,
            target_dialect=target_dialect,
            dialect_style=dialect_style,
        )
        if llm_text:
            pronunciation_text = llm_text
            fallback_used = True
            notes = llm_notes
    return {
        "pronunciation_text": pronunciation_text,
        "pronunciation_mode": cfg.pronunciation_mode or "rule_first",
        "pronunciation_rule_hits": rule_hits,
        "pronunciation_hit_categories": _collect_hit_categories(rule_hits),
        "pronunciation_fallback_used": fallback_used,
        "pronunciation_notes": notes,
    }


def apply_pronunciation_rules(
    semantic_text: str,
    *,
    target_dialect: str,
    dialect_style: str,
) -> tuple[str, list[dict[str, Any]]]:
    text = semantic_text
    hits: list[dict[str, Any]] = []
    rules = sorted(
        get_pronunciation_rules(target_dialect, dialect_style),
        key=lambda item: (len(str(item["source"])), int(item.get("priority", 0))),
        reverse=True,
    )
    for rule in rules:
        source = str(rule["source"])
        target = str(rule["pronunciation_form"])
        if source and source in text:
            count = text.count(source)
            text = text.replace(source, target)
            hits.append(
                {
                    "source": source,
                    "pronunciation_form": target,
                    "count": count,
                    "category": rule.get("category", "generic"),
                    "notes": rule.get("notes", ""),
                }
            )
    return text, hits


def llm_pronunciation_fallback(
    pronunciation_text: str,
    cfg: Step2Config,
    *,
    target_dialect: str,
    dialect_style: str,
) -> tuple[str, str]:
    payload = {
        "model": _model(cfg),
        "messages": [
            {
                "role": "system",
                "content": _fallback_system_prompt(target_dialect, dialect_style),
            },
            {
                "role": "user",
                "content": (
                    "请把下面这段文本修成更适合 TTS/音色克隆发音的版本。"
                    "重点处理容易被读成普通话的词，允许替换成更常见的方言口语写法，但不要改原意。\n"
                    f"{pronunciation_text}"
                ),
            },
        ],
        "stream": False,
        "temperature": 0.1,
    }
    try:
        t0 = time.perf_counter()
        result = _post_chat(payload, cfg)
        content = result["choices"][0]["message"]["content"].strip()
        return content or pronunciation_text, f"llm_fallback:{round((time.perf_counter() - t0) * 1000, 2)}ms"
    except Exception as exc:  # noqa: BLE001
        return pronunciation_text, f"llm_fallback_failed:{exc}"


def rag_pronunciation_lookup(
    semantic_text: str,
    *,
    target_dialect: str,
    dialect_style: str,
) -> list[dict[str, Any]]:
    _ = (semantic_text, target_dialect, dialect_style)
    return []


def _should_use_llm_fallback(original_text: str, pronunciation_text: str, target_dialect: str) -> bool:
    high_risk_terms = _HIGH_RISK_TERMS_BY_DIALECT.get(target_dialect, ())
    if not high_risk_terms:
        return False
    if original_text == pronunciation_text:
        return any(token in original_text for token in high_risk_terms)
    return any(token in pronunciation_text for token in high_risk_terms)


def _collect_hit_categories(rule_hits: list[dict[str, Any]]) -> list[str]:
    categories = {str(item.get("category") or "generic") for item in rule_hits if item.get("count", 0)}
    return sorted(categories)


def _fallback_system_prompt(target_dialect: str, dialect_style: str) -> str:
    if target_dialect == "yue":
        style = "广东通用粤语" if dialect_style == "guangdong_general" else "粤语"
        return (
            "你是方言 TTS 发音修正助手。任务不是做语义改写，而是把文本修成更适合语音合成发音的版本。"
            f"目标方言是{style}。"
            "重点是把容易被读成普通话的词，替换成更稳定、更常见的方言口语写法。"
            "保持原意，不要扩写，不要解释，只输出最终文本。"
        )
    if target_dialect == "sichuan":
        return (
            "你是方言 TTS 发音修正助手。任务不是做语义改写，而是把文本修成更适合四川话语音合成发音的版本。"
            "重点把容易被读成普通话的词替换成更稳定、更常见的四川话口语写法。"
            "保持原意，不要扩写，不要解释，只输出最终文本。"
        )
    if target_dialect == "minnan":
        return (
            "你是方言 TTS 发音修正助手。任务不是做语义改写，而是把文本修成更适合闽南语语音合成发音的版本。"
            "重点把容易被读成普通话的词替换成更稳定、更常见的闽南语口语写法。"
            "保持原意，不要扩写，不要解释，只输出最终文本。"
        )
    return (
        "你是方言 TTS 发音修正助手。请把文本修成更适合目标方言 TTS 发音的版本，"
        "保持原意，不要解释，只输出最终文本。"
    )


def _post_chat(payload: dict[str, Any], cfg: Step2Config) -> dict[str, Any]:
    base, key = _base_and_key(cfg)
    if not key:
        raise ValueError("Missing API key for pronunciation provider.")
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
