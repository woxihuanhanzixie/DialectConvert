from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import soundfile as sf

from asr_service.audio_io import SUPPORTED_EXTS, get_runtime_capabilities, normalize_file_to_wav
from asr_service.config import AsrServiceConfig
from dialect_service.pipeline_engine import get_pipeline_engine
from fireredasr2s.dialect_pipeline.dialects import normalize_dialect_style


def get_demo_capabilities() -> dict[str, Any]:
    caps = get_runtime_capabilities()
    engine = get_pipeline_engine()
    asr_cfg = AsrServiceConfig.from_env()
    caps.update(
        {
            "asr_provider": asr_cfg.provider,
            "asr_cloud_provider": asr_cfg.cloud_provider,
            "asr_cloud_model": asr_cfg.cloud_model,
            "asr_cloud_api_key_configured": bool(asr_cfg.cloud_api_key),
            "voice_conversion_provider": engine.cfg.voice_conversion_provider or "openvoice",
            "voice_conversion_mode": engine.cfg.voice_conversion_mode or "teacher_audio_to_audio",
            "qwen_voice_target_model": engine.cfg.qwen_voice_target_model,
            "reference_audio_strategy": engine.cfg.reference_audio_strategy or "vad_concat",
            "speaker_ref_audio_min_s": engine.cfg.speaker_ref_audio_min_s,
            "speaker_ref_audio_max_s": engine.cfg.speaker_ref_audio_max_s,
        }
    )
    return caps


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
    asr_cfg = AsrServiceConfig.from_env()
    dialect_style = normalize_dialect_style(target_dialect, dialect_style)
    ref_frontend_mode = "clone_ref_vad_concat" if engine.cfg.reference_audio_strategy == "vad_concat" else "clone_ref_safe"
    work_dir = Path("runtime_data") / "web_demo_uploads"
    src_audio_path = Path(audio_path).resolve()
    if _can_use_direct_cloud_asr(src_audio_path, asr_cfg):
        wav_path = src_audio_path
        meta = _inspect_audio_file(src_audio_path, frontend_mode="cloud_asr_direct")
    else:
        wav_path, meta = normalize_file_to_wav(audio_path, work_dir)
        wav_path = wav_path.resolve()
    ref_audio_path = ""
    if voice_clone_enabled:
        ref_dir = Path("runtime_data") / "web_demo_refs"
        ref_source = speaker_ref_audio or audio_path
        if _can_use_raw_qwen_reference(ref_source, voice_clone_provider):
            ref_audio_path = str(Path(ref_source).resolve())
            ref_meta = _inspect_audio_file(ref_audio_path, frontend_mode="qwen_voice_clone_raw_ref")
        else:
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


def _can_use_direct_cloud_asr(path: Path, cfg: AsrServiceConfig) -> bool:
    if cfg.provider not in {"api_first", "cloud_first", "dashscope", "qwen"}:
        return False
    if not cfg.cloud_api_key:
        return False
    return path.suffix.lower() in {".wav", ".mp3", ".aac", ".m4a", ".amr", ".3gp", ".flac"}


def _can_use_raw_qwen_reference(ref_source: str | Path, voice_clone_provider: str) -> bool:
    provider = (voice_clone_provider or "").strip().lower()
    if provider not in {"qwen_voice_clone", "qwen_vc", "qwen"}:
        return False
    return Path(ref_source).suffix.lower() in SUPPORTED_EXTS


def _inspect_audio_file(path_value: str | Path, *, frontend_mode: str) -> dict[str, Any]:
    path = Path(path_value).resolve()
    try:
        info = sf.info(str(path))
        sample_rate = int(info.samplerate)
        channels = int(info.channels)
        duration_s = round(float(info.duration), 3)
        fmt = str(info.format)
    except Exception:
        sample_rate = 0
        channels = 0
        duration_s = 0.0
        fmt = path.suffix.lower().lstrip(".")
    audio_summary = {
        "path": str(path),
        "duration_s": duration_s,
        "sample_rate": sample_rate,
        "channels": channels,
        "peak_db": None,
        "rms_db": None,
        "silence_ratio": None,
        "clipping_ratio": None,
        "quality_score": None,
        "quality_flags": [],
    }
    return {
        "original_path": str(path),
        "raw_path": str(path),
        "normalized_path": str(path),
        "work_path": str(path),
        "frontend_mode": frontend_mode,
        "sample_rate": sample_rate,
        "channels": channels,
        "duration_s": duration_s,
        "format": fmt,
        "conversion": {"tool": "none", "reason": frontend_mode},
        "audio_frontend": {
            "mode": frontend_mode,
            "raw_audio": audio_summary,
            "work_audio": audio_summary,
            "raw_path": str(path),
            "work_path": str(path),
            "quality_score": None,
            "quality_flags": [],
        },
    }


def load_eval_rows(
    result_jsonl: str | Path = "runtime_data/step2_output/results_audio16k_yue_tts.jsonl",
) -> list[dict[str, Any]]:
    p = Path(result_jsonl)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
