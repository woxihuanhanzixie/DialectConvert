from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_file() -> None:
    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent / ".env",
        here.parent.parent.parent / ".env",
    ]
    for path in candidates:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            text = line.strip()
            if not text or text.startswith("#") or "=" not in text:
                continue
            key, value = text.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


@dataclass
class AsrServiceConfig:
    provider: str
    cloud_provider: str
    cloud_model: str
    cloud_api_key: str
    cloud_workspace: str
    cloud_language_hints: str
    cloud_disfluency_removal: bool
    cloud_diarization: bool
    cloud_timestamp_alignment: bool
    model_dir: str
    punc_model_dir: str
    vad_model_dir: str
    lid_model_dir: str
    use_gpu: bool
    use_half: bool
    beam_size: int
    batch_size: int
    enable_punc_default: bool
    enable_vad_default: bool
    enable_lid_default: bool
    frontend_mode_default: str

    @classmethod
    def from_env(cls) -> "AsrServiceConfig":
        _load_env_file()
        root = Path(__file__).resolve().parent.parent
        default_asr = root / "runtime_data" / "models" / "FireRedASR2-AED"
        default_punc = root / "runtime_data" / "models" / "FireRedPunc"
        default_vad = root / "runtime_data" / "models" / "FireRedVAD" / "VAD"
        default_lid = root / "runtime_data" / "models" / "FireRedLID"
        return cls(
            provider=os.getenv("ASR_PROVIDER", "api_first").strip().lower(),
            cloud_provider=os.getenv("ASR_CLOUD_PROVIDER", "dashscope").strip().lower(),
            cloud_model=os.getenv("ASR_CLOUD_MODEL", "fun-asr-realtime-2026-02-28").strip(),
            cloud_api_key=os.getenv("ASR_CLOUD_API_KEY", os.getenv("DASHSCOPE_API_KEY", "")).strip(),
            cloud_workspace=os.getenv("DASHSCOPE_WORKSPACE", "").strip(),
            cloud_language_hints=os.getenv("ASR_CLOUD_LANGUAGE_HINTS", "zh").strip(),
            cloud_disfluency_removal=os.getenv("ASR_CLOUD_DISFLUENCY_REMOVAL", "0") == "1",
            cloud_diarization=os.getenv("ASR_CLOUD_DIARIZATION", "0") == "1",
            cloud_timestamp_alignment=os.getenv("ASR_CLOUD_TIMESTAMP_ALIGNMENT", "1") == "1",
            model_dir=os.getenv("ASR_MODEL_DIR", str(default_asr)),
            punc_model_dir=os.getenv("PUNC_MODEL_DIR", str(default_punc)),
            vad_model_dir=os.getenv("VAD_MODEL_DIR", str(default_vad)),
            lid_model_dir=os.getenv("LID_MODEL_DIR", str(default_lid)),
            use_gpu=os.getenv("ASR_USE_GPU", "0") == "1",
            use_half=os.getenv("ASR_USE_HALF", "0") == "1",
            beam_size=int(os.getenv("ASR_BEAM_SIZE", "3")),
            batch_size=int(os.getenv("ASR_BATCH_SIZE", "8")),
            enable_punc_default=os.getenv("ASR_ENABLE_PUNC", "1") == "1",
            enable_vad_default=os.getenv("ASR_ENABLE_VAD", "1") == "1",
            enable_lid_default=os.getenv("ASR_ENABLE_LID", "1") == "1",
            frontend_mode_default=os.getenv("AUDIO_FRONTEND_MODE", "light_asr_safe").strip(),
        )
