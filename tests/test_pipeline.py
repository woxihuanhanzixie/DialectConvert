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
        lambda text, dialect, expression=None, rag_context="": {
            "dialect_text": dialect_text,
            "pronunciation_note": "\u81ea\u7136\u5ddd\u6e1d\u53e3\u8bed",
        },
    )
    monkeypatch.setattr(pipeline, "voice_cache_key", lambda path, model: "cache")
    monkeypatch.setattr(pipeline, "read_voice_cache", lambda key, expected=None: None)
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
    assert {call["instruction"] for call in synth_calls if call["instruction"]} == {
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


def test_build_tts_instruction_can_target_reference_duration():
    instruction = pipeline.build_tts_instruction(
        "cantonese",
        "\u8bed\u6c14\u81ea\u7136\uff0c\u8282\u594f\u5e73\u7a33",
        8.576,
    )

    assert instruction.startswith("\u8bf7\u7528\u5e7f\u4e1c\u8bdd\u8868\u8fbe")
    assert "\u8d34\u8fd1\u53c2\u8003\u5f55\u97f3\u8bed\u901f" in instruction
    assert "\u7ea68.6\u79d2\u8bfb\u5b8c" in instruction
    assert len(instruction) <= 95


def test_convert_audio_retries_voice_matched_when_too_slow(monkeypatch, tmp_path):
    audio = tmp_path / "ref.wav"
    audio.write_bytes(b"fake-audio")
    synth_calls = []
    measured_durations = iter([10.9, 8.7])

    monkeypatch.setattr(pipeline, "cleanup_runtime", lambda: 0)
    monkeypatch.setattr(pipeline, "transcribe_audio", lambda path: "\u5404\u4f4d\u8bc4\u59d4\u8001\u5e08\u4f60\u4eec\u597d")
    monkeypatch.setattr(
        pipeline,
        "analyze_expression",
        lambda text: {
            "display_text": "\u5404\u4f4d\u8bc4\u59d4\u8001\u5e08\u4f60\u4eec\u597d\u3002",
            "emotion_label": "\u81ea\u7136",
            "prosody_instruction": "\u8bed\u6c14\u81ea\u7136\uff0c\u8282\u594f\u5e73\u7a33",
        },
    )
    monkeypatch.setattr(
        pipeline,
        "rewrite_to_dialect",
        lambda text, dialect, expression=None, rag_context="": {
            "dialect_text": "\u5404\u4f4d\u8bc4\u59d4\u8001\u5e08\uff0c\u5927\u5bb6\u597d\u3002",
            "pronunciation_note": "",
        },
    )
    monkeypatch.setattr(pipeline, "voice_cache_key", lambda path, model: "cache")
    monkeypatch.setattr(
        pipeline,
        "voice_cache_metadata",
        lambda path, model, duration_s=None: {
            "cache_schema": 2,
            "audio_sha256": "sha",
            "audio_bytes": 10,
            "target_model": model,
            "audio_duration_s": round(duration_s, 3),
        },
    )
    monkeypatch.setattr(pipeline, "read_voice_cache", lambda key, expected=None: None)
    monkeypatch.setattr(pipeline, "write_voice_cache", lambda key, payload: None)
    monkeypatch.setattr(pipeline, "enroll_voice", lambda path: "voice-1")
    monkeypatch.setattr(
        pipeline,
        "audio_duration_seconds",
        lambda path: next(measured_durations) if "voice_matched" in path.name else None,
    )

    def fake_synth(text, output_path, *, voice, model=None, instruction=None, language_hint="zh"):
        synth_calls.append({"voice": voice, "instruction": instruction})
        output_path.with_suffix(".mp3").write_bytes(b"fake")
        return f"/media/{output_path.name}-{len(synth_calls)}.mp3"

    monkeypatch.setattr(pipeline, "synthesize", fake_synth)

    result = pipeline.convert_audio("job", audio, "cantonese", reference_duration_s=8.576)

    voice_calls = [call for call in synth_calls if call["voice"] == "voice-1"]
    assert len(voice_calls) == 2
    assert "\u7ea68.6\u79d2\u8bfb\u5b8c" in voice_calls[0]["instruction"]
    assert "\u8bed\u901f\u52a0\u5feb" in voice_calls[1]["instruction"]
    assert result.voice_matched_audio_url == "/media/job_voice_matched.mp3-3.mp3"


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
        lambda text, dialect, expression=None, rag_context="": {"dialect_text": "\u4f60\u597d\u3002", "pronunciation_note": ""},
    )
    monkeypatch.setattr(pipeline, "voice_cache_key", lambda path, model: "cache")
    monkeypatch.setattr(pipeline, "read_voice_cache", lambda key, expected=None: None)
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
    assert result.warnings == ["Voice Matched \u514b\u9686\u97f3\u8272\u5931\u8d25\uff1a\u670d\u52a1\u5668\u7e41\u5fd9\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5"]


def test_speak_with_registered_voice_uses_existing_voice(monkeypatch):
    synth_calls = []
    monkeypatch.setattr(
        pipeline,
        "analyze_expression",
        lambda text: {
            "display_text": f"{text}\u3002",
            "emotion_label": "\u5f00\u5fc3",
            "prosody_instruction": "\u8bed\u6c14\u660e\u4eae\uff0c\u8282\u594f\u8f7b\u5feb",
        },
    )
    monkeypatch.setattr(
        pipeline,
        "rewrite_to_dialect",
        lambda text, dialect, expression=None, rag_context="": {"dialect_text": "\u4eca\u665a\u8bb0\u5f97\u8fd4\u5c4b\u4f01\u98df\u996d\u3002", "pronunciation_note": ""},
    )

    def fake_synth(text, output_path, *, voice, model=None, instruction=None, language_hint="zh"):
        synth_calls.append({"text": text, "voice": voice, "instruction": instruction})
        return "/media/jobs/registered_voice.mp3"

    monkeypatch.setattr(pipeline, "synthesize", fake_synth)

    result = pipeline.speak_with_registered_voice("job2", "\u4eca\u665a\u8bb0\u5f97\u56de\u5bb6\u5403\u996d", "cantonese", "voice-123")

    assert result.audio_url == "/media/jobs/registered_voice.mp3"
    assert synth_calls == [
        {
            "text": "\u4eca\u665a\u8bb0\u5f97\u8fd4\u5c4b\u4f01\u98df\u996d\u3002",
            "voice": "voice-123",
            "instruction": "\u8bf7\u7528\u5e7f\u4e1c\u8bdd\u8868\u8fbe\uff0c\u8bed\u6c14\u660e\u4eae\uff0c\u8282\u594f\u8f7b\u5feb\u3002",
        }
    ]
