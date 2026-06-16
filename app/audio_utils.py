from __future__ import annotations

import json
import os
import shutil
import subprocess
import wave
from pathlib import Path

from .config import settings


def audio_duration_seconds(path: Path) -> float | None:
    """Return media duration when the local runtime can inspect the file."""
    duration = _duration_with_ffprobe(path)
    if duration is not None:
        return duration
    if path.suffix.lower() == ".wav":
        return _duration_with_wave(path)
    return None


def ensure_reference_audio_duration(path: Path) -> float | None:
    duration = audio_duration_seconds(path)
    if duration is not None and duration > settings.ref_audio_max_s:
        raise ValueError(f"音频过长，请控制在 {settings.ref_audio_max_s}s 以内")
    return duration


def make_browser_preview_audio(source_path: Path, target_path: Path) -> tuple[Path, float | None]:
    duration = audio_duration_seconds(source_path)
    if source_path.suffix.lower() in {".mp3", ".wav", ".m4a", ".mp4", ".aac", ".ogg", ".webm"}:
        return source_path, duration
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return source_path, duration
    target_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "24000",
        "-b:a",
        "96k",
        str(target_path),
    ]
    try:
        proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=45)
    except (OSError, subprocess.TimeoutExpired):
        return source_path, duration
    if proc.returncode != 0 or not target_path.exists() or target_path.stat().st_size == 0:
        return source_path, duration
    return target_path, duration or audio_duration_seconds(target_path)


def speed_audio_to_duration(path: Path, target_duration_s: float, *, tolerance_ratio: float = 0.08) -> float | None:
    """Speed up an audio file in-place when it is clearly slower than the target."""
    current_duration = audio_duration_seconds(path)
    if current_duration is None or target_duration_s <= 0:
        return current_duration
    if current_duration <= max(target_duration_s * (1 + tolerance_ratio), target_duration_s + 0.4):
        return current_duration
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return current_duration
    factor = current_duration / target_duration_s
    if factor <= 1:
        return current_duration
    filters = _atempo_filters(factor)
    tmp_path = path.with_name(f"{path.stem}.speedtmp{path.suffix}")
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(path),
        "-filter:a",
        filters,
        "-vn",
        str(tmp_path),
    ]
    try:
        proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return current_duration
    if proc.returncode != 0 or not tmp_path.exists() or tmp_path.stat().st_size == 0:
        tmp_path.unlink(missing_ok=True)
        return current_duration
    os.replace(tmp_path, path)
    return audio_duration_seconds(path) or current_duration


def _atempo_filters(factor: float) -> str:
    factors: list[float] = []
    while factor > 2.0:
        factors.append(2.0)
        factor /= 2.0
    while factor < 0.5:
        factors.append(0.5)
        factor /= 0.5
    factors.append(factor)
    return ",".join(f"atempo={item:.6f}" for item in factors)


def is_audio_too_short_error(error: object) -> bool:
    text = str(error)
    needles = (
        "Audio.AudioShortError",
        "audio too short",
        "AudioShortError",
        "cosyvoice]Engine return error code: 428",
    )
    return any(needle in text for needle in needles)


def _duration_with_ffprobe(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
        if proc.returncode != 0:
            return None
        raw = json.loads(proc.stdout or "{}")
        duration = float(raw.get("format", {}).get("duration") or 0)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired):
        return None
    return duration if duration > 0 else None


def _duration_with_wave(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as audio:
            frames = audio.getnframes()
            rate = audio.getframerate()
    except (OSError, wave.Error):
        return None
    if rate <= 0:
        return None
    return frames / float(rate)
