from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


ROOT_DIR = Path(__file__).resolve().parents[1]


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _int_env(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _runtime_path_env(name: str, default: Path) -> Path:
    raw = _env(name)
    if not raw:
        return default
    path = Path(raw)
    # The archived project often carried absolute paths from the previous
    # workspace. Keep Linux deployment overrides, but avoid resurrecting that
    # stale Windows runtime directory during the rebuild.
    if "FireRedASR2S" in str(path) and "dialect convert" not in str(path):
        return default
    return path


@dataclass(frozen=True)
class Settings:
    app_name: str = "声临其境"
    host: str = _env("DIALECT_SERVICE_HOST", "0.0.0.0")
    port: int = _int_env("DIALECT_SERVICE_PORT", 7860)
    public_base_url: str = _env("PUBLIC_BASE_URL") or _env("PUBLIC_APP_ORIGIN")
    cors_origins: str = _env("CORS_ALLOW_ORIGINS", "*")

    dashscope_api_key: str = _env("DASHSCOPE_API_KEY") or _env("QWEN_TTS_API_KEY")
    qwen_llm_api_key: str = _env("QWEN_LLM_API_KEY") or _env("DASHSCOPE_API_KEY") or _env("DEEPSEEK_API_KEY")
    qwen_llm_base_url: str = _env("QWEN_LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    qwen_llm_model: str = _env("QWEN_LLM_MODEL", "qwen3-max")

    asr_provider: str = _env("ASR_PROVIDER", "dashscope_paraformer")
    asr_model: str = _env("ASR_MODEL", "paraformer-v2")
    asr_base_url: str = _env("ASR_BASE_URL", "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription")

    tts_provider: str = _env("TTS_PROVIDER", "dashscope_cosyvoice")
    qwen_tts_base_url: str = _env("QWEN_TTS_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    # Gold Teacher TTS: cosyvoice-v3-plus retains system-voice support ("longanyang")
    # plus instruction-based dialect / emotion control.
    qwen_tts_model: str = _env("QWEN_TTS_MODEL", "cosyvoice-v3-plus")
    qwen_tts_voice: str = _env("QWEN_TTS_VOICE", "longanyang")

    voice_match_provider: str = _env("VOICE_MATCH_PROVIDER", "cosyvoice_clone")
    qwen_voice_enrollment_model: str = _env("QWEN_VOICE_ENROLLMENT_MODEL", "voice-enrollment")
    # Voice Matched TTS: cosyvoice-v3.5-plus is the strongest voice-cloning model
    # (Beijing region only; does NOT ship system voices — use cloned voice_id only).
    qwen_voice_target_model: str = _env("QWEN_VOICE_TARGET_MODEL", "cosyvoice-v3.5-plus")
    qwen_voice_enrollment_url: str = _env(
        "QWEN_VOICE_ENROLLMENT_URL",
        "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization",
    )
    qwen_tts_vc_model: str = _env("QWEN_TTS_VC_MODEL", "cosyvoice-v3-flash")
    dashscope_task_url: str = _env("DASHSCOPE_TASK_URL", "https://dashscope.aliyuncs.com/api/v1/tasks")

    data_dir: Path = ROOT_DIR / "runtime_data"
    upload_dir: Path = data_dir / "uploads"
    output_dir: Path = data_dir / "outputs"
    metadata_dir: Path = data_dir / "jobs"
    cache_dir: Path = _runtime_path_env("QWEN_VOICE_CACHE_DIR", data_dir / "voice_cache")
    max_upload_mb: int = _int_env("MAX_UPLOAD_MB", 30)
    cleanup_after_hours: int = _int_env("CLEANUP_AFTER_HOURS", 24)
    voice_cache_ttl_hours: int = _int_env("VOICE_CACHE_TTL_HOURS", 720)
    request_timeout_s: int = _int_env("API_REQUEST_TIMEOUT_S", 90)
    max_retries: int = _int_env("API_MAX_RETRIES", 3)

    ref_audio_min_s: int = _int_env("SPEAKER_REF_AUDIO_MIN_S", 10)
    ref_audio_max_s: int = _int_env("SPEAKER_REF_AUDIO_MAX_S", 20)

    enable_mock_when_no_key: bool = _env("ENABLE_MOCK_WHEN_NO_KEY", "0") == "1"


settings = Settings()
