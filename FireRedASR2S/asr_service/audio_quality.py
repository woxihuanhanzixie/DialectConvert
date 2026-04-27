from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf


def analyze_audio_quality(audio_path: str | Path) -> dict[str, Any]:
    path = Path(audio_path)
    data, sr = sf.read(str(path), always_2d=True)
    mono = _to_mono(data)
    peak = float(np.max(np.abs(mono))) if mono.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(mono)))) if mono.size else 0.0
    silence_ratio = _silence_ratio(mono)
    clipping_ratio = _clipping_ratio(mono)
    duration_s = round(len(mono) / sr, 3) if sr else 0.0

    peak_db = _to_db(peak)
    rms_db = _to_db(rms)
    quality_flags: list[str] = []
    score = 100.0

    if clipping_ratio > 0.01:
        quality_flags.append("possible_clipping")
        score -= 20
    if silence_ratio > 0.45:
        quality_flags.append("too_much_silence")
        score -= 18
    if rms_db < -35:
        quality_flags.append("too_quiet")
        score -= 15
    if peak_db > -0.5:
        quality_flags.append("peak_too_hot")
        score -= 10
    if duration_s < 1.0:
        quality_flags.append("too_short")
        score -= 8

    return {
        "path": str(path.resolve()),
        "duration_s": duration_s,
        "sample_rate": sr,
        "channels": data.shape[1] if data.ndim == 2 else 1,
        "peak_db": round(peak_db, 2),
        "rms_db": round(rms_db, 2),
        "silence_ratio": round(silence_ratio, 4),
        "clipping_ratio": round(clipping_ratio, 4),
        "quality_score": max(0.0, round(score, 2)),
        "quality_flags": quality_flags,
    }


def trim_long_silence(audio: np.ndarray, sr: int, threshold: float = 0.01) -> np.ndarray:
    if audio.size == 0:
        return audio
    active = np.where(np.abs(audio) > threshold)[0]
    if active.size == 0:
        return audio
    start = max(int(active[0]) - int(0.08 * sr), 0)
    end = min(int(active[-1]) + int(0.08 * sr), len(audio))
    return audio[start:end]


def peak_normalize(audio: np.ndarray, target_peak: float = 0.85) -> np.ndarray:
    if audio.size == 0:
        return audio
    peak = float(np.max(np.abs(audio)))
    if peak <= 1e-6:
        return audio
    scale = min(target_peak / peak, 1.6)
    return (audio * scale).astype(np.float32)


def detect_speech_segments(
    audio: np.ndarray,
    sr: int,
    *,
    frame_ms: int = 30,
    hop_ms: int = 15,
    min_segment_ms: int = 800,
    max_gap_ms: int = 220,
) -> list[tuple[int, int]]:
    if audio.size == 0 or sr <= 0:
        return []
    frame = max(1, int(sr * frame_ms / 1000))
    hop = max(1, int(sr * hop_ms / 1000))
    energies: list[float] = []
    starts: list[int] = []
    for start in range(0, max(1, len(audio) - frame + 1), hop):
        chunk = audio[start : start + frame]
        energies.append(float(np.sqrt(np.mean(np.square(chunk))) if chunk.size else 0.0))
        starts.append(start)
    if not energies:
        return []
    energy_arr = np.array(energies, dtype=np.float32)
    non_zero = energy_arr[energy_arr > 1e-5]
    if non_zero.size == 0:
        return []
    threshold = max(float(np.percentile(non_zero, 35) * 0.65), 0.008)
    active = energy_arr >= threshold
    min_frames = max(1, int(min_segment_ms / hop_ms))
    max_gap_frames = max(1, int(max_gap_ms / hop_ms))
    segments: list[tuple[int, int]] = []
    seg_start = -1
    last_active = -1
    for idx, is_active in enumerate(active):
        if is_active:
            if seg_start < 0:
                seg_start = idx
            last_active = idx
            continue
        if seg_start >= 0 and idx - last_active > max_gap_frames:
            if last_active - seg_start + 1 >= min_frames:
                start = starts[seg_start]
                end = min(starts[last_active] + frame, len(audio))
                segments.append((start, end))
            seg_start = -1
            last_active = -1
    if seg_start >= 0 and last_active >= seg_start and last_active - seg_start + 1 >= min_frames:
        start = starts[seg_start]
        end = min(starts[last_active] + frame, len(audio))
        segments.append((start, end))
    return segments


