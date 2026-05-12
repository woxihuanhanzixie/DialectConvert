from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import re

import soundfile as sf

from .config import Step2Config


def create_qwen_voice(ref_audio_path: str | Path, cfg: Step2Config, preferred_name: str) -> dict[str, Any]:
    validation = _validate_reference_audio(ref_audio_path, cfg)
    cached = _load_qwen_voice_cache(ref_audio_path, cfg, validation=validation)
    if cached:
        return {**cached, "raw": cached.get("raw", {}), "cache_hit": True, "reference_audio_validation": validation}

    ref_path = Path(ref_audio_path)
    mime_type = mimetypes.guess_type(ref_path.name)[0] or "audio/wav"
    data_uri = f"data:{mime_type};base64,{base64.b64encode(ref_path.read_bytes()).decode()}"
    payload = {
        "model": cfg.qwen_voice_enrollment_model,
        "input": {
            "action": "create",
            "target_model": cfg.qwen_voice_target_model,
            "preferred_name": _sanitize_preferred_name(preferred_name),
            "audio": {"data": data_uri},
        },
    }
    raw = _post_json(f"{cfg.qwen_tts_base_url}{cfg.qwen_tts_customization_path}", payload, cfg.qwen_tts_api_key, cfg.timeout_s)
    voice = raw.get("output", {}).get("voice", "")
    if not voice:
        raise RuntimeError(f"Missing output.voice in qwen voice enrollment response: {json.dumps(raw, ensure_ascii=False)[:500]}")
    result = {
        "voice": voice,
        "raw": raw,
        "cache_hit": False,
        "target_model": cfg.qwen_voice_target_model,
        "enrollment_model": cfg.qwen_voice_enrollment_model,
        "reference_audio_validation": validation,
    }
    _save_qwen_voice_cache(ref_audio_path, cfg, result, validation=validation)
    return result


def synthesize_qwen_vc(text: str, voice: str, out_wav: Path, cfg: Step2Config) -> dict[str, Any]:
    payload = {
        "model": cfg.qwen_voice_target_model,
        "input": {
            "text": text,
            "voice": voice,
        },
    }
    raw = _post_json(f"{cfg.qwen_tts_base_url}{cfg.qwen_tts_path}", payload, cfg.qwen_tts_api_key, cfg.timeout_s)
    audio_url = raw.get("output", {}).get("audio", {}).get("url", "")
    expires_at = str(raw.get("output", {}).get("audio", {}).get("expires_at", "") or "")
    if not audio_url:
        raise RuntimeError(f"Missing output.audio.url in qwen vc response: {json.dumps(raw, ensure_ascii=False)[:500]}")
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(str(audio_url), timeout=cfg.timeout_s) as resp:
        out_wav.write_bytes(resp.read())
    return {
        "wav_path": str(out_wav),
        "audio_url": audio_url,
        "expires_at": expires_at,
        "voice": voice,
        "model": cfg.qwen_voice_target_model,
    }


def synthesize_local_clone(*args, **kwargs) -> dict[str, Any]:
    raise NotImplementedError("Local voice clone provider is reserved but not implemented yet.")


