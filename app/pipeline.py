from __future__ import annotations

from pathlib import Path

from .config import settings
from .models import ConversionResult
from .providers import ProviderError, enroll_voice, rewrite_to_dialect, synthesize, transcribe_audio
from .storage import (
    cleanup_runtime,
    local_output_path,
    read_voice_cache,
    voice_cache_key,
    write_voice_cache,
)


def convert_audio(job_id: str, audio_path: Path, dialect: str) -> ConversionResult:
    cleanup_runtime()
    warnings: list[str] = []

    source_text = transcribe_audio(audio_path)
    rewritten = rewrite_to_dialect(source_text, dialect)
    dialect_text = rewritten["dialect_text"]

    gold_audio_url = None
    voice_matched_audio_url = None
    voice_id = None

    try:
        gold_audio_url = synthesize(
            dialect_text,
            local_output_path(job_id, "gold"),
            voice=settings.qwen_tts_voice,
            model=settings.qwen_tts_model,
        )
    except ProviderError as exc:
        warnings.append(f"Gold Teacher 合成失败：{exc}")

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
            dialect_text,
            local_output_path(job_id, "voice_matched"),
            voice=voice_id,
            model=settings.qwen_voice_target_model,
        )
    except ProviderError as exc:
        warnings.append(f"Voice Matched 克隆音色合成失败，已保留 Gold Teacher：{exc}")

    recommended = voice_matched_audio_url or gold_audio_url
    status = "ok" if recommended else "failed"
    return ConversionResult(
        job_id=job_id,
        dialect=dialect,  # type: ignore[arg-type]
        source_text=source_text,
        dialect_text=dialect_text,
        pronunciation_note=rewritten.get("pronunciation_note", ""),
        gold_audio_url=gold_audio_url,
        voice_matched_audio_url=voice_matched_audio_url,
        recommended_audio_url=recommended,
        voice_id=voice_id,
        status=status,
        warnings=warnings,
    )

