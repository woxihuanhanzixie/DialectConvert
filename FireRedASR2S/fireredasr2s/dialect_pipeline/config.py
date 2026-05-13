from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_file() -> None:
    # Load .env from project root or workspace root, without overriding existing env vars.
    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent.parent / ".env",  # .../fireredasr2s/.env
        here.parent.parent.parent.parent / ".env",  # .../大赛/.env
    ]
    for p in candidates:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            key = k.strip()
            val = v.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def _voice_match_provider_from_env() -> str:
    provider = os.getenv("VOICE_MATCH_PROVIDER", os.getenv("VOICE_CONVERSION_PROVIDER", "none")).strip().lower()
    if provider in {"qwen_voice_clone", "qwen_vc", "qwen"}:
        return os.getenv("TEACHER_FIRST_VOICE_MATCH_PROVIDER", "none").strip().lower()
    return provider or "none"


@dataclass
class Step2Config:
    provider: str
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    qwen_api_key: str
    qwen_base_url: str
    qwen_model: str
    qwen_tts_api_key: str
    qwen_tts_base_url: str
    qwen_tts_model: str
    qwen_tts_voice: str
    qwen_tts_format: str
    qwen_tts_path: str
    qwen_tts_language_type: str
    qwen_tts_instruction_model: str
    qwen_tts_teacher_voice: str
    qwen_tts_teacher_instructions: str
    voice_clone_provider: str
    text_clone_provider: str
    voice_conversion_provider: str
    qwen_voice_enrollment_model: str
    qwen_voice_target_model: str
    voice_conversion_mode: str
    voice_conversion_model: str
    voice_conversion_device: str
    qwen_tts_vc_model: str
    qwen_tts_customization_path: str
    qwen_voice_cache_dir: Path
    speaker_ref_audio_min_s: float
    speaker_ref_audio_max_s: float
    speaker_ref_keep_raw: bool
    speaker_similarity_priority: str
    reference_audio_strategy: str
    tts_fluency_mode: str
    tts_style_instructions: str
    default_target_dialect: str
    default_dialect_style: str
    pronunciation_mode: str
    pronunciation_llm_fallback: bool
    pronunciation_rag_enabled: bool
    pronunciation_target_dialect: str
    local_clone_provider: str
    timeout_s: int
    retry_count: int
    output_dir: Path

    @classmethod
    def from_env(cls) -> "Step2Config":
        _load_env_file()
        root = Path(__file__).resolve().parent.parent.parent
        return cls(
            provider=os.getenv("REWRITE_PROVIDER", "deepseek").strip().lower(),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip(),
            qwen_api_key=os.getenv("QWEN_LLM_API_KEY", "").strip(),
            qwen_base_url=os.getenv("QWEN_LLM_BASE_URL", "").rstrip("/"),
            qwen_model=os.getenv("QWEN_LLM_MODEL", "").strip(),
            qwen_tts_api_key=os.getenv("QWEN_TTS_API_KEY", os.getenv("DASHSCOPE_API_KEY", "")).strip(),
            qwen_tts_base_url=os.getenv("QWEN_TTS_BASE_URL", os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/api/v1")).rstrip("/"),
            qwen_tts_model=os.getenv("QWEN_TTS_MODEL", "qwen3-tts-flash").strip(),
            qwen_tts_voice=os.getenv("QWEN_TTS_VOICE", "Kiki").strip(),
            qwen_tts_format=os.getenv("QWEN_TTS_FORMAT", "wav").strip().lower(),
            qwen_tts_path=os.getenv("QWEN_TTS_PATH", "/services/aigc/multimodal-generation/generation").strip(),
            qwen_tts_language_type=os.getenv("QWEN_TTS_LANGUAGE_TYPE", "Chinese").strip(),
            qwen_tts_instruction_model=os.getenv("QWEN_TTS_INSTRUCTION_MODEL", "qwen3-tts-instruct-flash").strip(),
            qwen_tts_teacher_voice=os.getenv("QWEN_TTS_TEACHER_VOICE", "Cherry").strip(),
            qwen_tts_teacher_instructions=os.getenv(
                "QWEN_TTS_TEACHER_INSTRUCTIONS",
                "用自然、连贯、口语化的广东通用粤语播报，句中连接平滑，停顿轻一点，整体比普通朗读更顺。",
            ).strip(),
            voice_clone_provider=os.getenv("VOICE_CLONE_PROVIDER", "qwen_vc").strip(),
            text_clone_provider=os.getenv("TEXT_CLONE_PROVIDER", os.getenv("VOICE_CLONE_PROVIDER", "qwen_vc")).strip(),
            voice_conversion_provider=_voice_match_provider_from_env(),
            qwen_voice_enrollment_model=os.getenv("QWEN_VOICE_ENROLLMENT_MODEL", "qwen-voice-enrollment").strip(),
            qwen_voice_target_model=os.getenv(
                "QWEN_VOICE_TARGET_MODEL",
                os.getenv("QWEN_TTS_VC_MODEL", "qwen3-tts-vc-2026-01-22"),
            ).strip(),
            voice_conversion_mode=os.getenv("VOICE_CONVERSION_MODE", "teacher_audio_to_audio").strip(),
            voice_conversion_model=os.getenv("VOICE_CONVERSION_MODEL", "").strip(),
            voice_conversion_device=os.getenv("VOICE_CONVERSION_DEVICE", "cpu").strip(),
            qwen_tts_vc_model=os.getenv(
                "QWEN_TTS_VC_MODEL",
                os.getenv("QWEN_VOICE_TARGET_MODEL", "qwen3-tts-vc-2026-01-22"),
            ).strip(),
            qwen_tts_customization_path=os.getenv("QWEN_TTS_CUSTOMIZATION_PATH", "/services/audio/tts/customization").strip(),
            qwen_voice_cache_dir=Path(
                os.getenv("QWEN_VOICE_CACHE_DIR", str(root / "runtime_data" / "step2_output" / "voice_cache"))
            ),
            speaker_ref_audio_min_s=float(os.getenv("SPEAKER_REF_AUDIO_MIN_S", "10")),
            speaker_ref_audio_max_s=float(os.getenv("SPEAKER_REF_AUDIO_MAX_S", "20")),
            speaker_ref_keep_raw=os.getenv("SPEAKER_REF_KEEP_RAW", "1") == "1",
            speaker_similarity_priority=os.getenv("SPEAKER_SIMILARITY_PRIORITY", "high").strip(),
            reference_audio_strategy=os.getenv("REFERENCE_AUDIO_STRATEGY", "vad_concat").strip(),
            tts_fluency_mode=os.getenv("TTS_FLUENCY_MODE", "allow_rate_adjust").strip(),
            tts_style_instructions=os.getenv(
                "TTS_STYLE_INSTRUCTIONS",
                "保持说话人音色接近参考音频，整体语速可以略微调整，停顿自然，保证粤语播报顺畅。",
            ).strip(),
            default_target_dialect=os.getenv("DEFAULT_TARGET_DIALECT", "yue").strip(),
            default_dialect_style=os.getenv("DEFAULT_DIALECT_STYLE", "guangdong_general").strip(),
            pronunciation_mode=os.getenv("PRONUNCIATION_MODE", "rule_first").strip(),
            pronunciation_llm_fallback=os.getenv("PRONUNCIATION_LLM_FALLBACK", "1") == "1",
            pronunciation_rag_enabled=os.getenv("PRONUNCIATION_RAG_ENABLED", "0") == "1",
            pronunciation_target_dialect=os.getenv("PRONUNCIATION_TARGET_DIALECT", "yue").strip(),
            local_clone_provider=os.getenv("LOCAL_CLONE_PROVIDER", "gpt_sovits").strip(),
            timeout_s=int(os.getenv("REWRITE_TIMEOUT_S", "45")),
            retry_count=int(os.getenv("REWRITE_RETRY_COUNT", "2")),
            output_dir=Path(os.getenv("STEP2_OUTPUT_DIR", str(root / "runtime_data" / "step2_output"))),
        )
