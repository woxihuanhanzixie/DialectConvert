from pathlib import Path

import app.pipeline as pipeline


def test_convert_audio_prefers_voice_matched(monkeypatch, tmp_path):
    audio = tmp_path / "ref.wav"
    audio.write_bytes(b"fake-audio")

    source_text = "\u6211\u8981\u4fdd\u62a4\u5bb6\u4e61\u8bdd"
    dialect_text = "\u6211\u8981\u4fdd\u62a4\u5bb6\u4e61\u8bdd\u5662"
    synth_calls = []

    monkeypatch.setattr(pipeline, "cleanup_runtime", lambda: 0)
    monkeypatch.setattr(pipeline, "transcribe_audio", lambda path: source_text)
    monkeypatch.setattr(
        pipeline,
        "rewrite_to_dialect",
        lambda text, dialect: {
            "dialect_text": dialect_text,
            "pronunciation_note": "\u81ea\u7136\u5ddd\u6e1d\u53e3\u8bed",
        },
    )
    monkeypatch.setattr(pipeline, "voice_cache_key", lambda path, model: "cache")
    monkeypatch.setattr(pipeline, "read_voice_cache", lambda key: None)
    monkeypatch.setattr(pipeline, "write_voice_cache", lambda key, payload: None)
    monkeypatch.setattr(pipeline, "enroll_voice", lambda path: "voice-1")

    def fake_synth(text, output_path, *, voice, model=None, instruction=None, language_hint="zh"):
        synth_calls.append(
            {
                "text": text,
                "voice": voice,
                "instruction": instruction,
                "language_hint": language_hint,
            }
        )
        return f"/media/{output_path.name}-{voice}.mp3"

    monkeypatch.setattr(pipeline, "synthesize", fake_synth)
    result = pipeline.convert_audio("job", audio, "sichuanese")

    assert result.source_text == source_text
    assert result.dialect_text == dialect_text
    assert result.voice_id == "voice-1"
    assert result.recommended_audio_url == result.voice_matched_audio_url
    assert synth_calls
    assert {call["text"] for call in synth_calls} == {dialect_text}
    assert {call["instruction"] for call in synth_calls} == {"\u8bf7\u7528\u56db\u5ddd\u8bdd\u8868\u8fbe\u3002"}
    assert {call["language_hint"] for call in synth_calls} == {"zh"}
