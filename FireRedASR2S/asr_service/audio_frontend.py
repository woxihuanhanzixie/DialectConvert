from __future__ import annotations

from pathlib import Path
from typing import Any

import soundfile as sf

from .audio_quality import (
    analyze_audio_quality,
    concat_speech_segments,
    detect_speech_segments,
    peak_normalize,
    trim_long_silence,
)


def build_audio_tracks(
    raw_path: str | Path,
    work_path: str | Path,
    *,
    mode: str = "light_asr_safe",
) -> dict[str, Any]:
    raw_path = Path(raw_path)
    work_path = Path(work_path)
    work_path.parent.mkdir(parents=True, exist_ok=True)

    raw_quality = analyze_audio_quality(raw_path)
    data, sr = sf.read(str(raw_path), always_2d=True)
    mono = data.mean(axis=1).astype("float32") if data.ndim == 2 else data.astype("float32")

    if mode == "light_asr_safe":
        mono = trim_long_silence(mono, sr)
        mono = peak_normalize(mono, 0.85)
    elif mode == "clone_ref_safe":
        mono = trim_long_silence(mono, sr)
    elif mode == "clone_ref_vad_concat":
        trimmed = trim_long_silence(mono, sr)
        segments = detect_speech_segments(trimmed, sr)
        concat_audio, concat_meta = concat_speech_segments(
            trimmed,
            sr,
            segments,
            max_duration_s=10.0,
            min_duration_s=3.0,
        )
        mono = peak_normalize(concat_audio, 0.92)
    else:
        concat_meta = {
            "segment_count": 0,
            "speech_ratio": 0.0,
            "concat_duration_s": round(len(mono) / sr, 3) if sr else 0.0,
            "dropped_reason": f"unknown_mode:{mode}",
            "concat_applied": False,
        }
        segments = []
    if mode != "clone_ref_vad_concat":
        segments = []
        concat_meta = {
            "segment_count": 0,
            "speech_ratio": 0.0,
            "concat_duration_s": round(len(mono) / sr, 3) if sr else 0.0,
            "dropped_reason": "",
            "concat_applied": False,
        }

    sf.write(str(work_path), mono, sr, subtype="PCM_16")
    work_quality = analyze_audio_quality(work_path)

    return {
        "mode": mode,
        "raw_audio": raw_quality,
        "work_audio": work_quality,
        "raw_path": str(raw_path.resolve()),
        "work_path": str(work_path.resolve()),
        "quality_score": work_quality["quality_score"],
        "quality_flags": work_quality["quality_flags"],
        "speech_segment_count": concat_meta["segment_count"],
        "speech_ratio": concat_meta["speech_ratio"],
        "concat_duration_s": concat_meta["concat_duration_s"],
        "concat_applied": concat_meta["concat_applied"],
        "concat_fallback_reason": concat_meta["dropped_reason"],
        "detected_segments": [[int(start), int(end)] for start, end in segments],
    }
