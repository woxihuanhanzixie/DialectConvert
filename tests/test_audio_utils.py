from types import SimpleNamespace
import wave

import pytest

import app.audio_utils as audio_utils


def _write_silent_wav(path, seconds=1, rate=16000):
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(b"\x00\x00" * rate * seconds)


def test_reference_audio_short_wav_is_allowed_to_enter_pipeline(monkeypatch, tmp_path):
    audio = tmp_path / "short.wav"
    _write_silent_wav(audio, seconds=2)
    monkeypatch.setattr(
        audio_utils,
        "settings",
        SimpleNamespace(ref_audio_min_s=8, ref_audio_max_s=40),
    )

    assert audio_utils.ensure_reference_audio_duration(audio) == pytest.approx(2.0)


def test_reference_audio_valid_wav_returns_duration(monkeypatch, tmp_path):
    audio = tmp_path / "valid.wav"
    _write_silent_wav(audio, seconds=9)
    monkeypatch.setattr(
        audio_utils,
        "settings",
        SimpleNamespace(ref_audio_min_s=8, ref_audio_max_s=40),
    )

    assert audio_utils.ensure_reference_audio_duration(audio) == pytest.approx(9.0)


def test_audio_short_provider_error_is_detected():
    error = 'HTTP 400: {"code":"Audio.AudioShortError","message":"audio too short!"}'

    assert audio_utils.is_audio_too_short_error(error)


def test_browser_preview_keeps_browser_playable_audio(tmp_path):
    audio = tmp_path / "demo.mp3"
    target = tmp_path / "target.mp3"
    audio.write_bytes(b"mp3")

    preview, duration = audio_utils.make_browser_preview_audio(audio, target)

    assert preview == audio
    assert duration is None
