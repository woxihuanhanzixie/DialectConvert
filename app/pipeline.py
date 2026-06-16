from __future__ import annotations

from pathlib import Path

from .audio_utils import audio_duration_seconds, is_audio_too_short_error, speed_audio_to_duration
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
    voice_cache_metadata,
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


def _format_seconds(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _instruction_units(text: str) -> int:
    return sum(2 if "\u4e00" <= char <= "\u9fff" else 1 for char in text)


def build_tts_instruction(
    dialect: str,
    prosody_instruction: str,
    reference_duration_s: float | None = None,
    *,
    retry_faster: bool = False,
) -> str:
    """Keep CosyVoice instruction short enough for dialect plus emotion control."""
    base = DIALECT_TTS_CONTROLS[dialect]["instruction"].rstrip("。")
    prosody = (prosody_instruction or "自然口语，有轻微起伏").strip("。；; ")
    parts = [base]
    if reference_duration_s and reference_duration_s > 0:
        target = _format_seconds(reference_duration_s)
        if retry_faster:
            parts.append(f"语速加快，停顿更短，约{target}秒读完")
        else:
            parts.append(f"贴近参考录音语速，约{target}秒读完")
    parts.append(prosody)
    instruction = f"{'，'.join(part for part in parts if part)}。"
    if _instruction_units(instruction) <= 95:
        return instruction
    if reference_duration_s and reference_duration_s > 0:
        target = _format_seconds(reference_duration_s)
        speed = f"语速加快，约{target}秒读完" if retry_faster else f"约{target}秒读完"
        compact = f"{base}，{speed}，自然口语。"
        if _instruction_units(compact) <= 95:
            return compact
    return f"{base}，自然口语，有情绪起伏。"


def _is_too_slow_for_reference(output_path: Path, reference_duration_s: float | None) -> bool:
    if not reference_duration_s or reference_duration_s <= 0:
        return False
    output_duration_s = audio_duration_seconds(output_path)
    if output_duration_s is None:
        return False
    return output_duration_s > max(reference_duration_s * 1.15, reference_duration_s + 0.75)


def convert_audio(
    job_id: str,
    audio_path: Path,
    dialect: str,
    reference_duration_s: float | None = None,
) -> ConversionResult:
    cleanup_runtime()
    warnings: list[str] = []
    if reference_duration_s is None:
        reference_duration_s = audio_duration_seconds(audio_path)

    raw_source_text = transcribe_audio(audio_path)
    expression = analyze_expression(raw_source_text)
    source_text = expression["display_text"]
    rag_context = retrieve_dialect_knowledge(source_text, dialect)
    rewritten = rewrite_to_dialect(source_text, dialect, expression, rag_context=rag_context)
    dialect_text = rewritten["dialect_text"]
    tts_control = DIALECT_TTS_CONTROLS[dialect]
    synthesis_text = dialect_text
    tts_instruction = build_tts_instruction(dialect, expression["prosody_instruction"], reference_duration_s)

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
        cache_metadata = voice_cache_metadata(audio_path, settings.qwen_voice_target_model, reference_duration_s)
        cached = read_voice_cache(cache_key, expected=cache_metadata)
        voice_id = cached["voice_id"] if cached else enroll_voice(audio_path)
        if not cached:
            write_voice_cache(
                cache_key,
                {
                    **cache_metadata,
                    "status": "ok",
                    "voice_id": voice_id,
                    "target_model": settings.qwen_voice_target_model,
                    "enrollment_model": settings.qwen_voice_enrollment_model,
                },
            )
        voice_output_path = local_output_path(job_id, "voice_matched")
        voice_matched_audio_url = synthesize(
            synthesis_text,
            voice_output_path,
            voice=voice_id,
            model=settings.qwen_voice_target_model,
            instruction=tts_instruction,
            language_hint=tts_control["language_hint"],
        )
        if _is_too_slow_for_reference(voice_output_path.with_suffix(".mp3"), reference_duration_s):
            retry_instruction = build_tts_instruction(
                dialect,
                expression["prosody_instruction"],
                reference_duration_s,
                retry_faster=True,
            )
            voice_matched_audio_url = synthesize(
                synthesis_text,
                voice_output_path,
                voice=voice_id,
                model=settings.qwen_voice_target_model,
                instruction=retry_instruction,
                language_hint=tts_control["language_hint"],
            )
            if _is_too_slow_for_reference(voice_output_path.with_suffix(".mp3"), reference_duration_s):
                speed_audio_to_duration(voice_output_path.with_suffix(".mp3"), reference_duration_s)
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
