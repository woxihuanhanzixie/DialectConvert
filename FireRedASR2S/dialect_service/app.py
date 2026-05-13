from __future__ import annotations

import asyncio
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from asr_service.audio_io import AudioNormalizeError, get_runtime_capabilities, make_temp_dir, normalize_file_to_wav, normalize_upload_to_wav
from asr_service.cloud_asr import transcribe_api_first
from asr_service.config import AsrServiceConfig
from fireredasr2s.dialect_pipeline.cosyvoice import clean_realtime_speech_text, cosyvoice_instruction, create_cosyvoice_voice, stream_cosyvoice_websocket
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


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALLOWED_AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".webm", ".flac"}
REALTIME_SESSIONS: dict[str, dict[str, Any]] = {}


def _cors_allow_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if raw:
        return [item.strip() for item in raw.split(",") if item.strip()]
    public_origin = os.getenv("PUBLIC_APP_ORIGIN", "").strip()
    if public_origin:
        return [public_origin]
    return ["*"]


app = FastAPI(title="Demo1 Dialect Service", version="0.1.0")
_ALLOW_ORIGINS = _cors_allow_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOW_ORIGINS,
    allow_credentials=_ALLOW_ORIGINS != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _validate_dialect(target_dialect: str, dialect_style: str = "") -> str:
    if not is_supported_dialect(target_dialect):
        supported = ", ".join(supported_dialect_codes())
        raise HTTPException(status_code=400, detail=f"Unsupported dialect: {target_dialect}. Supported dialects: {supported}.")
    return normalize_dialect_style(target_dialect, dialect_style)


def _allowed_media_roots() -> list[Path]:
    engine = get_pipeline_engine()
    roots = [engine.cfg.output_dir.resolve()]
    preview_root = (PROJECT_ROOT / "runtime_data" / "web_demo_preview").resolve()
    if preview_root not in roots:
        roots.append(preview_root)
    return roots


def _is_relative_to(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _media_relative_path(file_path: str) -> str:
    if not file_path:
        return ""
    p = Path(file_path).resolve()
    for root in _allowed_media_roots():
        if _is_relative_to(p, root):
            return p.relative_to(root).as_posix()
    return ""


def _public_audio_url(request: Request, file_path: str) -> str:
    relative_path = _media_relative_path(file_path)
    if not relative_path:
        return ""
    return str(request.url_for("public_audio_file", relative_path=relative_path))


def _attach_public_audio_urls(result: dict, request: Request) -> dict:
    tts = result.get("tts") or {}
    if not isinstance(tts, dict):
        return result
    route_keys = ["baseline", "clone", "gold_teacher", "voice_matched", "cloned_dialect", "qwen_cloned_dialect", "cosyvoice_fallback", "legacy_text_clone"]
    for key in route_keys:
        route = tts.get(key)
        if isinstance(route, dict):
            public_url = _public_audio_url(request, route.get("wav_path", ""))
            if public_url:
                route["audio_url"] = public_url
    if isinstance(tts.get("gold_teacher"), dict):
        tts["baseline_audio_url"] = tts["gold_teacher"].get("audio_url", "")
    primary_route_key = tts.get("recommended_main_output") or "qwen_cloned_dialect"
    primary_route = tts.get(primary_route_key)
    if isinstance(primary_route, dict):
        tts["audio_url"] = primary_route.get("audio_url", "")
        tts["wav_path"] = primary_route.get("wav_path", tts.get("wav_path", ""))
    return result


def _copy_reference_audio_to_public_dir(ref_audio_path: str, trace_id: str) -> str:
    engine = get_pipeline_engine()
    src = Path(ref_audio_path)
    if not src.exists():
        return ""
    suffix = src.suffix.lower() or ".wav"
    engine.cfg.cosyvoice_ref_audio_dir.mkdir(parents=True, exist_ok=True)
    dst = engine.cfg.cosyvoice_ref_audio_dir / f"{trace_id}{suffix}"
    if src.resolve() != dst.resolve():
        shutil.copyfile(src, dst)
    return str(dst)


def _audio_media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".mp3":
        return "audio/mpeg"
    if suffix == ".m4a":
        return "audio/mp4"
    if suffix in {".ogg", ".opus"}:
        return "audio/ogg"
    if suffix == ".webm":
        return "audio/webm"
    if suffix == ".flac":
        return "audio/flac"
    return "audio/wav"


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    engine = get_pipeline_engine()
    return HealthResponse(
        status="ok",
        supported_dialects=supported_dialect_codes(),
        default_voice=engine.cfg.qwen_tts_voice,
        runtime={**engine.health(), **get_runtime_capabilities()},
    )


@app.get("/readyz", response_model=HealthResponse)
def readyz() -> HealthResponse:
    return healthz()


@app.get("/api/v1/files/audio/{relative_path:path}", name="public_audio_file")
def public_audio_file(relative_path: str) -> FileResponse:
    rel = Path(relative_path)
    if rel.is_absolute():
        raise HTTPException(status_code=400, detail="Absolute path is not allowed.")
    if rel.suffix.lower() not in ALLOWED_AUDIO_EXTS:
        raise HTTPException(status_code=400, detail="Unsupported audio extension.")
    for root in _allowed_media_roots():
        candidate = (root / rel).resolve()
        if not _is_relative_to(candidate, root):
            continue
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate, media_type=_audio_media_type(candidate), filename=candidate.name)
    raise HTTPException(status_code=404, detail="Audio file not found.")


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
def tts(req: TtsRequest, request: Request) -> TtsResponse:
    engine = get_pipeline_engine()
    dialect_style = _validate_dialect(req.target_dialect, req.dialect_style)
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
        target_dialect=req.target_dialect,
        dialect_style=dialect_style,
    )
    result = _attach_public_audio_urls({"tts": result["tts"]}, request)
    return TtsResponse(**result["tts"])


