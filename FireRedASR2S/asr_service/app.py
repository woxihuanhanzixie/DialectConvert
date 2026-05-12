from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from .audio_io import AudioNormalizeError, get_runtime_capabilities, make_temp_dir, normalize_upload_to_wav
from .asr_engine import get_asr_engine
from .config import AsrServiceConfig
from .schemas import AsrResponse, AudioNormalizeResponse, ErrorResponse, HealthResponse
from .system_engine import get_asr_system_engine


app = FastAPI(
    title="Demo1 ASR Service",
    version="0.1.0",
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(
        status="ok",
        capabilities=get_runtime_capabilities(),
        engine={
            "plain_asr": get_asr_engine().health(),
            "asr_system": get_asr_system_engine().health(),
        },
    )


@app.post("/api/v1/audio/normalize", response_model=AudioNormalizeResponse)
async def normalize_audio(
    file: UploadFile = File(...),
    frontend_mode: str = Form("light_asr_safe"),
) -> AudioNormalizeResponse:
    work_dir = make_temp_dir(prefix="demo1_audio_normalize_")
    try:
        wav_path, meta = await normalize_upload_to_wav(file, work_dir, frontend_mode=frontend_mode or "light_asr_safe")
        return AudioNormalizeResponse(
            status="ok",
            wav_path=str(wav_path),
            audio_meta=meta,
            audio_quality=(meta.get("audio_frontend") or {}).get("work_audio"),
            conversion=meta.get("conversion"),
        )
    except AudioNormalizeError as e:
        raise HTTPException(status_code=400, detail=e.to_detail()) from e


@app.post("/api/v1/asr/transcribe", response_model=AsrResponse)
async def transcribe(
    file: UploadFile = File(...),
    enable_punc: bool = Form(True),
    return_timestamp: bool = Form(True),
    enable_vad: bool = Form(True),
    enable_lid: bool = Form(True),
    frontend_mode: str = Form("light_asr_safe"),
) -> AsrResponse:
    work_dir = make_temp_dir(prefix="demo1_asr_")
    try:
        cfg = AsrServiceConfig.from_env()
        wav_path, meta = await normalize_upload_to_wav(file, work_dir, frontend_mode=frontend_mode or cfg.frontend_mode_default)
        result = None
        try:
            result = get_asr_system_engine().process_file(
                wav_path,
                enable_vad=enable_vad,
                enable_lid=enable_lid,
                enable_punc=enable_punc,
            )
        except Exception:
            result = get_asr_engine().transcribe_file(
                wav_path,
                enable_punc=enable_punc,
                return_timestamp=return_timestamp,
            )
            result["detected_languages"] = []
            result["vad_segments_ms"] = []
            result["sentences"] = []
            result["words"] = []
        result["audio_quality"] = (meta.get("audio_frontend") or {}).get("work_audio")
        return AsrResponse(**result, audio_meta=meta)
    except AudioNormalizeError as e:
        raise HTTPException(status_code=400, detail=e.to_detail()) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"error_code": "ASR_ENGINE_ERROR", "message": str(e)}) from e
