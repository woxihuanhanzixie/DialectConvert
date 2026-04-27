from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from typing import Any

from fireredasr2s.dialect_pipeline.config import Step2Config
from fireredasr2s.dialect_pipeline.pronunciation import build_pronunciation_text
from fireredasr2s.dialect_pipeline.prosody import build_prosody_text
from fireredasr2s.dialect_pipeline.rewrite import rewrite_to_dialect
from fireredasr2s.dialect_pipeline.tn import prepare_reviewed_text_for_rewrite, split_sentences
from fireredasr2s.dialect_pipeline.tts import (
    synthesize_gold_teacher,
    synthesize_qwen_tts,
    synthesize_voice_clone,
    synthesize_voice_matched_from_teacher,
)


def review_asr_text(text: str, cfg: Step2Config, *, input_lang: str = "zh") -> dict[str, Any]:
    cleaned = _rule_clean(text)
    payload = {
        "model": _model(cfg),
        "messages": [
            {
                "role": "system",
                "content": _review_prompt(input_lang),
            },
            {
                "role": "user",
                "content": _review_user_prompt(cleaned, input_lang),
            },
        ],
        "stream": False,
        "temperature": 0.1,
    }

    t0 = time.perf_counter()
    err = ""
    reviewed_text = cleaned
    notes = "rule_clean_only"
    for i in range(cfg.retry_count + 1):
        try:
            result = _post_chat(payload, cfg)
            content = result["choices"][0]["message"]["content"].strip()
            reviewed_text, notes = _parse_review_payload(content, cleaned)
            return {
                "asr_raw_text": text,
                "asr_reviewed_text": reviewed_text,
                "asr_review_notes": notes,
                "review_degrade_mode": False,
                "review_model": _model(cfg),
                "review_latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                "input_lang": input_lang,
            }
        except Exception as e:  # noqa: BLE001
            err = str(e)
            if i < cfg.retry_count:
                time.sleep(1 + i)

    return {
        "asr_raw_text": text,
        "asr_reviewed_text": cleaned,
        "asr_review_notes": f"degrade_to_rule_clean: {err}",
        "review_degrade_mode": True,
        "review_model": _model(cfg),
        "review_latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        "input_lang": input_lang,
    }


def review_asr_text_en(text: str, cfg: Step2Config) -> dict[str, Any]:
    return review_asr_text(text, cfg, input_lang="en")


def translate_en_to_pivot_zh(text: str, cfg: Step2Config) -> dict[str, Any]:
    payload = {
        "model": _model(cfg),
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是英文语音转写后处理助手。请把英文文本准确转成自然、简洁的普通话中间文本。"
                    "要求：保留原意，不扩写，不总结，不加入解释；输出 JSON，字段必须是 pivot_text_zh 和 notes。"
                ),
            },
            {"role": "user", "content": f"请把这段英文文本翻译成普通话中间文本：\n{text}"},
        ],
        "stream": False,
        "temperature": 0.1,
    }
    t0 = time.perf_counter()
    err = ""
    for i in range(cfg.retry_count + 1):
        try:
            result = _post_chat(payload, cfg)
            content = result["choices"][0]["message"]["content"].strip()
            pivot_text, notes = _parse_pivot_payload(content, text)
            return {
                "pivot_text_zh": pivot_text,
                "translation_notes": notes,
                "translation_latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                "translation_model": _model(cfg),
                "translation_error": "",
            }
        except Exception as e:  # noqa: BLE001
            err = str(e)
            if i < cfg.retry_count:
                time.sleep(1 + i)
    return {
        "pivot_text_zh": text,
        "translation_notes": "degrade_to_original_en",
        "translation_latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        "translation_model": _model(cfg),
        "translation_error": err,
    }


