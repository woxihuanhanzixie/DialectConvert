from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable

import soundfile as sf

from .config import Step2Config


SUPPORTED_COSYVOICE_DIALECTS = {"yue", "sichuan", "minnan"}


def clean_realtime_speech_text(text: str) -> str:
    value = str(text or "").strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[ \t]*([，。！？；：,.!?;:])[ \t]*", r"\1", value)
    value = re.sub(r"([，。！？；：,.!?;:]){2,}", r"\1", value)
    return value.strip()


def cosyvoice_instruction(target_dialect: str) -> str:
    mapping = {
        "yue": "请使用自然广东话/粤语表达，保持原意。",
        "sichuan": "请使用自然四川话表达，保持原意。",
        "minnan": "请使用自然闽南语表达，保持原意。",
    }
    if target_dialect not in mapping:
        supported = ", ".join(sorted(mapping))
        raise ValueError(f"Unsupported CosyVoice dialect: {target_dialect}. Supported: {supported}.")
    return mapping[target_dialect]


def create_cosyvoice_voice(
    ref_audio_path: str | Path,
    public_ref_url: str,
    cfg: Step2Config,
    *,
    prefix: str = "demo",
) -> dict[str, Any]:
    if not cfg.qwen_tts_api_key:
        raise RuntimeError("Missing DASHSCOPE_API_KEY or QWEN_TTS_API_KEY for CosyVoice.")
    if not public_ref_url.startswith(("http://", "https://")):
        raise RuntimeError("CosyVoice voice enrollment requires a public HTTP(S) reference audio URL.")

    ref_path = Path(ref_audio_path)
    validation = validate_cosyvoice_reference_audio(ref_path, cfg)
    cached = _load_cosyvoice_cache(ref_path, public_ref_url, cfg, validation=validation)
    if cached:
        return {**cached, "cache_hit": True, "reference_audio_validation": validation}

    payload = {
        "model": cfg.cosyvoice_enrollment_model,
        "input": {
            "action": "create_voice",
            "target_model": cfg.cosyvoice_target_model,
            "prefix": _sanitize_prefix(prefix),
            "url": public_ref_url,
            "language_hints": ["zh"],
        },
    }
    raw = _post_json(
        f"{cfg.cosyvoice_base_url}{cfg.qwen_tts_customization_path}",
        payload,
        cfg.qwen_tts_api_key,
        cfg.timeout_s,
    )
    output = raw.get("output") or {}
    voice_id = str(output.get("voice_id") or output.get("voice") or "")
    if not voice_id:
        raise RuntimeError(f"Missing output.voice_id in CosyVoice response: {json.dumps(raw, ensure_ascii=False)[:500]}")

    result = {
        "voice_id": voice_id,
        "voice": voice_id,
        "raw": raw,
        "cache_hit": False,
        "target_model": cfg.cosyvoice_target_model,
        "enrollment_model": cfg.cosyvoice_enrollment_model,
        "reference_audio_validation": validation,
        "public_ref_url": public_ref_url,
    }
    _save_cosyvoice_cache(ref_path, public_ref_url, cfg, result, validation=validation)
    return result


def synthesize_cosyvoice_http(
    text: str,
    out_audio: Path,
    cfg: Step2Config,
    *,
    voice: str,
    target_dialect: str,
) -> dict[str, Any]:
    if not cfg.qwen_tts_api_key:
        return _error_result("Missing DASHSCOPE_API_KEY or QWEN_TTS_API_KEY for CosyVoice.", cfg, voice)

    cleaned = clean_realtime_speech_text(text)
    if not cleaned:
        return _error_result("Missing text for CosyVoice synthesis.", cfg, voice)

    instruction = cosyvoice_instruction(target_dialect)
    payload = {
        "model": cfg.cosyvoice_target_model,
        "input": {
            "text": cleaned,
            "voice": voice,
        },
        "parameters": {
            "format": cfg.cosyvoice_audio_format,
            "sample_rate": cfg.cosyvoice_sample_rate,
            "instruction": instruction,
        },
    }
    started_at = time.perf_counter()
    try:
        raw = _post_json(
            f"{cfg.cosyvoice_base_url}/services/aigc/multimodal-generation/generation",
            payload,
            cfg.qwen_tts_api_key,
            cfg.timeout_s,
        )
        audio_url = str((raw.get("output") or {}).get("audio", {}).get("url") or "")
        expires_at = str((raw.get("output") or {}).get("audio", {}).get("expires_at") or "")
        if not audio_url:
            return _error_result(f"Missing output.audio.url in CosyVoice response: {json.dumps(raw, ensure_ascii=False)[:500]}", cfg, voice)
        out_audio.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(audio_url, timeout=cfg.timeout_s) as resp:
            out_audio.write_bytes(resp.read())
        return {
            "ok": True,
            "wav_path": str(out_audio),
            "audio_url": audio_url,
            "expires_at": expires_at,
            "voice": voice,
            "voice_id": voice,
            "model": cfg.cosyvoice_target_model,
            "provider": "cosyvoice",
            "error": "",
            "fallback_reason": "",
            "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
            "tts_style_instructions": instruction,
            "instruction_mode_active": True,
        }
    except Exception as exc:  # noqa: BLE001
        return _error_result(str(exc), cfg, voice)


