from __future__ import annotations

import json
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