def convert_voice_from_teacher(
    teacher_wav_path: str | Path,
    ref_audio_path: str | Path,
    out_wav: Path,
    cfg: Step2Config,
    *,
    preferred_name: str,
    input_text: str = "",
) -> dict[str, Any]:
    provider = (cfg.voice_conversion_provider or "none").strip().lower()
    teacher_path = Path(teacher_wav_path)
    ref_path = Path(ref_audio_path)
    if provider in {"qwen_voice_clone", "qwen_vc", "qwen"}:
        return {
            "ok": False,
            "wav_path": "",
            "provider": "qwen_voice_clone",
            "error": "Qwen voice clone is text-to-speech cloning, not teacher audio-to-audio conversion.",
            "fallback_reason": "qwen_text_clone_not_teacher_audio_to_audio",
            "teacher_wav_path": str(teacher_path),
            "reference_wav_path": str(ref_path),
            "model": cfg.qwen_voice_target_model,
        }
    if not teacher_path.exists():
        return {
            "ok": False,
            "wav_path": "",
            "provider": provider,
            "error": f"Missing teacher wav: {teacher_path}",
            "fallback_reason": "missing_teacher_wav",
            "teacher_wav_path": str(teacher_path),
            "reference_wav_path": str(ref_path),
        }
    if not ref_path.exists():
        return {
            "ok": False,
            "wav_path": "",
            "provider": provider,
            "error": f"Missing reference audio: {ref_path}",
            "fallback_reason": "missing_reference_audio",
            "teacher_wav_path": str(teacher_path),
            "reference_wav_path": str(ref_path),
        }
    if provider in {"", "none"}:
        return {
            "ok": False,
            "wav_path": "",
            "provider": provider or "none",
            "error": "VOICE_CONVERSION_PROVIDER is not configured",
            "fallback_reason": "voice_conversion_not_configured",
            "teacher_wav_path": str(teacher_path),
            "reference_wav_path": str(ref_path),
        }
    if provider == "openvoice":
        return _convert_with_openvoice_subprocess(
            teacher_path,
            ref_path,
            out_wav,
            cfg,
            preferred_name=preferred_name,
        )
    if provider == "rvc":
        return _convert_with_rvc_subprocess(
            teacher_path,
            ref_path,
            out_wav,
            cfg,
        )
    if provider in {"gpt_sovits", "fish_speech"}:
        return {
            "ok": False,
            "wav_path": "",
            "provider": provider,
            "error": (
                f"Voice conversion provider '{provider}' is planned but not implemented yet. "
                "Expected mode: teacher_audio_to_audio."
            ),
            "fallback_reason": "voice_conversion_provider_not_implemented",
            "teacher_wav_path": str(teacher_path),
            "reference_wav_path": str(ref_path),
            "model": cfg.voice_conversion_model,
            "device": cfg.voice_conversion_device,
            "preferred_name": preferred_name,
        }
    return {
        "ok": False,
        "wav_path": "",
        "provider": provider,
        "error": f"Unsupported voice conversion provider: {provider}",
        "fallback_reason": "unsupported_voice_conversion_provider",
        "teacher_wav_path": str(teacher_path),
        "reference_wav_path": str(ref_path),
    }


