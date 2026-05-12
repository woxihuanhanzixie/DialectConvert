from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    text: str
    provider: str = "deepseek"


class ReviewResponse(BaseModel):
    asr_raw_text: str
    asr_reviewed_text: str
    asr_review_notes: str = ""
    review_degrade_mode: bool = False
    review_model: str
    review_latency_ms: float
    input_lang: str = "zh"


class RewriteRequest(BaseModel):
    text: str
    target_dialect: str = "yue"
    dialect_style: str = "guangdong_general"
    provider: str = "deepseek"
    segment_max_len: int = 28


class CulturalKnowledgeCardResponse(BaseModel):
    id: str
    target_dialect: str
    term: str
    aliases: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)
    meaning: str = ""
    cultural_note: str = ""
    usage_example: str = ""
    speech_register: str = Field(default="", alias="register")
    source_label: str = ""
    source_url: str = ""


class RewriteResponse(BaseModel):
    source_text: str
    tn_text: str
    rewrite_segments: list[str]
    dialect_text: str
    semantic_text: str = ""
    pronunciation_text: str = ""
    prosody_text: str = ""
    pronunciation_mode: str = "rule_first"
    pronunciation_rule_hits: list[dict[str, Any]] = Field(default_factory=list)
    pronunciation_hit_categories: list[str] = Field(default_factory=list)
    pronunciation_fallback_used: bool = False
    pronunciation_notes: str = ""
    prosody_mode: str = "rule_plus_llm"
    prosody_rule_hits: list[dict[str, Any]] = Field(default_factory=list)
    prosody_hit_categories: list[str] = Field(default_factory=list)
    prosody_fallback_used: bool = False
    prosody_notes: str = ""
    cultural_cards: list[CulturalKnowledgeCardResponse] = Field(default_factory=list)
    cultural_card_terms: list[str] = Field(default_factory=list)
    degrade_mode: bool
    llm_model: str
    llm_latency_ms: float
    llm_error: str = ""
    input_lang: str = "zh"
    pivot_text_zh: str = ""
    translation_notes: str = ""
    target_dialect: str = "yue"
    dialect_style: str = "guangdong_general"


class TtsRequest(BaseModel):
    text: str
    voice: str = "Kiki"
    model: str = "qwen3-tts-flash"
    language_type: str = "Chinese"
    voice_clone_enabled: bool = False
    speaker_ref_audio: str = ""
    voice_clone_provider: str = "openvoice"
    clone_mode: str = "api_first"
    speaker_similarity_priority: str = "high"
    tts_fluency_mode: str = "allow_rate_adjust"
    tts_style_instructions: str = ""


class TtsRouteResponse(BaseModel):
    route_name: str
    wav_path: str = ""
    audio_url: str = ""
    expires_at: str = ""
    tts_model: str = ""
    tts_voice: str = ""
    latency_ms: float = 0.0
    error: str = ""
    input_text: str = ""
    input_mode: str = "semantic_text"
    route_role: str = ""
    route_reason: str = ""
    audio_meta: dict[str, Any] | None = None
    voice_clone_enabled: bool = False
    voice_clone_provider: str = ""
    speaker_similarity_note: str = ""
    clone_mode: str = ""
    fallback_reason: str = ""
    speaker_similarity_priority: str = "high"
    tts_fluency_mode: str = "allow_rate_adjust"
    tts_style_instructions: str = ""
    instruction_mode_active: bool = False


class GapSummaryResponse(BaseModel):
    content_diff: str = ""
    pronunciation_diff: str = ""
    fluency_diff: str = ""
    route_summary: str = ""
    processing_split: str = ""
    issue_tags: list[dict[str, Any]] = Field(default_factory=list)
    issue_tag_summary: str = ""
    recommended_route: str = "baseline"
    recommended_strategy: str = ""
    recommended_reason: str = ""
    baseline_advantage: str = ""
    clone_weakness: str = ""


class VoiceMatchSummaryResponse(BaseModel):
    teacher_is_reference: bool = True
    voice_matched_available: bool = False
    voice_match_provider: str = ""
    voice_match_error: str = ""
    recommendation_reason: str = ""


class TtsResponse(BaseModel):
    wav_path: str = ""
    audio_url: str = ""
    expires_at: str = ""
    tts_model: str
    tts_voice: str
    latency_ms: float
    error: str = ""
    voice_clone_enabled: bool = False
    voice_clone_provider: str = ""
    speaker_similarity_note: str = ""
    clone_mode: str = ""
    fallback_reason: str = ""
    speaker_similarity_priority: str = "high"
    tts_fluency_mode: str = "allow_rate_adjust"
    tts_style_instructions: str = ""
    instruction_mode_active: bool = False
    tts_input_text: str = ""
    tts_input_mode: str = "semantic_text"
    audio_meta: dict[str, Any] | None = None
    baseline_wav_path: str = ""
    baseline_audio_url: str = ""
    baseline_tts_model: str = ""
    baseline_tts_voice: str = ""
    baseline_error: str = ""
    baseline_tts_input_text: str = ""
    baseline_tts_input_mode: str = "semantic_text"
    baseline_audio_meta: dict[str, Any] | None = None
    baseline: TtsRouteResponse | None = None
    clone: TtsRouteResponse | None = None
    gap_summary: GapSummaryResponse | None = None
    gold_teacher: TtsRouteResponse | None = None
    voice_matched: TtsRouteResponse | None = None
    legacy_text_clone: TtsRouteResponse | None = None
    recommended_main_output: str = "gold_teacher"
    voice_match_summary: VoiceMatchSummaryResponse | None = None
    timbre_ref_audio: str = ""
    prosody_ref_audio: str = ""
    prosody_guidance_mode: str = ""


class PipelineResponse(BaseModel):
    source_audio: dict[str, Any] | None = None
    asr: dict[str, Any] | None = None
    review: ReviewResponse | None = None
    rewrite: RewriteResponse | None = None
    tts: TtsResponse | None = None
    trace_id: str
    total_latency_ms: float = Field(..., description="Total elapsed time in milliseconds")
    input_lang: str = "zh"
    pivot_text_zh: str = ""


class HealthResponse(BaseModel):
    status: str
    supported_dialects: list[str]
    default_voice: str
    runtime: dict[str, Any]
