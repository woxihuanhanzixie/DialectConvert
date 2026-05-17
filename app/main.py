from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .config import ROOT_DIR, settings
from .models import HealthResult
from .pipeline import convert_audio
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


def _is_supported_upload(upload: UploadFile) -> bool:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix in ALLOWED_AUDIO_EXTS:
        return True
    content_type = (upload.content_type or "").lower()
    return content_type.startswith("audio/") or content_type in {"video/mp4", "video/quicktime"}


@app.post("/api/convert")
async def convert(
    dialect: str = Form(...),
    audio: UploadFile = File(...),
):
    if dialect not in {"cantonese", "sichuanese", "hokkien"}:
        raise HTTPException(status_code=400, detail="暂只支持粤语、四川话、闽南话")
    if not _is_supported_upload(audio):
        raise HTTPException(status_code=400, detail="请上传音频文件")
    job_id = new_job_id()
    try:
        audio_path = await save_upload(audio, job_id)
        result = await run_in_threadpool(convert_audio, job_id, audio_path, dialect)
        update_job_metadata(
            job_id,
            {
                "dialect": dialect,
                "status": result.status,
                "has_gold_audio": bool(result.gold_audio_url),
                "has_voice_matched_audio": bool(result.voice_matched_audio_url),
                "warning_count": len(result.warnings),
            },
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