def rewrite_text(
    text: str,
    cfg: Step2Config,
    segment_max_len: int = 28,
    *,
    input_lang: str = "zh",
    pivot_text_zh: str = "",
    target_dialect: str = "yue",
    dialect_style: str = "guangdong_general",
) -> dict[str, Any]:
    source_for_rewrite = pivot_text_zh or text
    rewrite_input_text = prepare_reviewed_text_for_rewrite(source_for_rewrite)
    segments = split_sentences(rewrite_input_text, max_len=segment_max_len) or [rewrite_input_text]
    texts: list[str] = []
    total_latency = 0.0
    degrade = False
    model = ""
    errors: list[str] = []
    for seg in segments:
        rw = rewrite_to_dialect(seg, cfg, target_dialect=target_dialect, dialect_style=dialect_style)
        texts.append(str(rw["dialect_text"]).rstrip("。"))
        total_latency += float(rw["llm_latency_ms"])
        degrade = degrade or bool(rw["degrade_mode"])
        model = str(rw["llm_model"])
        if rw["llm_error"]:
            errors.append(str(rw["llm_error"]))
    clean_texts = [t.strip("。！？!?,， ") for t in texts if t and t.strip("。！？!?,， ")]
    semantic_text = "，".join(clean_texts).strip()
    if semantic_text and not semantic_text.endswith("。"):
        semantic_text += "。"
    pronunciation = build_pronunciation_text(
        semantic_text,
        cfg,
        target_dialect=target_dialect,
        dialect_style=dialect_style,
    )
    prosody = build_prosody_text(
        semantic_text,
        pronunciation["pronunciation_text"],
        cfg,
        target_dialect=target_dialect,
        dialect_style=dialect_style,
    )
    return {
        "source_text": text,
        "tn_text": rewrite_input_text,
        "rewrite_segments": segments,
        "dialect_text": semantic_text,
        "semantic_text": semantic_text,
        "pronunciation_text": pronunciation["pronunciation_text"],
        "prosody_text": prosody["prosody_text"],
        "pronunciation_mode": pronunciation["pronunciation_mode"],
        "pronunciation_hit_categories": pronunciation["pronunciation_hit_categories"],
        "pronunciation_rule_hits": pronunciation["pronunciation_rule_hits"],
        "pronunciation_fallback_used": pronunciation["pronunciation_fallback_used"],
        "pronunciation_notes": pronunciation["pronunciation_notes"],
        "prosody_mode": prosody["prosody_mode"],
        "prosody_hit_categories": prosody["prosody_hit_categories"],
        "prosody_rule_hits": prosody["prosody_rule_hits"],
        "prosody_fallback_used": prosody["prosody_fallback_used"],
        "degrade_mode": degrade,
        "llm_model": model or "unknown",
        "llm_latency_ms": round(total_latency, 2),
        "llm_error": " | ".join(errors),
        "input_lang": input_lang,
        "pivot_text_zh": pivot_text_zh,
        "translation_notes": "",
        "target_dialect": target_dialect,
        "dialect_style": dialect_style,
    }


