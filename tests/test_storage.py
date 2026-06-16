from types import SimpleNamespace

from app.storage import safe_ext
import app.storage as storage


def test_safe_ext_keeps_common_audio_suffixes():
    assert safe_ext("demo.webm", "audio/webm") == ".webm"
    assert safe_ext("demo.mp3", "audio/mpeg") == ".mp3"


def test_safe_ext_falls_back_from_content_type():
    assert safe_ext("recording", "audio/ogg") == ".ogg"
    assert safe_ext(None, "audio/wav") == ".wav"
    assert safe_ext("ios-recording", "audio/mp4") == ".m4a"
    assert safe_ext("android-recording", "audio/3gpp") == ".3gp"
    assert safe_ext("voice", "audio/x-caf") == ".caf"


def test_safe_ext_rejects_unknown_suffix_to_wav():
    assert safe_ext("bad.exe", "application/octet-stream") == ".wav"


def test_new_job_id_is_sortable_and_non_sensitive():
    job_id = storage.new_job_id()

    assert job_id.startswith("dc_")
    assert len(job_id.split("_")) == 3
    assert "audio" not in job_id.lower()


def test_voice_cache_requires_audio_metadata_match(monkeypatch, tmp_path):
    monkeypatch.setattr(
        storage,
        "settings",
        SimpleNamespace(
            upload_dir=tmp_path / "uploads",
            output_dir=tmp_path / "outputs",
            metadata_dir=tmp_path / "jobs",
            cache_dir=tmp_path / "voice_cache",
            cleanup_after_hours=1,
            voice_cache_ttl_hours=1,
        ),
    )
    storage.ensure_dirs()

    audio = tmp_path / "ref.wav"
    audio.write_bytes(b"fake-audio")
    expected = storage.voice_cache_metadata(audio, "cosyvoice-v3.5-plus", 8.576)

    storage.write_voice_cache("legacy", {"status": "ok", "voice_id": "voice-old"})
    assert storage.read_voice_cache("legacy", expected=expected) is None

    storage.write_voice_cache("current", {**expected, "status": "ok", "voice_id": "voice-new"})
    assert storage.read_voice_cache("current", expected=expected)["voice_id"] == "voice-new"

    mismatched = {**expected, "audio_duration_s": 10.8}
    assert storage.read_voice_cache("current", expected=mismatched) is None


def test_cleanup_runtime_removes_old_media_and_job_metadata(monkeypatch, tmp_path):
    monkeypatch.setattr(
        storage,
        "settings",
        SimpleNamespace(
            upload_dir=tmp_path / "uploads",
            output_dir=tmp_path / "outputs",
            metadata_dir=tmp_path / "jobs",
            cache_dir=tmp_path / "voice_cache",
            cleanup_after_hours=1,
            voice_cache_ttl_hours=1,
        ),
    )
    storage.ensure_dirs()

    old_paths = [
        storage.settings.upload_dir / "dc_old.wav",
        storage.settings.output_dir / "dc_old_gold.mp3",
        storage.settings.metadata_dir / "dc_old.json",
        storage.settings.cache_dir / "voice.json",
    ]
    for path in old_paths:
        path.write_text("old", encoding="utf-8")
        old_time = 1
        path.touch()
        path.chmod(0o666)
        import os

        os.utime(path, (old_time, old_time))

    removed = storage.cleanup_runtime()

    assert removed == len(old_paths)
    assert all(not path.exists() for path in old_paths)
