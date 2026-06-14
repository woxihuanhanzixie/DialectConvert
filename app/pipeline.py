from __future__ import annotations

from pathlib import Path

from .audio_utils import is_audio_too_short_error
from .config import settings
from .models import ConversionResult, RegisteredVoiceSpeakResult
from .providers import (
    ProviderError,
    analyze_expression,
    enroll_voice,
    rewrite_to_dialect,
    synthesize,
    transcribe_audio,
)
from .rag import retrieve_dialect_knowledge
from .storage import (
    cleanup_runtime,
    local_output_path,
    read_voice_cache,
    voice_cache_key,
    write_voice_cache,
)


DIALECT_TTS_CONTROLS = {
    "cantonese": {
        "instruction": "请用广东话表达。",
        "language_hint": "zh",
    },
    "sichuanese": {
        "instruction": "请用四川话表达。",
        "language_hint": "zh",
    },
    "hokkien": {
        "instruction": "请用闽南话表达。",
        "language_hint": "zh",
    },
}


def build_tts_instruction(dialect: str, prosody_instruction: str) -> str:
    """Keep CosyVoice instruction short enough for dialect plus emotion control."""
    base = DIALECT_TTS_CONTROLS[dialect]["instruction"].rstrip("。")
    prosody = (prosody_instruction or "自然口语，有轻微起伏").strip("。；; ")
    instruction = f"{base}，{prosody}。"
    if len(instruction) <= 95:
        return instruction
    return f"{base}，自然口语，有情绪起伏。"


def convert_audio(job_id: str, audio_path: Path, dialect: str) -> ConversionResult:
    cleanup_runtime()
    warnings: list[str] = []

    raw_source_text = transcribe_audio(audio_path)
    expression = analyze_expression(raw_source_text)
    source_text = expression["display_text"]
    rag_context = retrieve_dialect_knowledge(source_text, dialect)
    rewritten = rewrite_to_dialect(source_text, dialect, expression, rag_context=rag_context)
    dialect_text = rewritten["dialect_text"]
    tts_control = DIALECT_TTS_CONTROLS[dialect]
    synthesis_text = dialect_text
    tts_instruction = build_tts_instruction(dialect, expression["prosody_instruction"])

    gold_audio_url = None
    voice_matched_audio_url = None
    voice_id = None

    # Gold Teacher: cosyvoice-v3-plus does NOT support the "instruction" parameter;
    # dialect pronunciation is carried by the dialect text itself.
    try:
        gold_audio_url = synthesize(
            synthesis_text,
            local_output_path(job_id, "gold"),
            voice=settings.qwen_tts_voice,
            model=settings.qwen_tts_model,
            language_hint=tts_control["language_hint"],
        )
    except ProviderError as exc:
        warnings.append(f"Gold Teacher synthesis failed: {exc}")

    # Voice Matched: cosyvoice-v3.5-plus + cloned voice_id with instruction.
    try:
        cache_key = voice_cache_key(audio_path, settings.qwen_voice_target_model)
        cached = read_voice_cache(cache_key)
        voice_id = cached["voice_id"] if cached else enroll_voice(audio_path)
        if not cached:
            write_voice_cache(
                cache_key,
                {
                    "status": "ok",
                    "voice_id": voice_id,
                    "target_model": settings.qwen_voice_target_model,
                    "enrollment_model": settings.qwen_voice_enrollment_model,
                },
            )
        voice_matched_audio_url = synthesize(
            synthesis_text,
            local_output_path(job_id, "voice_matched"),
            voice=voice_id,
            model=settings.qwen_voice_target_model,
            instruction=tts_instruction,
            language_hint=tts_control["language_hint"],
        )
    except ProviderError as exc:
        if is_audio_too_short_error(exc):
            warnings.append("Voice Matched 克隆音色失败：服务器繁忙，请稍后再试")
        else:
            warnings.append(f"Voice Matched cloned synthesis failed; kept Gold Teacher: {exc}")

    recommended = voice_matched_audio_url or gold_audio_url
    status = "ok" if recommended else "failed"
    return ConversionResult(
        job_id=job_id,
        dialect=dialect,  # type: ignore[arg-type]
        source_text=source_text,
        dialect_text=dialect_text,
        pronunciation_note=rewritten.get("pronunciation_note", ""),
        emotion_label=expression.get("emotion_label", ""),
        prosody_instruction=expression.get("prosody_instruction", ""),
        gold_audio_url=gold_audio_url,
        voice_matched_audio_url=voice_matched_audio_url,
        recommended_audio_url=recommended,
        voice_id=voice_id,
        status=status,
        warnings=warnings,
    )


def speak_with_registered_voice(job_id: str, text: str, dialect: str, voice_id: str) -> RegisteredVoiceSpeakResult:
    expression = analyze_expression(text)
    source_text = expression["display_text"]
    rag_context = retrieve_dialect_knowledge(source_text, dialect)
    rewritten = rewrite_to_dialect(source_text, dialect, expression, rag_context=rag_context)
    dialect_text = rewritten["dialect_text"]
    tts_control = DIALECT_TTS_CONTROLS[dialect]
    tts_instruction = build_tts_instruction(dialect, expression["prosody_instruction"])
    audio_url = synthesize(
        dialect_text,
        local_output_path(job_id, "registered_voice"),
        voice=voice_id,
        model=settings.qwen_voice_target_model,
        instruction=tts_instruction,
        language_hint=tts_control["language_hint"],
    )
    return RegisteredVoiceSpeakResult(
        job_id=job_id,
        dialect=dialect,  # type: ignore[arg-type]
        source_text=source_text,
        dialect_text=dialect_text,
        emotion_label=expression.get("emotion_label", ""),
        prosody_instruction=expression.get("prosody_instruction", ""),
        audio_url=audio_url,
    )
