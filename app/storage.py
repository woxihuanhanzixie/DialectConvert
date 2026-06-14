from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile

from .config import settings


ALLOWED_AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".webm", ".flac", ".amr", ".mp4", ".3gp", ".3gpp", ".caf"}


def ensure_dirs() -> None:
    for path in (settings.upload_dir, settings.output_dir, settings.metadata_dir, settings.cache_dir):
        path.mkdir(parents=True, exist_ok=True)


def new_job_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"dc_{stamp}_{uuid.uuid4().hex[:8]}"


def safe_ext(filename: str | None, content_type: str | None = None) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in ALLOWED_AUDIO_EXTS:
        return ext
    if content_type:
        if "webm" in content_type:
            return ".webm"
        if "mpeg" in content_type or "mp3" in content_type:
            return ".mp3"
        if "wav" in content_type:
            return ".wav"
        if "ogg" in content_type:
            return ".ogg"
        if "mp4" in content_type or "m4a" in content_type:
            return ".m4a"
        if "3gpp" in content_type or "3gp" in content_type:
            return ".3gp"
        if "caf" in content_type or "x-caf" in content_type:
            return ".caf"
        if "quicktime" in content_type:
            return ".mp4"
    return ".wav"


async def save_upload(upload: UploadFile, job_id: str) -> Path:
    ensure_dirs()
    ext = safe_ext(upload.filename, upload.content_type)
    target = settings.upload_dir / f"{job_id}{ext}"
    max_bytes = settings.max_upload_mb * 1024 * 1024
    size = 0
    with target.open("wb") as fh:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                fh.close()
                target.unlink(missing_ok=True)
                raise ValueError(f"音频过大，请控制在 {settings.max_upload_mb} MB 以内")
            fh.write(chunk)
    write_job_metadata(
        job_id,
        {
            "job_id": job_id,
            "created_at": int(time.time()),
            "upload": {
                "path": target.name,
                "ext": ext,
                "content_type": upload.content_type or "",
                "bytes": size,
            },
        },
    )
    return target


def write_job_metadata(job_id: str, payload: dict) -> None:
    ensure_dirs()
    path = settings.metadata_dir / f"{job_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def update_job_metadata(job_id: str, payload: dict) -> None:
    ensure_dirs()
    path = settings.metadata_dir / f"{job_id}.json"
    try:
        current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except json.JSONDecodeError:
        current = {}
    current.update(payload)
    current["updated_at"] = int(time.time())
    write_job_metadata(job_id, current)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def public_url_for(path: Path) -> str:
    rel = path.resolve().relative_to(settings.data_dir.resolve()).as_posix()
    if settings.public_base_url:
        return f"{settings.public_base_url.rstrip('/')}/media/{rel}"
    return f"/media/{rel}"


def media_url_to_public(url: str) -> str:
    if url.startswith("/media/") and settings.public_base_url:
        return f"{settings.public_base_url.rstrip('/')}{url}"
    return url


def voice_cache_key(audio_path: Path, target_model: str) -> str:
    return hashlib.sha256(f"{sha256_file(audio_path)}:{target_model}".encode("utf-8")).hexdigest()


def read_voice_cache(cache_key: str) -> dict | None:
    path = settings.cache_dir / f"{cache_key}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if data.get("status") == "ok" and data.get("voice_id"):
        return data
    return None


def write_voice_cache(cache_key: str, payload: dict) -> None:
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    payload = {**payload, "updated_at": int(time.time())}
    (settings.cache_dir / f"{cache_key}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def cleanup_runtime() -> int:
    ensure_dirs()
    cutoff = time.time() - settings.cleanup_after_hours * 3600
    cache_cutoff = time.time() - settings.voice_cache_ttl_hours * 3600
    removed = 0
    for root in (settings.upload_dir, settings.output_dir, settings.metadata_dir):
        for path in root.rglob("*"):
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
    for path in settings.cache_dir.glob("*.json"):
        if path.is_file() and path.stat().st_mtime < cache_cutoff:
            path.unlink(missing_ok=True)
            removed += 1
    for root in (settings.upload_dir, settings.output_dir, settings.metadata_dir):
        for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()
    return removed


def local_output_path(job_id: str, label: str, ext: str = ".mp3") -> Path:
    ensure_dirs()
    return settings.output_dir / f"{job_id}_{label}{ext}"


def atomic_write_bytes(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
