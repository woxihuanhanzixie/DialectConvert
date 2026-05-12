from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from asr_service.audio_io import get_runtime_capabilities, normalize_file_to_wav
from dialect_service.pipeline_engine import get_pipeline_engine
from fireredasr2s.dialect_pipeline.dialects import normalize_dialect_style


def get_demo_capabilities() -> dict[str, Any]:
    return get_runtime_capabilities()


def run_pipeline_from_audio(
    audio_path: str,
    *,
    speaker_ref_audio: str = "",
    enable_punc: bool = True,
    enable_rewrite: bool = True,
    enable_tts: bool = True,
    voice: str = "Kiki",
    segment_max_len: int = 28,
    input_lang: str = "",
    target_dialect: str = "yue",
    dialect_style: str = "",
    voice_clone_enabled: bool = False,
    voice_clone_provider: str = "openvoice",
) -> dict[str, Any]:
    engine = get_pipeline_engine()
    dialect_style = normalize_dialect_style(target_dialect, dialect_style)
    ref_frontend_mode = "clone_ref_vad_concat" if engine.cfg.reference_audio_strategy == "vad_concat" else "clone_ref_safe"
    work_dir = Path("runtime_data") / "web_demo_uploads"
    wav_path, meta = normalize_file_to_wav(audio_path, work_dir)
    wav_path = wav_path.resolve()
    ref_audio_path = ""
    if voice_clone_enabled:
        ref_dir = Path("runtime_data") / "web_demo_refs"
        ref_source = speaker_ref_audio or audio_path
        ref_audio_path, ref_meta = normalize_file_to_wav(ref_source, ref_dir, frontend_mode=ref_frontend_mode)
        ref_audio_path = str(Path(ref_audio_path).resolve())
        meta["voice_clone_ref_audio"] = {
            "source": "uploaded_ref" if speaker_ref_audio else "input_audio_auto",
            "path": ref_audio_path,
            "duration_s": ref_meta.get("duration_s", 0.0),
            "raw_path": ref_meta.get("raw_path", ""),
            "normalized_path": ref_meta.get("normalized_path", ""),
            "frontend_mode": ref_meta.get("frontend_mode", ""),
            "audio_frontend": ref_meta.get("audio_frontend", {}),
        }
    if voice_clone_provider:
        engine.cfg.voice_conversion_provider = voice_clone_provider
        engine.cfg.voice_clone_provider = engine.cfg.text_clone_provider or "qwen_vc"
    result = engine.process_audio(
        wav_path,
        enable_punc=enable_punc,
        enable_rewrite=enable_rewrite,
        enable_tts=enable_tts,
        segment_max_len=segment_max_len,
        voice=voice,
        voice_clone_enabled=voice_clone_enabled,
        speaker_ref_audio=str(ref_audio_path) if ref_audio_path else "",
        target_dialect=target_dialect,
        dialect_style=dialect_style,
    )
    result["source_audio"] = meta
    return result


def load_eval_rows(
    result_jsonl: str | Path = "runtime_data/step2_output/results_audio16k_yue_tts.jsonl",
) -> list[dict[str, Any]]:
    p = Path(result_jsonl)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