def stream_cosyvoice_websocket(
    *,
    text: str,
    cfg: Step2Config,
    voice: str,
    target_dialect: str,
    send_audio: Callable[[bytes], None],
    send_event: Callable[[dict[str, Any]], None],
) -> None:
    try:
        import websocket
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Missing websocket-client dependency for CosyVoice realtime synthesis.") from exc

    cleaned = clean_realtime_speech_text(text)
    if not cleaned:
        raise RuntimeError("Missing text for CosyVoice realtime synthesis.")
    instruction = cosyvoice_instruction(target_dialect)
    task_id = str(uuid.uuid4())
    headers = [
        f"Authorization: Bearer {cfg.qwen_tts_api_key}",
        "X-DashScope-DataInspection: enable",
    ]
    ws = websocket.create_connection(cfg.cosyvoice_ws_url, header=headers, timeout=max(10, cfg.timeout_s))
    try:
        run_task = {
            "header": {
                "action": "run-task",
                "task_id": task_id,
                "streaming": "duplex",
            },
            "payload": {
                "task_group": "audio",
                "task": "tts",
                "function": "SpeechSynthesizer",
                "model": cfg.cosyvoice_target_model,
                "parameters": {
                    "text_type": "PlainText",
                    "voice": voice,
                    "format": cfg.cosyvoice_audio_format,
                    "sample_rate": cfg.cosyvoice_sample_rate,
                    "volume": 50,
                    "rate": 1,
                    "pitch": 1,
                    "enable_ssml": False,
                    "instruction": instruction,
                },
                "input": {},
            },
        }
        ws.send(json.dumps(run_task, ensure_ascii=False))
        send_event({"type": "cosyvoice_started", "task_id": task_id, "model": cfg.cosyvoice_target_model})
        ws.send(json.dumps({"header": {"action": "continue-task", "task_id": task_id}, "payload": {"input": {"text": cleaned}}}, ensure_ascii=False))
        ws.send(json.dumps({"header": {"action": "finish-task", "task_id": task_id}, "payload": {"input": {}}}, ensure_ascii=False))

        while True:
            message = ws.recv()
            if isinstance(message, bytes):
                send_audio(message)
                continue
            if not message:
                break
            payload = _json_or_text(message)
            send_event({"type": "cosyvoice_event", "payload": payload})
            if _is_terminal_event(payload):
                break
    finally:
        ws.close()


