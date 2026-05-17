from types import SimpleNamespace

from app.main import _is_supported_upload


def test_mobile_capture_content_types_are_supported():
    assert _is_supported_upload(SimpleNamespace(filename="recording.m4a", content_type="audio/mp4"))
    assert _is_supported_upload(SimpleNamespace(filename="recording.3gp", content_type="audio/3gpp"))
    assert _is_supported_upload(SimpleNamespace(filename="recording.mp4", content_type="video/mp4"))
    assert _is_supported_upload(SimpleNamespace(filename="recording.mov", content_type="video/quicktime"))


def test_non_audio_upload_is_rejected():
    assert not _is_supported_upload(SimpleNamespace(filename="payload.exe", content_type="application/octet-stream"))