@app.post("/api/v1/dialect/realtime-session")
async def realtime_session(
    request: Request,
    file: UploadFile | None = File(default=None),
    speaker_ref_audio: UploadFile | None = File(default=None),
    text: str = Form(default=""),
    enable_punc: bool = Form(default=True),
    target_dialect: str = Form(default="yue"),
    dialect_style: str = Form(default=""),
    voice_clone_enabled: bool = Form(default=True),
) -> dict[str, Any]:
    engine = get_pipeline_engine()
    dialect_style = _validate_dialect(target_dialect, dialect_style)
    engine.cfg.default_target_dialect = target_dialect
    engine.cfg.default_dialect_style = dialect_style
    engine.cfg.voice_conversion_provider = "cosyvoice"
    engine.cfg.voice_clone_provider = "cosyvoice"
    trace_id = str(uuid.uuid4())
    ref_frontend_mode = "clone_ref_vad_concat" if engine.cfg.reference_audio_strategy == "vad_concat" else "clone_ref_safe"
    source_audio: dict[str, Any] | None = None
    asr_payload: dict[str, Any] | None = None
    try:
        speech_text = clean_realtime_speech_text(text)
        if file is not None and not speech_text:
            work_dir = make_temp_dir(prefix="demo1_realtime_")
            wav_path, source_audio = await normalize_upload_to_wav(file, work_dir)
            asr_cfg = AsrServiceConfig.from_env()
            asr_result, cloud_asr_error = transcribe_api_first(wav_path, asr_cfg, enable_punc=enable_punc, return_timestamp=True)
            if asr_result is None:
                raise RuntimeError(f"Cloud ASR failed before realtime synthesis: {cloud_asr_error}")
            asr_payload = asr_result
            speech_text = clean_realtime_speech_text(asr_result.get("punc_text") or asr_result.get("text") or "")
        if not speech_text:
            raise HTTPException(status_code=400, detail="Either text or an audio file with recognizable speech is required.")

        ref_audio_path = ""
        ref_public_url = ""
        voice_id = engine.cfg.cosyvoice_system_voice
        voice_cache_hit = False
        reference_audio_validation: dict[str, Any] = {}
        if speaker_ref_audio is not None and voice_clone_enabled:
            ref_dir = make_temp_dir(prefix="demo1_cosyvoice_ref_")
            normalized_ref_path, ref_meta = await normalize_upload_to_wav(speaker_ref_audio, ref_dir, frontend_mode=ref_frontend_mode)
            ref_audio_path = _copy_reference_audio_to_public_dir(str(normalized_ref_path), trace_id)
            ref_public_url = _public_audio_url(request, ref_audio_path)
            voice_info = await asyncio.to_thread(
                create_cosyvoice_voice,
                ref_audio_path,
                ref_public_url,
                engine.cfg,
                prefix="demo",
            )
            voice_id = str(voice_info.get("voice_id") or voice_info.get("voice") or voice_id)
            voice_cache_hit = bool(voice_info.get("cache_hit"))
            reference_audio_validation = voice_info.get("reference_audio_validation", {})
            reference_audio_validation.setdefault("frontend_mode", ref_meta.get("frontend_mode", ""))

        stream_id = str(uuid.uuid4())
        stream_url = str(request.url_for("cosyvoice_stream", stream_id=stream_id))
        if request.url.scheme == "http":
            stream_url = stream_url.replace("http://", "ws://", 1)
        elif request.url.scheme == "https":
            stream_url = stream_url.replace("https://", "wss://", 1)
        REALTIME_SESSIONS[stream_id] = {
            "trace_id": trace_id,
            "speech_text": speech_text,
            "target_dialect": target_dialect,
            "dialect_style": dialect_style,
            "voice_id": voice_id,
            "voice_cache_hit": voice_cache_hit,
            "reference_audio_validation": reference_audio_validation,
            "created_at": asyncio.get_running_loop().time(),
        }
        return {
            "stream_id": stream_id,
            "trace_id": trace_id,
            "speech_text": speech_text,
            "target_dialect": target_dialect,
            "dialect_style": dialect_style,
            "voice_id": voice_id,
            "voice_cache_hit": voice_cache_hit,
            "stream_url": stream_url,
            "model": engine.cfg.cosyvoice_target_model,
            "provider": "cosyvoice",
            "instruction": cosyvoice_instruction(target_dialect),
            "source_audio": source_audio,
            "asr": asr_payload,
            "reference_audio_validation": reference_audio_validation,
        }
    except AudioNormalizeError as exc:
        raise HTTPException(status_code=400, detail=exc.to_detail()) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.websocket("/api/v1/dialect/stream/{stream_id}", name="cosyvoice_stream")