def _convert_with_openvoice_subprocess(
    teacher_path: Path,
    ref_path: Path,
    out_wav: Path,
    cfg: Step2Config,
    *,
    preferred_name: str,
) -> dict[str, Any]:
    workspace_root = _workspace_root()
    openvoice_runtime_dir = workspace_root / "OpenVoiceRuntime"
    script_path = openvoice_runtime_dir / "run_openvoice_convert.py"
    openvoice_repo = _project_root() / "runtime_data" / "models" / "OpenVoice"
    converter_dir = Path(cfg.voice_conversion_model).expanduser() if cfg.voice_conversion_model else (openvoice_repo / "checkpoints_v2" / "converter")
    cache_dir = openvoice_runtime_dir / "cache" / "se"
    python_exe, python_source, python_warning = _resolve_openvoice_python()
    if not script_path.exists():
        return {
            "ok": False,
            "wav_path": "",
            "provider": "openvoice",
            "error": f"Missing OpenVoice runtime script: {script_path}",
            "fallback_reason": "missing_openvoice_runtime_script",
            "teacher_wav_path": str(teacher_path),
            "reference_wav_path": str(ref_path),
        }
    if not openvoice_repo.exists():
        return {
            "ok": False,
            "wav_path": "",
            "provider": "openvoice",
            "error": f"Missing OpenVoice repository: {openvoice_repo}",
            "fallback_reason": "missing_openvoice_repo",
            "teacher_wav_path": str(teacher_path),
            "reference_wav_path": str(ref_path),
        }
    if not Path(python_exe).exists():
        return {
            "ok": False,
            "wav_path": "",
            "provider": "openvoice",
            "error": f"OpenVoice python executable does not exist: {python_exe}",
            "fallback_reason": "missing_openvoice_python",
            "teacher_wav_path": str(teacher_path),
            "reference_wav_path": str(ref_path),
            "python_exe": python_exe,
            "python_source": python_source,
            "python_warning": python_warning,
        }
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    command = [
        python_exe,
        str(script_path),
        "--teacher-wav",
        str(teacher_path),
        "--ref-audio",
        str(ref_path),
        "--out-wav",
        str(out_wav),
        "--openvoice-repo",
        str(openvoice_repo),
        "--converter-dir",
        str(converter_dir),
        "--cache-dir",
        str(cache_dir),
        "--device",
        cfg.voice_conversion_device or "auto",
        "--message",
        _sanitize_preferred_name(preferred_name),
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    started_at = time.perf_counter()
    try:
        proc = subprocess.run(
            command,
            cwd=str(workspace_root),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=max(300, cfg.timeout_s * 6),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "wav_path": "",
            "provider": "openvoice",
            "error": "OpenVoice conversion timed out",
            "fallback_reason": "openvoice_timeout",
            "teacher_wav_path": str(teacher_path),
            "reference_wav_path": str(ref_path),
            "model": str(converter_dir),
            "device": cfg.voice_conversion_device or "auto",
            "python_exe": python_exe,
            "python_source": python_source,
            "python_warning": python_warning,
        }
    except OSError as exc:
        return {
            "ok": False,
            "wav_path": "",
            "provider": "openvoice",
            "error": f"Failed to launch OpenVoice subprocess: {exc}",
            "fallback_reason": "openvoice_subprocess_launch_failed",
            "teacher_wav_path": str(teacher_path),
            "reference_wav_path": str(ref_path),
            "model": str(converter_dir),
            "device": cfg.voice_conversion_device or "auto",
            "python_exe": python_exe,
            "python_source": python_source,
            "python_warning": python_warning,
        }

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    payload: dict[str, Any] = {}
    if stdout:
        payload = _extract_json_from_output(stdout)
    if proc.returncode != 0 or not payload.get("ok"):
        error_text = payload.get("error") or stderr or stdout or f"OpenVoice process failed with code {proc.returncode}"
        return {
            "ok": False,
            "wav_path": "",
            "provider": "openvoice",
            "error": error_text,
            "fallback_reason": "openvoice_process_failed",
            "teacher_wav_path": str(teacher_path),
            "reference_wav_path": str(ref_path),
            "model": str(converter_dir),
            "device": payload.get("device") or (cfg.voice_conversion_device or "auto"),
            "stderr": stderr[:1000],
            "python_exe": python_exe,
            "python_source": python_source,
            "python_warning": python_warning,
        }

    return {
        "ok": True,
        "wav_path": payload.get("wav_path", str(out_wav)),
        "provider": "openvoice",
        "audio_url": "",
        "expires_at": "",
        "error": "",
        "fallback_reason": "",
        "teacher_wav_path": str(teacher_path),
        "reference_wav_path": str(ref_path),
        "model": str(converter_dir),
        "device": payload.get("device") or (cfg.voice_conversion_device or "auto"),
        "source_embedding_cache": payload.get("source_embedding_cache", ""),
        "target_embedding_cache": payload.get("target_embedding_cache", ""),
        "openvoice_latency_ms": payload.get("latency_ms", round((time.perf_counter() - started_at) * 1000, 2)),
        "audio_bytes": payload.get("audio_bytes", 0),
        "python_exe": python_exe,
        "python_source": python_source,
        "python_warning": python_warning,
    }


def _convert_with_qwen_voice_clone(
    input_text: str,
    ref_path: Path,
    out_wav: Path,
    cfg: Step2Config,
    *,
    preferred_name: str,
    teacher_path: Path,
) -> dict[str, Any]:
    if not cfg.qwen_tts_api_key:
        return {
            "ok": False,
            "wav_path": "",
            "provider": "qwen_voice_clone",
            "error": "Missing QWEN_TTS_API_KEY or DASHSCOPE_API_KEY",
            "fallback_reason": "missing_qwen_tts_api_key",
            "teacher_wav_path": str(teacher_path),
            "reference_wav_path": str(ref_path),
            "model": cfg.qwen_voice_target_model,
        }
    if not ref_path.exists():
        return {
            "ok": False,
            "wav_path": "",
            "provider": "qwen_voice_clone",
            "error": f"Missing reference audio: {ref_path}",
            "fallback_reason": "missing_reference_audio",
            "teacher_wav_path": str(teacher_path),
            "reference_wav_path": str(ref_path),
            "model": cfg.qwen_voice_target_model,
        }
    try:
        voice_info = create_qwen_voice(ref_path, cfg, preferred_name=preferred_name)
        result = synthesize_qwen_vc(input_text, voice_info["voice"], out_wav, cfg)
        return {
            "ok": True,
            "wav_path": result.get("wav_path", str(out_wav)),
            "provider": "qwen_voice_clone",
            "audio_url": result.get("audio_url", ""),
            "expires_at": result.get("expires_at", ""),
            "error": "",
            "fallback_reason": "",
            "teacher_wav_path": str(teacher_path),
            "reference_wav_path": str(ref_path),
            "model": cfg.qwen_voice_target_model,
            "voice": result.get("voice") or voice_info.get("voice", ""),
            "target_model": cfg.qwen_voice_target_model,
            "enrollment_model": cfg.qwen_voice_enrollment_model,
            "voice_cache_hit": bool(voice_info.get("cache_hit")),
            "reference_audio_validation": voice_info.get("reference_audio_validation", {}),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "wav_path": "",
            "provider": "qwen_voice_clone",
            "error": str(exc),
            "fallback_reason": "qwen_voice_clone_failed",
            "teacher_wav_path": str(teacher_path),
            "reference_wav_path": str(ref_path),
            "model": cfg.qwen_voice_target_model,
            "target_model": cfg.qwen_voice_target_model,
            "enrollment_model": cfg.qwen_voice_enrollment_model,
        }


def _convert_with_rvc_subprocess(
    teacher_path: Path,
    ref_path: Path,
    out_wav: Path,
    cfg: Step2Config,
) -> dict[str, Any]:
    # RVC uses trained speaker model/index; reference wav is kept for route compatibility.
    _ = ref_path
    script_path = _project_root() / "runtime" / "rvc" / "run_rvc_convert.py"
    configured_model = cfg.voice_conversion_model or os.getenv("RVC_MODEL_PATH", "")
    model_path = Path(configured_model).expanduser() if configured_model else Path()
    index_path_str = os.getenv("RVC_INDEX_PATH", "").strip()
    index_path = Path(index_path_str).expanduser() if index_path_str else Path()
    f0_method = os.getenv("RVC_F0_METHOD", "harvest").strip() or "harvest"
    f0_up_key = int(os.getenv("RVC_F0_UP_KEY", "0") or "0")
    index_rate = float(os.getenv("RVC_INDEX_RATE", "0.5") or "0.5")
    rms_mix_rate = float(os.getenv("RVC_RMS_MIX_RATE", "0.25") or "0.25")
    protect = float(os.getenv("RVC_PROTECT", "0.33") or "0.33")
    filter_radius = int(os.getenv("RVC_FILTER_RADIUS", "3") or "3")
    version = os.getenv("RVC_VERSION", "v2").strip() or "v2"
    if not script_path.exists():
        return {
            "ok": False,
            "wav_path": "",
            "provider": "rvc",
            "error": f"Missing RVC runtime script: {script_path}",
            "fallback_reason": "missing_rvc_runtime_script",
            "teacher_wav_path": str(teacher_path),
            "reference_wav_path": str(ref_path),
        }
    if not model_path.exists():
        return {
            "ok": False,
            "wav_path": "",
            "provider": "rvc",
            "error": (
                "RVC model is not configured. Set VOICE_CONVERSION_MODEL or RVC_MODEL_PATH "
                "to a valid .pth model file path."
            ),
            "fallback_reason": "missing_rvc_model",
            "teacher_wav_path": str(teacher_path),
            "reference_wav_path": str(ref_path),
            "model": str(model_path) if configured_model else "",
            "device": cfg.voice_conversion_device or "auto",
        }

    rvc_python = os.getenv("RVC_PYTHON", "").strip() or os.getenv("OPENVOICE_PYTHON", "").strip() or sys.executable
    if not Path(rvc_python).expanduser().exists():
        return {
            "ok": False,
            "wav_path": "",
            "provider": "rvc",
            "error": f"RVC python executable does not exist: {rvc_python}",
            "fallback_reason": "missing_rvc_python",
            "teacher_wav_path": str(teacher_path),
            "reference_wav_path": str(ref_path),
            "model": str(model_path),
            "device": cfg.voice_conversion_device or "auto",
        }

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(Path(rvc_python).expanduser()),
        str(script_path),
        "--teacher-wav",
        str(teacher_path),
        "--out-wav",
        str(out_wav),
        "--model-path",
        str(model_path),
        "--device",
        cfg.voice_conversion_device or "auto",
        "--f0-method",
        f0_method,
        "--f0-up-key",
        str(f0_up_key),
        "--index-rate",
        str(index_rate),
        "--rms-mix-rate",
        str(rms_mix_rate),
        "--protect",
        str(protect),
        "--filter-radius",
        str(filter_radius),
        "--version",
        version,
    ]
    if index_path.exists():
        command.extend(["--index-path", str(index_path)])

    started_at = time.perf_counter()
    try:
        proc = subprocess.run(
            command,
            cwd=str(_project_root()),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=max(300, cfg.timeout_s * 6),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "wav_path": "",
            "provider": "rvc",
            "error": "RVC conversion timed out",
            "fallback_reason": "rvc_timeout",
            "teacher_wav_path": str(teacher_path),
            "reference_wav_path": str(ref_path),
            "model": str(model_path),
            "device": cfg.voice_conversion_device or "auto",
        }
    except OSError as exc:
        return {
            "ok": False,
            "wav_path": "",
            "provider": "rvc",
            "error": f"Failed to launch RVC subprocess: {exc}",
            "fallback_reason": "rvc_subprocess_launch_failed",
            "teacher_wav_path": str(teacher_path),
            "reference_wav_path": str(ref_path),
            "model": str(model_path),
            "device": cfg.voice_conversion_device or "auto",
        }

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    payload: dict[str, Any] = {}
    if stdout:
        payload = _extract_json_from_output(stdout)
    if proc.returncode != 0 or not payload.get("ok"):
        error_text = payload.get("error") or stderr or stdout or f"RVC process failed with code {proc.returncode}"
        return {
            "ok": False,
            "wav_path": "",
            "provider": "rvc",
            "error": error_text,
            "fallback_reason": "rvc_process_failed",
            "teacher_wav_path": str(teacher_path),
            "reference_wav_path": str(ref_path),
            "model": str(model_path),
            "index_path": str(index_path) if index_path.exists() else "",
            "device": payload.get("device") or (cfg.voice_conversion_device or "auto"),
            "stderr": stderr[:1000],
        }

    return {
        "ok": True,
        "wav_path": payload.get("wav_path", str(out_wav)),
        "provider": "rvc",
        "audio_url": "",
        "expires_at": "",
        "error": "",
        "fallback_reason": "",
        "teacher_wav_path": str(teacher_path),
        "reference_wav_path": str(ref_path),
        "model": str(model_path),
        "index_path": str(index_path) if index_path.exists() else "",
        "device": payload.get("device") or (cfg.voice_conversion_device or "auto"),
        "rvc_latency_ms": payload.get("latency_ms", round((time.perf_counter() - started_at) * 1000, 2)),
        "audio_bytes": payload.get("audio_bytes", 0),
    }