def validate_cosyvoice_reference_audio(ref_audio_path: str | Path, cfg: Step2Config) -> dict[str, Any]:
    ref_path = Path(ref_audio_path)
    if not ref_path.exists() or not ref_path.is_file():
        raise RuntimeError(f"Missing reference audio: {ref_path}")
    if ref_path.suffix.lower() not in {".wav", ".mp3", ".m4a"}:
        raise RuntimeError("CosyVoice reference audio must be WAV, MP3, or M4A.")
    size_bytes = ref_path.stat().st_size
    if size_bytes <= 0:
        raise RuntimeError("Reference audio is empty.")
    if size_bytes > 10 * 1024 * 1024:
        raise RuntimeError("CosyVoice reference audio must be no larger than 10 MB.")
    try:
        info = sf.info(str(ref_path))
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Cannot inspect reference audio: {exc}") from exc
    duration_s = float(info.duration)
    if duration_s < cfg.speaker_ref_audio_min_s:
        raise RuntimeError(f"Reference audio is too short: {duration_s:.2f}s, minimum is {cfg.speaker_ref_audio_min_s:.2f}s.")
    if duration_s > 60:
        raise RuntimeError(f"Reference audio is too long: {duration_s:.2f}s, maximum is 60.00s.")
    if info.samplerate < 16000:
        raise RuntimeError(f"Reference audio sample rate is too low: {info.samplerate}Hz, minimum is 16000Hz.")
    return {
        "path": str(ref_path),
        "size_bytes": size_bytes,
        "duration_s": round(duration_s, 3),
        "sample_rate": info.samplerate,
        "channels": info.channels,
        "format": info.format,
        "subtype": info.subtype,
    }


def _post_json(url: str, payload: dict[str, Any], api_key: str, timeout_s: int) -> dict[str, Any]:
    req = urllib.request.Request(
        url=url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def _audio_cache_key(ref_audio_path: str | Path, public_ref_url: str, cfg: Step2Config) -> str:
    h = hashlib.sha256()
    h.update(Path(ref_audio_path).read_bytes())
    h.update(public_ref_url.encode("utf-8"))
    h.update(cfg.cosyvoice_target_model.encode("utf-8"))
    h.update(cfg.cosyvoice_base_url.encode("utf-8"))
    return h.hexdigest()


def _cache_path(ref_audio_path: str | Path, public_ref_url: str, cfg: Step2Config) -> Path:
    return cfg.cosyvoice_voice_cache_dir / f"{_audio_cache_key(ref_audio_path, public_ref_url, cfg)}.json"


def _load_cosyvoice_cache(ref_audio_path: str | Path, public_ref_url: str, cfg: Step2Config, *, validation: dict[str, Any]) -> dict[str, Any] | None:
    path = _cache_path(ref_audio_path, public_ref_url, cfg)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if payload.get("target_model") != cfg.cosyvoice_target_model:
        return None
    voice_id = str(payload.get("voice_id") or payload.get("voice") or "")
    if not voice_id:
        return None
    return {
        "voice_id": voice_id,
        "voice": voice_id,
        "target_model": payload.get("target_model", ""),
        "enrollment_model": payload.get("enrollment_model", ""),
        "created_at": payload.get("created_at", ""),
        "cache_path": str(path),
        "reference_audio_validation": validation,
        "public_ref_url": public_ref_url,
    }


def _save_cosyvoice_cache(ref_audio_path: str | Path, public_ref_url: str, cfg: Step2Config, result: dict[str, Any], *, validation: dict[str, Any]) -> None:
    voice_id = str(result.get("voice_id") or result.get("voice") or "")
    if not voice_id:
        return
    path = _cache_path(ref_audio_path, public_ref_url, cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "voice_id": voice_id,
        "voice": voice_id,
        "target_model": cfg.cosyvoice_target_model,
        "enrollment_model": cfg.cosyvoice_enrollment_model,
        "public_ref_url": public_ref_url,
        "reference_audio": validation,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _sanitize_prefix(prefix: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_]+", "", str(prefix or "demo")).strip("_")
    if not value:
        value = "demo"
    if not value[0].isalpha():
        value = f"demo{value}"
    return value[:12]


def _error_result(error: str, cfg: Step2Config, voice: str) -> dict[str, Any]:
    return {
        "ok": False,
        "wav_path": "",
        "audio_url": "",
        "expires_at": "",
        "voice": voice,
        "voice_id": voice,
        "model": cfg.cosyvoice_target_model,
        "provider": "cosyvoice",
        "error": error,
        "fallback_reason": "cosyvoice_failed",
        "latency_ms": 0.0,
    }


def _json_or_text(message: str) -> Any:
    try:
        return json.loads(message)
    except Exception:
        return message


def _is_terminal_event(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    header = payload.get("header") or {}
    event = str(header.get("event") or header.get("status") or "").lower()
    return event in {"task-finished", "task-failed", "task-canceled", "task-ended"}
