from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AsrServiceConfig:
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
        root = Path(__file__).resolve().parent.parent
        default_asr = root / "runtime_data" / "models" / "FireRedASR2-AED"
        default_punc = root / "runtime_data" / "models" / "FireRedPunc"
        default_vad = root / "runtime_data" / "models" / "FireRedVAD" / "VAD"
        default_lid = root / "runtime_data" / "models" / "FireRedLID"
        return cls(
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