def _post_json(url: str, payload: dict[str, Any], api_key: str, timeout_s: int) -> dict[str, Any]:
    req = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {e.code}: {body}") from e


def _validate_reference_audio(ref_audio_path: str | Path, cfg: Step2Config) -> dict[str, Any]:
    ref_path = Path(ref_audio_path)
    if not ref_path.exists():
        raise RuntimeError(f"Missing reference audio: {ref_path}")
    if not ref_path.is_file():
        raise RuntimeError(f"Reference audio is not a file: {ref_path}")

    suffix = ref_path.suffix.lower()
    allowed_exts = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".webm", ".flac"}
    if suffix not in allowed_exts:
        raise RuntimeError(f"Unsupported reference audio extension: {suffix or '(none)'}")

    size_bytes = ref_path.stat().st_size
    if size_bytes <= 0:
        raise RuntimeError("Reference audio is empty.")

    try:
        info = sf.info(str(ref_path))
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Cannot inspect reference audio: {exc}") from exc

    duration_s = float(info.duration)
    if duration_s < cfg.speaker_ref_audio_min_s:
        raise RuntimeError(
            f"Reference audio is too short: {duration_s:.2f}s, "
            f"minimum is {cfg.speaker_ref_audio_min_s:.2f}s."
        )
    if duration_s > cfg.speaker_ref_audio_max_s:
        raise RuntimeError(
            f"Reference audio is too long: {duration_s:.2f}s, "
            f"maximum is {cfg.speaker_ref_audio_max_s:.2f}s."
        )

    return {
        "path": str(ref_path),
        "size_bytes": size_bytes,
        "duration_s": round(duration_s, 3),
        "sample_rate": info.samplerate,
        "channels": info.channels,
        "format": info.format,
        "subtype": info.subtype,
    }


