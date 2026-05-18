from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .audio_utils import ensure_reference_audio_duration
from .config import ROOT_DIR, settings
from .models import HealthResult
from .pipeline import convert_audio, speak_with_registered_voice
from .storage import ALLOWED_AUDIO_EXTS, ensure_dirs, new_job_id, save_upload, update_job_metadata


ensure_dirs()

app = FastAPI(title=settings.app_name, version="1.0.0")

origins = ["*"] if settings.cors_origins == "*" else [x.strip() for x in settings.cors_origins.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=ROOT_DIR / "static"), name="static")
app.mount("/media", StaticFiles(directory=settings.data_dir), name="media")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT_DIR / "static" / "index.html")


@app.get("/health", response_model=HealthResult)
def health() -> HealthResult:
    return HealthResult(
        ok=True,
        app=settings.app_name,
        configured={
            "dashscope_api_key": bool(settings.dashscope_api_key),
            "qwen_llm_api_key": bool(settings.qwen_llm_api_key),
            "public_base_url": bool(settings.public_base_url),
            "voice_cache_dir": settings.cache_dir.exists(),
        },
    )


@app.get("/api/audio-limits")
def audio_limits() -> dict[str, int]:
    return {
        "min_seconds": settings.ref_audio_min_s,
        "max_seconds": settings.ref_audio_max_s,
    }


def _is_supported_upload(upload: UploadFile) -> bool:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix in ALLOWED_AUDIO_EXTS:
        return True
    content_type = (upload.content_type or "").lower()
    return content_type.startswith("audio/") or content_type in {"video/mp4", "video/quicktime"}


def _validate_dialect(dialect: str) -> None:
    if dialect not in {"cantonese", "sichuanese", "hokkien"}:
        raise HTTPException(status_code=400, detail="暂只支持粤语、四川话、闽南话")


@app.post("/api/convert")
async def convert(
    dialect: str = Form(...),
    audio: UploadFile = File(...),
):
    _validate_dialect(dialect)
    if not _is_supported_upload(audio):
        raise HTTPException(status_code=400, detail="请上传音频文件")
    job_id = new_job_id()
    try:
        audio_path = await save_upload(audio, job_id)
        duration_s = await run_in_threadpool(ensure_reference_audio_duration, audio_path)
        result = await run_in_threadpool(convert_audio, job_id, audio_path, dialect)
        update_job_metadata(
            job_id,
            {
                "dialect": dialect,
                "status": result.status,
                "duration_s": round(duration_s, 3) if duration_s is not None else None,
                "has_gold_audio": bool(result.gold_audio_url),
                "has_voice_matched_audio": bool(result.voice_matched_audio_url),
                "warning_count": len(result.warnings),
            },
        )
        if not result.recommended_audio_url:
            raise RuntimeError("conversion produced no playable audio")
        return result
    except ValueError as exc:
        if "audio_path" in locals():
            audio_path.unlink(missing_ok=True)
            (settings.metadata_dir / f"{job_id}.json").unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="服务器繁忙，请稍后再试") from exc


@app.post("/api/speak-with-voice")
async def speak_with_voice(
    dialect: str = Form(...),
    voice_id: str = Form(...),
    text: str = Form(...),
):
    _validate_dialect(dialect)
    clean_text = " ".join(text.split()).strip()
    clean_voice_id = voice_id.strip()
    if not clean_voice_id or len(clean_voice_id) > 120:
        raise HTTPException(status_code=400, detail="音色未准备好，请先完成一次音色复刻")
    if len(clean_text) < 2:
        raise HTTPException(status_code=400, detail="请输入要朗读的文本")
    if len(clean_text) > 180:
        raise HTTPException(status_code=400, detail="文本过长，请控制在 180 字以内")
    job_id = new_job_id()
    try:
        result = await run_in_threadpool(speak_with_registered_voice, job_id, clean_text, dialect, clean_voice_id)
        update_job_metadata(
            job_id,
            {
                "dialect": dialect,
                "status": result.status,
                "mode": "registered_voice_text",
                "has_voice_matched_audio": True,
            },
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=502, detail="服务器繁忙，请稍后再试") from exc