async def cosyvoice_stream(websocket: WebSocket, stream_id: str) -> None:
    await websocket.accept()
    session = REALTIME_SESSIONS.get(stream_id)
    if not session:
        await websocket.send_text(json.dumps({"type": "error", "message": "Realtime session not found."}, ensure_ascii=False))
        await websocket.close()
        return

    engine = get_pipeline_engine()
    loop = asyncio.get_running_loop()

    def send_audio(data: bytes) -> None:
        asyncio.run_coroutine_threadsafe(websocket.send_bytes(data), loop).result()

    def send_event(event: dict[str, Any]) -> None:
        asyncio.run_coroutine_threadsafe(websocket.send_text(json.dumps(event, ensure_ascii=False)), loop).result()

    try:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "session",
                    "trace_id": session["trace_id"],
                    "model": engine.cfg.cosyvoice_target_model,
                    "voice_id": session["voice_id"],
                    "target_dialect": session["target_dialect"],
                    "format": engine.cfg.cosyvoice_audio_format,
                    "sample_rate": engine.cfg.cosyvoice_sample_rate,
                },
                ensure_ascii=False,
            )
        )
        await asyncio.to_thread(
            stream_cosyvoice_websocket,
            text=session["speech_text"],
            cfg=engine.cfg,
            voice=session["voice_id"],
            target_dialect=session["target_dialect"],
            send_audio=send_audio,
            send_event=send_event,
        )
        await websocket.send_text(json.dumps({"type": "done", "trace_id": session["trace_id"]}, ensure_ascii=False))
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False))
    finally:
        REALTIME_SESSIONS.pop(stream_id, None)
        try:
            await websocket.close()
        except Exception:
            pass


@app.post("/api/v1/dialect/pipeline", response_model=PipelineResponse)
async def pipeline(
    request: Request,
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
    voice_clone_enabled: bool = Form(default=True),
    voice_clone_provider: str = Form(default="cosyvoice"),
) -> PipelineResponse:
    engine = get_pipeline_engine()
    dialect_style = _validate_dialect(target_dialect, dialect_style)
    engine.cfg.default_target_dialect = target_dialect
    engine.cfg.default_dialect_style = dialect_style
    engine.cfg.voice_conversion_provider = voice_clone_provider or "cosyvoice"
    engine.cfg.voice_clone_provider = "cosyvoice" if engine.cfg.voice_conversion_provider == "cosyvoice" else (engine.cfg.text_clone_provider or "qwen_vc")
    ref_frontend_mode = "clone_ref_vad_concat" if engine.cfg.reference_audio_strategy == "vad_concat" else "clone_ref_safe"
    try:
        ref_audio_path = ""
        ref_audio_url = ""
        if speaker_ref_audio is not None:
            ref_dir = make_temp_dir(prefix="demo1_ref_audio_")
            ref_audio_path, ref_meta = await normalize_upload_to_wav(speaker_ref_audio, ref_dir, frontend_mode=ref_frontend_mode)
            if engine.cfg.voice_conversion_provider == "cosyvoice":
                ref_audio_path = _copy_reference_audio_to_public_dir(str(ref_audio_path), uuid.uuid4().hex)
                ref_audio_url = _public_audio_url(request, ref_audio_path)
        if file is not None:
            work_dir = make_temp_dir(prefix="demo1_pipeline_")
            wav_path, meta = await normalize_upload_to_wav(file, work_dir)
            if voice_clone_enabled and not ref_audio_path:
                ref_dir = make_temp_dir(prefix="demo1_ref_audio_auto_")
                ref_source = meta.get("original_path") or meta.get("raw_path") or str(wav_path)
                ref_audio_path, ref_meta = normalize_file_to_wav(ref_source, ref_dir, frontend_mode=ref_frontend_mode)
                if engine.cfg.voice_conversion_provider == "cosyvoice":
                    ref_audio_path = _copy_reference_audio_to_public_dir(str(ref_audio_path), uuid.uuid4().hex)
                    ref_audio_url = _public_audio_url(request, ref_audio_path)
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
                speaker_ref_audio_url=ref_audio_url,
                target_dialect=target_dialect,
                dialect_style=dialect_style,
            )
            result["source_audio"] = meta
            result = _attach_public_audio_urls(result, request)
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
                speaker_ref_audio_url=ref_audio_url,
                target_dialect=target_dialect,
                dialect_style=dialect_style,
            )
            result = _attach_public_audio_urls(result, request)
            return PipelineResponse(**result)
        raise HTTPException(status_code=400, detail="Either file or text is required.")
    except AudioNormalizeError as e:
        raise HTTPException(status_code=400, detail=e.to_detail()) from e
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)) from e