def _audio_cache_key(ref_audio_path: str | Path, cfg: Step2Config) -> str:
    ref_path = Path(ref_audio_path)
    h = hashlib.sha256()
    h.update(ref_path.read_bytes())
    h.update(cfg.qwen_voice_target_model.encode("utf-8"))
    h.update(cfg.qwen_voice_enrollment_model.encode("utf-8"))
    return h.hexdigest()


def _voice_cache_path(ref_audio_path: str | Path, cfg: Step2Config) -> Path:
    return cfg.qwen_voice_cache_dir / f"{_audio_cache_key(ref_audio_path, cfg)}.json"


def _load_qwen_voice_cache(ref_audio_path: str | Path, cfg: Step2Config, *, validation: dict[str, Any]) -> dict[str, Any] | None:
    cache_path = _voice_cache_path(ref_audio_path, cfg)
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if payload.get("target_model") != cfg.qwen_voice_target_model:
        return None
    if payload.get("enrollment_model") != cfg.qwen_voice_enrollment_model:
        return None
    voice = str(payload.get("voice") or "")
    if not voice:
        return None
    return {
        "voice": voice,
        "target_model": payload.get("target_model", ""),
        "enrollment_model": payload.get("enrollment_model", ""),
        "created_at": payload.get("created_at", ""),
        "cache_path": str(cache_path),
        "reference_audio_validation": validation,
    }


