from pathlib import Path

import app.pipeline as pipeline


def test_convert_audio_prefers_voice_matched(monkeypatch, tmp_path):
    audio = tmp_path / "ref.wav"
    audio.write_bytes(b"fake-audio")

    monkeypatch.setattr(pipeline, "cleanup_runtime", lambda: 0)
    monkeypatch.setattr(pipeline, "transcribe_audio", lambda path: "我要保护家乡话")
    monkeypatch.setattr(
        pipeline,
        "rewrite_to_dialect",
        lambda text, dialect: {"dialect_text": "我要保护家乡话噻", "pronunciation_note": "自然川渝口语"},
    )
    monkeypatch.setattr(pipeline, "voice_cache_key", lambda path, model: "cache")
    monkeypatch.setattr(pipeline, "read_voice_cache", lambda key: None)
    monkeypatch.setattr(pipeline, "write_voice_cache", lambda key, payload: None)
    monkeypatch.setattr(pipeline, "enroll_voice", lambda path: "voice-1")

    def fake_synth(text, output_path, *, voice, model=None, instruction=None, language_hint="zh"):
        assert instruction
        return f"/media/{output_path.name}-{voice}.mp3"

    monkeypatch.setattr(pipeline, "synthesize", fake_synth)
    result = pipeline.convert_audio("job", audio, "sichuanese")

    assert result.source_text == "我要保护家乡话"
    assert result.dialect_text == "我要保护家乡话噻"
    assert result.voice_id == "voice-1"
    assert result.recommended_audio_url == result.voice_matched_audio_url
