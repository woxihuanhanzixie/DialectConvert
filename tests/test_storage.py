from pathlib import Path

from app.storage import safe_ext


def test_safe_ext_keeps_common_audio_suffixes():
    assert safe_ext("demo.webm", "audio/webm") == ".webm"
    assert safe_ext("demo.mp3", "audio/mpeg") == ".mp3"


def test_safe_ext_falls_back_from_content_type():
    assert safe_ext("recording", "audio/ogg") == ".ogg"
    assert safe_ext(None, "audio/wav") == ".wav"


def test_safe_ext_rejects_unknown_suffix_to_wav():
    assert safe_ext("bad.exe", "application/octet-stream") == ".wav"