def tts_text(
    text: str,
    cfg: Step2Config,
    wav_path,
    *,
    voice_clone_enabled: bool = False,
    speaker_ref_audio: str = "",
    preferred_name: str = "demo1_voice",
) -> dict[str, Any]:
    t0 = time.perf_counter()
    if voice_clone_enabled and speaker_ref_audio:
        result = synthesize_voice_clone(
            text,
            wav_path,
            cfg,
            ref_audio_path=speaker_ref_audio,
            preferred_name=preferred_name,
        )
        result["voice_clone_enabled"] = True
        result["voice_clone_provider"] = cfg.voice_clone_provider
        result["clone_mode"] = "api_first"
        result["speaker_similarity_note"] = "参考音频已参与克隆，优先保留声纹相似度"
        result["fallback_reason"] = "" if not result.get("error") else "voice_clone_failed"
    else:
        result = synthesize_qwen_tts(text, wav_path, cfg)
        result["voice_clone_enabled"] = False
        result["voice_clone_provider"] = ""
        result["clone_mode"] = "standard_tts"
        result["speaker_similarity_note"] = "未使用参考音频，回退系统音色"
        result["fallback_reason"] = ""
    result["speaker_similarity_priority"] = cfg.speaker_similarity_priority
    result["tts_fluency_mode"] = cfg.tts_fluency_mode
    result["tts_style_instructions"] = cfg.tts_style_instructions
    result["instruction_mode_active"] = False
    result["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    return result


def tts_gold_teacher(text: str, cfg: Step2Config, wav_path) -> dict[str, Any]:
    t0 = time.perf_counter()
    result = synthesize_gold_teacher(text, wav_path, cfg)
    result["voice_clone_enabled"] = False
    result["voice_clone_provider"] = ""
    result["clone_mode"] = "gold_teacher"
    result["speaker_similarity_note"] = "系统粤语 TTS 作为发音和流畅度金标准"
    result["fallback_reason"] = ""
    result["speaker_similarity_priority"] = cfg.speaker_similarity_priority
    result["tts_fluency_mode"] = cfg.tts_fluency_mode
    result["tts_style_instructions"] = cfg.tts_style_instructions
    result["instruction_mode_active"] = False
    result["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    return result


def tts_voice_match_from_teacher(
    teacher_wav_path,
    cfg: Step2Config,
    wav_path,
    *,
    speaker_ref_audio: str,
    preferred_name: str = "demo1_voice",
) -> dict[str, Any]:
    t0 = time.perf_counter()
    result = synthesize_voice_matched_from_teacher(
        teacher_wav_path,
        speaker_ref_audio,
        wav_path,
        cfg,
        preferred_name=preferred_name,
    )
    result["voice_clone_enabled"] = True
    result["voice_clone_provider"] = cfg.voice_conversion_provider
    result["clone_mode"] = "teacher_audio_to_audio"
    result["speaker_similarity_note"] = "尝试保留 gold teacher 发音，只迁移参考说话人音色"
    result["speaker_similarity_priority"] = cfg.speaker_similarity_priority
    result["tts_fluency_mode"] = cfg.tts_fluency_mode
    result["tts_style_instructions"] = cfg.tts_style_instructions
    result["instruction_mode_active"] = False
    result["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    return result


def _rule_clean(text: str) -> str:
    x = text.strip()
    x = re.sub(r"[，,]{2,}", "，", x)
    x = re.sub(r"[。\.]{2,}", "。", x)
    x = re.sub(r"\s+", "", x)
    x = x.replace("，，", "，").replace("。。", "。")
    return x


def _parse_review_payload(content: str, fallback: str) -> tuple[str, str]:
    try:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(content[start : end + 1])
            reviewed = str(data.get("reviewed_text") or fallback).strip()
            notes = str(data.get("notes") or "")
            return reviewed or fallback, notes
    except Exception:
        pass
    plain = content.strip().replace("以下是修正结果：", "").strip()
    return plain or fallback, "plain_text_fallback"


def _parse_pivot_payload(content: str, fallback: str) -> tuple[str, str]:
    try:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(content[start : end + 1])
            pivot = str(data.get("pivot_text_zh") or fallback).strip()
            notes = str(data.get("notes") or "")
            return pivot or fallback, notes
    except Exception:
        pass
    return content.strip() or fallback, "plain_text_fallback"


def _post_chat(payload: dict[str, Any], cfg: Step2Config) -> dict[str, Any]:
    base, key = _base_and_key(cfg)
    if not key:
        raise ValueError("Missing API key for review provider.")
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


def _review_prompt(input_lang: str) -> str:
    if input_lang == "en":
        return (
            "You are an ASR transcript review assistant. Fix obvious recognition errors, punctuation, "
            "word breaks, and clearly wrong homophone-like mistakes without changing meaning. "
            "Keep natural filler words if they help preserve spoken rhythm. "
            "Do not summarize or rewrite style. Output JSON with reviewed_text and notes."
        )
    return (
        "你是 ASR 文本审查助手。任务是在不改变原意的前提下，"
        "优先修正明显的识别错误、同音字错误、错别字、断句问题和重复标点，"
        "让文本更适合后续方言改写与语音合成。"
        "要求："
        "1) 保持原意，不扩写，不缩写，不总结；"
        "2) 可以按语义调整断句和标点，让口语更自然；"
        "3) 对明显错误的同音字/近音字进行修正，比如“话/画”“在/再”；"
        "4) 像“嗯、呃、啊、这个、那个”等口语停顿词，如果符合真实口语节奏，可以保留，不要机械删除；"
        "5) 若某处无法确认，就保留原文，不要瞎猜；"
        "6) 输出 JSON，字段必须是 reviewed_text 和 notes。"
    )


def _review_user_prompt(cleaned: str, input_lang: str) -> str:
    if input_lang == "en":
        return (
            "Please review this ASR transcript. Fix obvious recognition mistakes, punctuation, and broken phrasing. "
            "Keep natural spoken fillers if helpful.\n"
            f"{cleaned}"
        )
    return (
        "请审查下面这段 ASR 文本。"
        "请重点修正断句、错字、同音字和明显不通顺处；"
        "若停顿词能增强真实口语感，可以保留。\n"
        f"{cleaned}"
    )
