from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AudioMeta(BaseModel):
    original_path: str
    raw_path: str | None = None
    normalized_path: str
    work_path: str | None = None
    sample_rate: int
    channels: int
    duration_s: float
    format: str
    audio_frontend: dict[str, Any] | None = None


class AsrResponse(BaseModel):
    uttid: str
    text: str
    confidence: float | None = None
    timestamp: list[list[Any]] | None = None
    punc_text: str | None = None
    audio_meta: AudioMeta | None = None
    audio_quality: dict[str, Any] | None = None
    detected_languages: list[dict[str, Any]] | None = None
    vad_segments_ms: list[list[int]] | None = None
    sentences: list[dict[str, Any]] | None = None
    words: list[dict[str, Any]] | None = None
    latency_ms: float = Field(..., description="API elapsed time in milliseconds")


class ErrorResponse(BaseModel):
    error_code: str
    message: str


class HealthResponse(BaseModel):
    status: str
    capabilities: dict[str, Any]
    engine: dict[str, Any]
