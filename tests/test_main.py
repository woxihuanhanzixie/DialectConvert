from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main
from app.main import _is_supported_upload
from app.main import app


def test_audio_limits_are_exposed_to_frontend():
    response = TestClient(app).get("/api/audio-limits")

    assert response.status_code == 200
    assert response.json()["min_seconds"] > 0
    assert response.json()["max_seconds"] >= response.json()["min_seconds"]


def test_health_reports_static_assets_available():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    configured = response.json()["configured"]
    assert configured["static_index_html"] is True
    assert configured["static_app_js"] is True
    assert configured["static_styles_css"] is True


def test_frontend_static_assets_are_served():
    client = TestClient(app)

    index_response = client.get("/")
    app_js_response = client.get("/static/app.js")
    styles_response = client.get("/static/styles.css")

    assert index_response.status_code == 200
    assert 'id="convertForm"' in index_response.text
    assert "/static/app.js" in index_response.text
    assert "/static/styles.css" in index_response.text

    assert app_js_response.status_code == 200
    assert 'document.querySelector("#convertForm")' in app_js_response.text
    assert "form.addEventListener" in app_js_response.text

    assert styles_response.status_code == 200
    assert ".app-shell" in styles_response.text
    assert ".primary" in styles_response.text


def test_mobile_capture_content_types_are_supported():
    assert _is_supported_upload(SimpleNamespace(filename="recording.m4a", content_type="audio/mp4"))
    assert _is_supported_upload(SimpleNamespace(filename="recording.3gp", content_type="audio/3gpp"))
    assert _is_supported_upload(SimpleNamespace(filename="recording.mp4", content_type="video/mp4"))
    assert _is_supported_upload(SimpleNamespace(filename="recording.mov", content_type="video/quicktime"))


def test_non_audio_upload_is_rejected():
    assert not _is_supported_upload(SimpleNamespace(filename="payload.exe", content_type="application/octet-stream"))


def test_convert_internal_errors_are_sanitized(monkeypatch, tmp_path):
    audio = tmp_path / "short.wav"
    audio.write_bytes(b"fake")

    async def fake_save_upload(upload, job_id):
        return audio

    monkeypatch.setattr(main, "save_upload", fake_save_upload)
    monkeypatch.setattr(main, "ensure_reference_audio_duration", lambda path: 2.0)
    monkeypatch.setattr(main, "convert_audio", lambda job_id, path, dialect: (_ for _ in ()).throw(RuntimeError("raw backend error")))

    with TestClient(app) as client:
        response = client.post(
            "/api/convert",
            data={"dialect": "cantonese"},
            files={"audio": ("demo.wav", b"fake", "audio/wav")},
        )

    assert response.status_code == 502
    assert response.json() == {"detail": "服务器繁忙，请稍后再试"}


def test_convert_without_playable_audio_is_sanitized(monkeypatch, tmp_path):
    audio = tmp_path / "short.wav"
    audio.write_bytes(b"fake")

    async def fake_save_upload(upload, job_id):
        return audio

    monkeypatch.setattr(main, "save_upload", fake_save_upload)
    monkeypatch.setattr(main, "ensure_reference_audio_duration", lambda path: 2.0)
    monkeypatch.setattr(main, "update_job_metadata", lambda job_id, payload: None)
    monkeypatch.setattr(
        main,
        "convert_audio",
        lambda job_id, path, dialect: SimpleNamespace(
            status="failed",
            recommended_audio_url=None,
            gold_audio_url=None,
            voice_matched_audio_url=None,
            warnings=["raw provider warning"],
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/convert",
            data={"dialect": "cantonese"},
            files={"audio": ("demo.wav", b"fake", "audio/wav")},
        )

    assert response.status_code == 502
    assert response.json() == {"detail": "服务器繁忙，请稍后再试"}


def test_speak_with_voice_endpoint_uses_registered_voice(monkeypatch):
    monkeypatch.setattr(
        main,
        "speak_with_registered_voice",
        lambda job_id, text, dialect, voice_id: SimpleNamespace(
            job_id=job_id,
            dialect=dialect,
            source_text=f"{text}。",
            dialect_text="今晚记得返屋企食饭。",
            emotion_label="开心",
            prosody_instruction="语气明亮，节奏轻快",
            audio_url="/media/outputs/demo.mp3",
            status="ok",
        ),
    )
    monkeypatch.setattr(main, "update_job_metadata", lambda job_id, payload: None)

    response = TestClient(app).post(
        "/api/speak-with-voice",
        data={"dialect": "cantonese", "voice_id": "voice-123", "text": "今晚记得回家吃饭"},
    )

    assert response.status_code == 200
    assert response.json()["audio_url"] == "/media/outputs/demo.mp3"


def test_speak_with_voice_endpoint_sanitizes_errors(monkeypatch):
    monkeypatch.setattr(
        main,
        "speak_with_registered_voice",
        lambda job_id, text, dialect, voice_id: (_ for _ in ()).throw(RuntimeError("raw provider error")),
    )

    response = TestClient(app).post(
        "/api/speak-with-voice",
        data={"dialect": "cantonese", "voice_id": "voice-123", "text": "今晚记得回家吃饭"},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "服务器繁忙，请稍后再试"}


def test_preview_audio_endpoint_returns_playable_preview(monkeypatch, tmp_path):
    source = tmp_path / "input.amr"
    preview = tmp_path / "preview.mp3"
    source.write_bytes(b"fake")
    preview.write_bytes(b"mp3")

    async def fake_save_upload(upload, job_id):
        return source

    monkeypatch.setattr(main, "save_upload", fake_save_upload)
    monkeypatch.setattr(main, "make_browser_preview_audio", lambda source_path, target_path: (preview, 12.4))
    monkeypatch.setattr(main, "public_url_for", lambda path: f"/media/outputs/{path.name}")
    monkeypatch.setattr(main, "update_job_metadata", lambda job_id, payload: None)

    response = TestClient(app).post(
        "/api/preview-audio",
        files={"audio": ("demo.amr", b"fake", "audio/amr")},
    )

    assert response.status_code == 200
    assert response.json() == {"audio_url": "/media/outputs/preview.mp3", "duration_s": 12.4}