def concat_speech_segments(
    audio: np.ndarray,
    sr: int,
    segments: list[tuple[int, int]],
    *,
    pad_ms: int = 50,
    max_duration_s: float = 10.0,
    min_duration_s: float = 3.0,
) -> tuple[np.ndarray, dict[str, Any]]:
    if audio.size == 0 or sr <= 0:
        return audio, {
            "segment_count": 0,
            "speech_ratio": 0.0,
            "concat_duration_s": 0.0,
            "dropped_reason": "empty_audio",
            "concat_applied": False,
        }
    if not segments:
        return audio, {
            "segment_count": 0,
            "speech_ratio": 0.0,
            "concat_duration_s": round(len(audio) / sr, 3),
            "dropped_reason": "no_valid_speech_segment",
            "concat_applied": False,
        }
    pad = int(sr * pad_ms / 1000)
    enriched: list[dict[str, float | int]] = []
    for start, end in segments:
        s = max(0, start - pad)
        e = min(len(audio), end + pad)
        chunk = audio[s:e]
        if chunk.size == 0:
            continue
        rms = float(np.sqrt(np.mean(np.square(chunk))))
        duration_s = (e - s) / sr
        if duration_s < 0.8 or rms < 0.01:
            continue
        clipping_ratio = float(np.mean(np.abs(chunk) >= 0.995))
        if clipping_ratio > 0.03:
            continue
        center_bias = abs(((s + e) / 2) - (len(audio) / 2)) / max(len(audio), 1)
        score = (rms * 3.0) + min(duration_s, 3.5) - center_bias
        enriched.append({"start": s, "end": e, "score": score})
    if not enriched:
        return audio, {
            "segment_count": 0,
            "speech_ratio": 0.0,
            "concat_duration_s": round(len(audio) / sr, 3),
            "dropped_reason": "segments_filtered_out",
            "concat_applied": False,
        }
    enriched.sort(key=lambda item: float(item["score"]), reverse=True)
    picked: list[np.ndarray] = []
    total = 0
    max_samples = int(max_duration_s * sr)
    for item in enriched:
        seg = audio[int(item["start"]) : int(item["end"])]
        if total >= max_samples:
            break
        remaining = max_samples - total
        if seg.size > remaining:
            seg = seg[:remaining]
        if seg.size == 0:
            continue
        picked.append(seg)
        total += seg.size
    if not picked:
        return audio, {
            "segment_count": 0,
            "speech_ratio": 0.0,
            "concat_duration_s": round(len(audio) / sr, 3),
            "dropped_reason": "segments_truncated_to_zero",
            "concat_applied": False,
        }
    silence_bridge = np.zeros(int(sr * 0.04), dtype=np.float32)
    concat_audio = picked[0].astype(np.float32)
    for seg in picked[1:]:
        concat_audio = np.concatenate([concat_audio, silence_bridge, seg.astype(np.float32)])
    duration_s = len(concat_audio) / sr
    speech_ratio = float(sum(end - start for start, end in segments) / max(len(audio), 1))
    if duration_s < min_duration_s:
        return audio, {
            "segment_count": len(picked),
            "speech_ratio": round(speech_ratio, 4),
            "concat_duration_s": round(duration_s, 3),
            "dropped_reason": "concat_too_short",
            "concat_applied": False,
        }
    return concat_audio.astype(np.float32), {
        "segment_count": len(picked),
        "speech_ratio": round(speech_ratio, 4),
        "concat_duration_s": round(duration_s, 3),
        "dropped_reason": "",
        "concat_applied": True,
    }


def _to_mono(data: np.ndarray) -> np.ndarray:
    if data.ndim == 1:
        return data.astype(np.float32)
    return data.mean(axis=1).astype(np.float32)


def _to_db(value: float) -> float:
    if value <= 1e-8:
        return -120.0
    return 20 * math.log10(value)


def _silence_ratio(audio: np.ndarray, threshold: float = 0.01) -> float:
    if audio.size == 0:
        return 1.0
    return float(np.mean(np.abs(audio) < threshold))


def _clipping_ratio(audio: np.ndarray, threshold: float = 0.995) -> float:
    if audio.size == 0:
        return 0.0
    return float(np.mean(np.abs(audio) >= threshold))
