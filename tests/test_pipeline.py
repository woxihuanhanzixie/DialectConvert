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
        "analyze_expression",
        lambda text: {
            "display_text": f"{text}\uff01",
            "emotion_label": "\u60ca\u8bb6",
            "prosody_instruction": "\u8bed\u6c14\u5938\u5f20\uff0c\u5c3e\u97f3\u4e0a\u626c",
        },
    )
    monkeypatch.setattr(
        pipeline,
        "rewrite_to_dialect",
        lambda text, dialect, expression=None: {
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

    assert result.source_text == f"{source_text}\uff01"
    assert result.dialect_text == dialect_text
    assert result.emotion_label == "\u60ca\u8bb6"
    assert result.prosody_instruction == "\u8bed\u6c14\u5938\u5f20\uff0c\u5c3e\u97f3\u4e0a\u626c"
    assert result.voice_id == "voice-1"
    assert result.recommended_audio_url == result.voice_matched_audio_url
    assert synth_calls
    assert {call["text"] for call in synth_calls} == {dialect_text}
    assert {call["instruction"] for call in synth_calls} == {
        "\u8bf7\u7528\u56db\u5ddd\u8bdd\u8868\u8fbe\uff0c\u8bed\u6c14\u5938\u5f20\uff0c\u5c3e\u97f3\u4e0a\u626c\u3002"
    }
    assert {call["language_hint"] for call in synth_calls} == {"zh"}


def test_build_tts_instruction_keeps_dialect_and_caps_length():
    instruction = pipeline.build_tts_instruction(
        "cantonese",
        "\u8bed\u6c14\u7126\u6025\uff0c\u505c\u987f\u66f4\u77ed\uff0c\u5c3e\u97f3\u7565\u4e0a\u626c",
    )

    assert instruction.startswith("\u8bf7\u7528\u5e7f\u4e1c\u8bdd\u8868\u8fbe")
    assert "\u8bed\u6c14\u7126\u6025" in instruction
    assert len(instruction) <= 95


def test_convert_audio_translates_audio_short_warning(monkeypatch, tmp_path):
    audio = tmp_path / "ref.wav"
    audio.write_bytes(b"fake-audio")

    monkeypatch.setattr(pipeline, "cleanup_runtime", lambda: 0)
    monkeypatch.setattr(pipeline, "transcribe_audio", lambda path: "\u4f60\u597d")
    monkeypatch.setattr(
        pipeline,
        "analyze_expression",
        lambda text: {
            "display_text": "\u4f60\u597d\u3002",
            "emotion_label": "\u81ea\u7136",
            "prosody_instruction": "\u81ea\u7136\u53e3\u8bed",
        },
    )
    monkeypatch.setattr(
        pipeline,
        "rewrite_to_dialect",
        lambda text, dialect, expression=None: {"dialect_text": "\u4f60\u597d\u3002", "pronunciation_note": ""},
    )
    monkeypatch.setattr(pipeline, "voice_cache_key", lambda path, model: "cache")
    monkeypatch.setattr(pipeline, "read_voice_cache", lambda key: None)
    monkeypatch.setattr(pipeline, "enroll_voice", lambda path: "voice-1")
    monkeypatch.setattr(pipeline, "settings", type("Settings", (), {**pipeline.settings.__dict__, "ref_audio_min_s": 8})())

    def fake_synth(text, output_path, *, voice, model=None, instruction=None, language_hint="zh"):
        if voice == "voice-1":
            raise pipeline.ProviderError('HTTP 400: {"code":"Audio.AudioShortError","message":"audio too short!"}')
        return f"/media/{output_path.name}-{voice}.mp3"

    monkeypatch.setattr(pipeline, "synthesize", fake_synth)

    result = pipeline.convert_audio("job", audio, "cantonese")

    assert result.gold_audio_url
    assert not result.voice_matched_audio_url
    assert result.warnings == ["Voice Matched \u514b\u9686\u97f3\u8272\u5931\u8d25\uff1a\u8bf7\u8f93\u5165\u5927\u4e8e 8s \u7684\u97f3\u9891"]
