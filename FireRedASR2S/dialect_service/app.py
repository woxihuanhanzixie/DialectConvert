from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from asr_service.audio_io import AudioNormalizeError, get_runtime_capabilities, make_temp_dir, normalize_file_to_wav, normalize_upload_to_wav
from fireredasr2s.dialect_pipeline.dialects import is_supported_dialect, normalize_dialect_style, supported_dialect_codes

from .pipeline_engine import get_pipeline_engine
from .schemas import (
    HealthResponse,
    PipelineResponse,
    ReviewRequest,
    ReviewResponse,
    RewriteRequest,
    RewriteResponse,
    TtsRequest,
    TtsResponse,
)


app = FastAPI(title="Demo1 Dialect Service", version="0.1.0")


def _validate_dialect(target_dialect: str, dialect_style: str = "") -> str:
    if not is_supported_dialect(target_dialect):
        supported = ", ".join(supported_dialect_codes())
        raise HTTPException(status_code=400, detail=f"Unsupported dialect: {target_dialect}. Supported dialects: {supported}.")
    return normalize_dialect_style(target_dialect, dialect_style)


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    engine = get_pipeline_engine()
    return HealthResponse(
        status="ok",
        supported_dialects=supported_dialect_codes(),
        default_voice=engine.cfg.qwen_tts_voice,
        runtime={**engine.health(), **get_runtime_capabilities()},
    )


@app.post("/api/v1/text/review", response_model=ReviewResponse)
def review_text(req: ReviewRequest) -> ReviewResponse:
    engine = get_pipeline_engine()
    engine.cfg.provider = req.provider
    return ReviewResponse(**engine.process_text(req.text, enable_rewrite=False, enable_tts=False)["review"])


@app.post("/api/v1/dialect/rewrite", response_model=RewriteResponse)
def rewrite(req: RewriteRequest) -> RewriteResponse:
    dialect_style = _validate_dialect(req.target_dialect, req.dialect_style)
    engine = get_pipeline_engine()
    engine.cfg.provider = req.provider
    engine.cfg.default_target_dialect = req.target_dialect
    engine.cfg.default_dialect_style = dialect_style
    result = engine.process_text(
        req.text,
        enable_rewrite=True,
        enable_tts=False,
        segment_max_len=req.segment_max_len,
        target_dialect=req.target_dialect,
        dialect_style=dialect_style,
    )
    return RewriteResponse(**result["rewrite"])


@app.post("/api/v1/dialect/tts", response_model=TtsResponse)
def tts(req: TtsRequest) -> TtsResponse:
    engine = get_pipeline_engine()
    engine.cfg.qwen_tts_model = req.model
    engine.cfg.qwen_tts_voice = req.voice
    engine.cfg.qwen_tts_language_type = req.language_type
    engine.cfg.voice_conversion_provider = req.voice_clone_provider
    engine.cfg.voice_clone_provider = engine.cfg.text_clone_provider or "qwen_vc"
    result = engine.process_text(
        req.text,
        enable_rewrite=False,
        enable_tts=True,
        voice=req.voice,
        voice_clone_enabled=req.voice_clone_enabled,
        speaker_ref_audio=req.speaker_ref_audio,
    )
    return TtsResponse(**result["tts"])


@app.post("/api/v1/dialect/pipeline", response_model=PipelineResponse)
async def pipeline(
    file: UploadFile | None = File(default=None),
    speaker_ref_audio: UploadFile | None = File(default=None),
    text: str = Form(default=""),
    enable_punc: bool = Form(default=True),
    enable_rewrite: bool = Form(default=True),
    enable_tts: bool = Form(default=True),
    segment_max_len: int = Form(default=28),
    voice: str = Form(default="Kiki"),
    input_lang: str = Form(default="zh"),
    target_dialect: str = Form(default="yue"),
    dialect_style: str = Form(default=""),
    voice_clone_enabled: bool = Form(default=False),
    voice_clone_provider: str = Form(default="openvoice"),
) -> PipelineResponse:
    engine = get_pipeline_engine()
    dialect_style = _validate_dialect(target_dialect, dialect_style)
    engine.cfg.default_target_dialect = target_dialect
    engine.cfg.default_dialect_style = dialect_style
    engine.cfg.voice_conversion_provider = voice_clone_provider
    engine.cfg.voice_clone_provider = engine.cfg.text_clone_provider or "qwen_vc"
    ref_frontend_mode = "clone_ref_vad_concat" if engine.cfg.reference_audio_strategy == "vad_concat" else "clone_ref_safe"
    try:
        ref_audio_path = ""
        if speaker_ref_audio is not None:
            ref_dir = make_temp_dir(prefix="demo1_ref_audio_")
            ref_audio_path, ref_meta = await normalize_upload_to_wav(speaker_ref_audio, ref_dir, frontend_mode=ref_frontend_mode)
        if file is not None:
            work_dir = make_temp_dir(prefix="demo1_pipeline_")
            wav_path, meta = await normalize_upload_to_wav(file, work_dir)
            if voice_clone_enabled and not ref_audio_path:
                ref_dir = make_temp_dir(prefix="demo1_ref_audio_auto_")
                ref_source = meta.get("original_path") or meta.get("raw_path") or str(wav_path)
                ref_audio_path, ref_meta = normalize_file_to_wav(ref_source, ref_dir, frontend_mode=ref_frontend_mode)
                meta["voice_clone_ref_audio"] = {
                    "source": "input_audio_auto",
                    "path": str(ref_audio_path),
                    "duration_s": ref_meta.get("duration_s", 0.0),
                    "raw_path": ref_meta.get("raw_path", ""),
                    "normalized_path": ref_meta.get("normalized_path", ""),
                    "frontend_mode": ref_meta.get("frontend_mode", ""),
                    "audio_frontend": ref_meta.get("audio_frontend", {}),
                }
            elif ref_audio_path:
                meta["voice_clone_ref_audio"] = {
                    "source": "uploaded_ref",
                    "path": str(ref_audio_path),
                    "duration_s": ref_meta.get("duration_s", 0.0),
                    "raw_path": ref_meta.get("raw_path", ""),
                    "normalized_path": ref_meta.get("normalized_path", ""),
                    "frontend_mode": ref_meta.get("frontend_mode", ""),
                    "audio_frontend": ref_meta.get("audio_frontend", {}),
                }
            result = engine.process_audio(
                wav_path,
                enable_punc=enable_punc,
                enable_rewrite=enable_rewrite,
                enable_tts=enable_tts,
                segment_max_len=segment_max_len,
                voice=voice,
                voice_clone_enabled=voice_clone_enabled,
                speaker_ref_audio=ref_audio_path,
                target_dialect=target_dialect,
                dialect_style=dialect_style,
            )
            result["source_audio"] = meta
            return PipelineResponse(**result)
        if text.strip():
            result = engine.process_text(
                text,
                enable_rewrite=enable_rewrite,
                enable_tts=enable_tts,
                segment_max_len=segment_max_len,
                voice=voice,
                input_lang=input_lang,
                voice_clone_enabled=voice_clone_enabled,
                speaker_ref_audio=ref_audio_path,
                target_dialect=target_dialect,
                dialect_style=dialect_style,
            )
            return PipelineResponse(**result)
        raise HTTPException(status_code=400, detail="Either file or text is required.")
    except AudioNormalizeError as e:
        raise HTTPException(status_code=400, detail=e.to_detail()) from e
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)) from e
