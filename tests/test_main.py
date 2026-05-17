from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import _is_supported_upload
from app.main import app


def test_audio_limits_are_exposed_to_frontend():
    response = TestClient(app).get("/api/audio-limits")

    assert response.status_code == 200
    assert response.json()["min_seconds"] > 0
    assert response.json()["max_seconds"] >= response.json()["min_seconds"]


def test_mobile_capture_content_types_are_supported():
    assert _is_supported_upload(SimpleNamespace(filename="recording.m4a", content_type="audio/mp4"))
    assert _is_supported_upload(SimpleNamespace(filename="recording.3gp", content_type="audio/3gpp"))
    assert _is_supported_upload(SimpleNamespace(filename="recording.mp4", content_type="video/mp4"))
    assert _is_supported_upload(SimpleNamespace(filename="recording.mov", content_type="video/quicktime"))


def test_non_audio_upload_is_rejected():
    assert not _is_supported_upload(SimpleNamespace(filename="payload.exe", content_type="application/octet-stream"))
