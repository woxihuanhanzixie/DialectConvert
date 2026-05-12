from __future__ import annotations

import shutil
import subprocess
import tempfile
import os
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from fastapi import UploadFile

from .audio_frontend import build_audio_tracks
from .audio_quality import validate_audio_for_mode

TARGET_SR = 16000
TARGET_CHANNELS = 1
SUPPORTED_EXTS = {".wav", ".mp3", ".m4a", ".webm", ".flac", ".aac", ".amr", ".3gp", ".ogg", ".opus"}


class AudioNormalizeError(RuntimeError):
    def __init__(self, message: str, error_code: str = "AUDIO_CONVERT_FAILED", details: dict[str, Any] | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}

    def to_detail(self) -> dict[str, Any]:
        return {"error_code": self.error_code, "message": str(self), **self.details}


def get_runtime_capabilities() -> dict[str, Any]:
    ffmpeg = shutil.which("ffmpeg")
    return {
        "ffmpeg_available": bool(ffmpeg),
        "ffmpeg_path": ffmpeg or "",
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
        raise AudioNormalizeError(
            f"Unsupported audio format: {suffix or 'unknown'}",
            error_code="UNSUPPORTED_AUDIO_FORMAT",
            details={"supported_upload_exts": sorted(SUPPORTED_EXTS)},
        )

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
        raise AudioNormalizeError(f"Audio file not found: {src}", error_code="AUDIO_CONVERT_FAILED")
    if src.suffix.lower() not in SUPPORTED_EXTS:
        raise AudioNormalizeError(
            f"Unsupported audio format: {src.suffix.lower() or 'unknown'}",
            error_code="UNSUPPORTED_AUDIO_FORMAT",
            details={"supported_upload_exts": sorted(SUPPORTED_EXTS)},
        )

    work_dir.mkdir(parents=True, exist_ok=True)
    raw_pcm_path = work_dir / f"{src.stem}_16k_raw.wav"
    out_path = work_dir / f"{src.stem}_16k.wav"
    conversion_meta = _convert_to_model_wav(src, raw_pcm_path)

    frontend = build_audio_tracks(raw_pcm_path, out_path, mode=frontend_mode)
    info = sf.info(str(out_path))
    validation_error = validate_audio_for_mode(frontend["work_audio"], frontend_mode)
    if validation_error is not None:
        error_code, message = validation_error
        raise AudioNormalizeError(message, error_code=error_code, details={"audio_frontend": frontend})
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
        "conversion": conversion_meta,
        "audio_frontend": frontend,
    }
    return out_path, meta


def make_temp_dir(prefix: str = "demo1_audio_") -> Path:
    configured = os.getenv("DEMO1_TEMP_DIR", "").strip()
    root = Path(__file__).resolve().parent.parent
    candidates = [
        Path(configured) if configured else None,
        root / "runtime_data" / "tmp",
        Path("C:/tmp"),
        Path(tempfile.gettempdir()),
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            temp_dir = candidate / f"{prefix}{uuid.uuid4().hex}"
            temp_dir.mkdir(parents=False, exist_ok=False)
            return temp_dir
        except OSError:
            continue
    temp_dir = Path.cwd() / f"{prefix}{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=False)
    return temp_dir


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


def _convert_to_model_wav(src: Path, raw_pcm_path: Path) -> dict[str, Any]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-vn",
            "-ac",
            str(TARGET_CHANNELS),
            "-ar",
            str(TARGET_SR),
            "-sample_fmt",
            "s16",
            str(raw_pcm_path),
        ]
        completed = subprocess.run(cmd, capture_output=True, text=True)
        stderr = _brief_stderr(completed.stderr)
        if completed.returncode != 0:
            raise AudioNormalizeError(
                stderr or "ffmpeg conversion failed.",
                error_code="AUDIO_CONVERT_FAILED",
                details={"ffmpeg_stderr": stderr},
            )
        return {
            "tool": "ffmpeg",
            "ffmpeg_path": ffmpeg,
            "command": " ".join(cmd),
            "stderr_summary": stderr,
        }

    if src.suffix.lower() != ".wav":
        raise AudioNormalizeError(
            "ffmpeg is required for non-wav audio conversion.",
            error_code="FFMPEG_NOT_FOUND",
            details={"supported_without_ffmpeg": [".wav"]},
        )

    data, sr = sf.read(str(src), always_2d=True)
    data = _to_mono(data)
    if sr != TARGET_SR:
        data = _resample(data, sr, TARGET_SR)
        sr = TARGET_SR
    sf.write(raw_pcm_path, data, sr, subtype="PCM_16")
    return {
        "tool": "soundfile_fallback",
        "ffmpeg_path": "",
        "command": "",
        "stderr_summary": "",
    }


def _brief_stderr(stderr: str, max_len: int = 1200) -> str:
    lines = [line.strip() for line in (stderr or "").splitlines() if line.strip()]
    text = "\n".join(lines[-8:])
    if len(text) <= max_len:
        return text
    return text[-max_len:]