def _save_qwen_voice_cache(
    ref_audio_path: str | Path,
    cfg: Step2Config,
    result: dict[str, Any],
    *,
    validation: dict[str, Any],
) -> None:
    voice = str(result.get("voice") or "")
    if not voice:
        return
    cache_path = _voice_cache_path(ref_audio_path, cfg)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "voice": voice,
        "target_model": cfg.qwen_voice_target_model,
        "enrollment_model": cfg.qwen_voice_enrollment_model,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reference_audio_sha256": _audio_cache_key(ref_audio_path, cfg),
        "reference_audio": validation,
        "status": "active",
    }
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _sanitize_preferred_name(name: str) -> str:
    value = name.strip().lower()
    value = re.sub(r"[^a-z0-9_]+", "_", value)
    value = re.sub(r"_{2,}", "_", value).strip("_")
    if not value:
        value = "demo1voice"
    if not re.match(r"^[a-z]", value):
        value = f"demo1voice_{value}"
    if len(value) < 3:
        value = f"{value}_vc"
    return value[:32]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_openvoice_python() -> tuple[str, str, str]:
    configured = os.getenv("OPENVOICE_PYTHON", "").strip()
    if configured:
        configured_path = Path(configured).expanduser()
        if configured_path.exists():
            return str(configured_path), "OPENVOICE_PYTHON", ""
        return (
            sys.executable,
            "sys.executable",
            f"OPENVOICE_PYTHON points to a missing path, fallback to current interpreter: {configured_path}",
        )
    return sys.executable, "sys.executable", ""


def _extract_json_from_output(output: str) -> dict[str, Any]:
    text = output.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.rfind("{")
    while start >= 0:
        candidate = text[start:]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            start = text.rfind("{", 0, start)
    return {"ok": False, "error": text}
