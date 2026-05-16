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
    gold_audio_url: str | None = None
    voice_matched_audio_url: str | None = None
    recommended_audio_url: str | None = None
    voice_id: str | None = None
    status: str = "ok"
    warnings: list[str] = Field(default_factory=list)


class HealthResult(BaseModel):
    ok: bool
    app: str
    configured: dict[str, bool]

