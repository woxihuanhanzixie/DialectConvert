from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Dialect = Literal["cantonese", "sichuanese", "hokkien"]


class ConversionResult(BaseModel):
    job_id: str
    dialect: Dialect
    source_text: str
    dialect_text: str
    pronunciation_note: str = ""
    emotion_label: str = ""
    prosody_instruction: str = ""
    gold_audio_url: str | None = None
    voice_matched_audio_url: str | None = None
    recommended_audio_url: str | None = None
    voice_id: str | None = None
    status: str = "ok"
    warnings: list[str] = Field(default_factory=list)
    timings_ms: dict[str, int] = Field(default_factory=dict)


class RegisteredVoiceSpeakResult(BaseModel):
    job_id: str
    dialect: Dialect
    source_text: str
    dialect_text: str
    emotion_label: str = ""
    prosody_instruction: str = ""
    audio_url: str
    status: str = "ok"


class HealthResult(BaseModel):
    ok: bool
    app: str
    configured: dict[str, bool]
