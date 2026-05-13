from __future__ import annotations

import time
from http import HTTPStatus
from pathlib import Path
from typing import Any

import soundfile as sf

from .config import AsrServiceConfig


class CloudAsrError(RuntimeError):
    pass


class DashScopeAsrEngine:
    def __init__(self, cfg: AsrServiceConfig):
        self.cfg = cfg

    def transcribe_file(
        self,
        wav_path: str | Path,
        *,
        enable_punc: bool = True,
        return_timestamp: bool = True,
    ) -> dict[str, Any]:
        if self.cfg.cloud_provider not in {"dashscope", "qwen", "aliyun"}:
            raise CloudAsrError(f"Unsupported cloud ASR provider: {self.cfg.cloud_provider}")
        if not self.cfg.cloud_api_key:
            raise CloudAsrError("Missing ASR_CLOUD_API_KEY or DASHSCOPE_API_KEY")

        try:
            import dashscope
            from dashscope.audio.asr import Recognition
        except ModuleNotFoundError as exc:
            raise CloudAsrError("dashscope package is not installed") from exc

        path = Path(wav_path)
        if not path.exists():
            raise CloudAsrError(f"Audio file not found: {path}")

        dashscope.api_key = self.cfg.cloud_api_key
        kwargs: dict[str, Any] = {
            "disfluency_removal_enabled": self.cfg.cloud_disfluency_removal,
            "diarization_enabled": self.cfg.cloud_diarization,
            "timestamp_alignment_enabled": return_timestamp and self.cfg.cloud_timestamp_alignment,
        }
        language_hints = _split_csv(self.cfg.cloud_language_hints)
        if language_hints:
            kwargs["language_hints"] = language_hints
        if not enable_punc:
            kwargs["punctuation_prediction_enabled"] = False

        audio_format = _dashscope_audio_format(path)
        sample_rate = _audio_sample_rate(path) or 16000
        recognition = Recognition(
            model=self.cfg.cloud_model,
            callback=None,
            format=audio_format,
            sample_rate=sample_rate,
            workspace=self.cfg.cloud_workspace or None,
            **kwargs,
        )
        t0 = time.perf_counter()
        result = recognition.call(str(path))
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        if result.status_code != HTTPStatus.OK:
            message = getattr(result, "message", "") or getattr(result, "code", "") or "cloud ASR failed"
            raise CloudAsrError(f"DashScope ASR failed: {message}")

        sentences_raw = result.get_sentence() or []
        if isinstance(sentences_raw, dict):
            sentences_raw = [sentences_raw]
        sentences = [_normalize_sentence(s) for s in sentences_raw if isinstance(s, dict)]
        text = "".join(s.get("text", "") for s in sentences).strip()
        words = [w for sentence in sentences for w in sentence.get("words", [])]
        detected_languages = _detected_languages(sentences)
        return {
            "uttid": path.stem,
            "text": text,
            "confidence": _avg_confidence(sentences),
            "timestamp": _word_timestamps(words) if return_timestamp else None,
            "punc_text": text if enable_punc else None,
            "vad_segments_ms": [
                [int(s["start_ms"]), int(s["end_ms"])]
                for s in sentences
                if s.get("start_ms") is not None and s.get("end_ms") is not None
            ],
            "sentences": sentences,
            "words": words,
            "detected_languages": detected_languages,
            "latency_ms": latency_ms,
            "asr_provider": "dashscope",
            "asr_model": self.cfg.cloud_model,
            "request_id": result.get_request_id(),
            "audio_format": audio_format,
            "sample_rate": sample_rate,
        }

    def health(self) -> dict[str, Any]:
        return {
            "provider": self.cfg.cloud_provider,
            "model": self.cfg.cloud_model,
            "api_key_configured": bool(self.cfg.cloud_api_key),
            "language_hints": _split_csv(self.cfg.cloud_language_hints),
        }


def transcribe_api_first(
    wav_path: str | Path,
    cfg: AsrServiceConfig,
    *,
    enable_punc: bool = True,
    return_timestamp: bool = True,
) -> tuple[dict[str, Any] | None, str]:
    if cfg.provider not in {"api_only", "api_first", "cloud_first", "dashscope", "qwen"}:
        return None, "cloud_asr_disabled"
    try:
        result = DashScopeAsrEngine(cfg).transcribe_file(
            wav_path,
            enable_punc=enable_punc,
            return_timestamp=return_timestamp,
        )
        return result, ""
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def _split_csv(value: str) -> list[str]:
    return [x.strip() for x in (value or "").split(",") if x.strip()]


def _dashscope_audio_format(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    mapping = {
        "m4a": "aac",
        "3gp": "amr",
    }
    return mapping.get(suffix, suffix or "wav")


def _audio_sample_rate(path: Path) -> int | None:
    try:
        return int(sf.info(str(path)).samplerate)
    except Exception:
        return None


def _normalize_sentence(sentence: dict[str, Any]) -> dict[str, Any]:
    begin = sentence.get("begin_time", sentence.get("start_time", sentence.get("start_ms")))
    end = sentence.get("end_time", sentence.get("end_ms"))
    words_raw = sentence.get("words") or []
    return {
        "text": str(sentence.get("text") or ""),
        "start_ms": _to_int(begin),
        "end_ms": _to_int(end),
        "confidence": _to_float(sentence.get("confidence")),
        "lang": sentence.get("language") or sentence.get("lang") or "",
        "words": [_normalize_word(w) for w in words_raw if isinstance(w, dict)],
        "raw": sentence,
    }


def _normalize_word(word: dict[str, Any]) -> dict[str, Any]:
    begin = word.get("begin_time", word.get("start_time", word.get("start_ms")))
    end = word.get("end_time", word.get("end_ms"))
    return {
        "text": str(word.get("text") or word.get("word") or ""),
        "start_ms": _to_int(begin),
        "end_ms": _to_int(end),
        "confidence": _to_float(word.get("confidence")),
    }


def _word_timestamps(words: list[dict[str, Any]]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for word in words:
        text = word.get("text")
        start_ms = word.get("start_ms")
        end_ms = word.get("end_ms")
        if text and start_ms is not None and end_ms is not None:
            rows.append([text, round(start_ms / 1000, 3), round(end_ms / 1000, 3)])
    return rows


def _detected_languages(sentences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for sentence in sentences:
        lang = str(sentence.get("lang") or "").strip()
        if not lang or lang in seen:
            continue
        seen[lang] = {"lang": lang, "confidence": sentence.get("confidence")}
    return list(seen.values())


def _avg_confidence(sentences: list[dict[str, Any]]) -> float | None:
    values = [float(s["confidence"]) for s in sentences if s.get("confidence") is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
