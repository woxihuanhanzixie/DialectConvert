from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from fastapi import UploadFile

from .audio_frontend import build_audio_tracks

TARGET_SR = 16000
TARGET_CHANNELS = 1
SUPPORTED_EXTS = {".wav", ".mp3", ".m4a", ".webm", ".flac"}


class AudioNormalizeError(RuntimeError):
    pass


def get_runtime_capabilities() -> dict[str, Any]:
    ffmpeg = shutil.which("ffmpeg")
    return {
        "ffmpeg_available": bool(ffmpeg),
        "supported_upload_exts": sorted(SUPPORTED_EXTS),
        "preferred_format": "16kHz mono wav",
        "microphone_hint": "浏览器录音依赖当前环境；若不可用，请改用上传音频。",
    }


async def normalize_upload_to_wav(
    upload: UploadFile,
    work_dir: Path,
    *,
    frontend_mode: str = "light_asr_safe",
) -> tuple[Path, dict[str, Any]]:
    suffix = Path(upload.filename or "upload.wav").suffix.lower()
    if suffix not in SUPPORTED_EXTS:
        raise AudioNormalizeError(f"Unsupported audio format: {suffix or 'unknown'}")

    work_dir.mkdir(parents=True, exist_ok=True)
    raw_path = work_dir / f"input{suffix or '.wav'}"
    with raw_path.open("wb") as f:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
    return normalize_file_to_wav(raw_path, work_dir, frontend_mode=frontend_mode)


def normalize_file_to_wav(
    src_path: str | Path,
    work_dir: Path,
    *,
    frontend_mode: str = "light_asr_safe",
) -> tuple[Path, dict[str, Any]]:
    src = Path(src_path)
    if not src.exists():
        raise AudioNormalizeError(f"Audio file not found: {src}")

    work_dir.mkdir(parents=True, exist_ok=True)
    raw_pcm_path = work_dir / f"{src.stem}_16k_raw.wav"
    out_path = work_dir / f"{src.stem}_16k.wav"
    if src.suffix.lower() == ".wav":
        data, sr = sf.read(str(src), always_2d=True)
        data = _to_mono(data)
        if sr != TARGET_SR:
            data = _resample(data, sr, TARGET_SR)
            sr = TARGET_SR
        sf.write(raw_pcm_path, data, sr, subtype="PCM_16")
    else:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise AudioNormalizeError("ffmpeg is required for non-wav audio conversion.")
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-ac",
            str(TARGET_CHANNELS),
            "-ar",
            str(TARGET_SR),
            str(raw_pcm_path),
        ]
        completed = subprocess.run(cmd, capture_output=True, text=True)
        if completed.returncode != 0:
            raise AudioNormalizeError(completed.stderr.strip() or "ffmpeg conversion failed.")

    frontend = build_audio_tracks(raw_pcm_path, out_path, mode=frontend_mode)
    info = sf.info(str(out_path))
    meta = {
        "original_path": str(src.resolve()),
        "raw_path": str(raw_pcm_path.resolve()),
        "normalized_path": str(out_path.resolve()),
        "work_path": str(out_path.resolve()),
        "frontend_mode": frontend_mode,
        "sample_rate": info.samplerate,
        "channels": info.channels,
        "duration_s": round(float(info.duration), 3),
        "format": info.format,
        "audio_frontend": frontend,
    }
    return out_path, meta


def make_temp_dir(prefix: str = "demo1_audio_") -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix))


def _to_mono(data: np.ndarray) -> np.ndarray:
    if data.ndim == 1:
        return data
    return data.mean(axis=1)


def _resample(data: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr:
        return data
    if data.size == 0:
        return data
    duration = len(data) / src_sr
    src_x = np.linspace(0, duration, num=len(data), endpoint=False)
    dst_len = max(1, round(len(data) * dst_sr / src_sr))
    dst_x = np.linspace(0, duration, num=dst_len, endpoint=False)
    return np.interp(dst_x, src_x, data).astype(np.float32)
