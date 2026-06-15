from dataclasses import replace

import app.providers as providers


def _use_real_llm_path(monkeypatch):
    monkeypatch.setattr(
        providers,
        "settings",
        replace(providers.settings, enable_mock_when_no_key=False, qwen_llm_api_key="test-key"),
    )


def test_rewrite_to_dialect_parses_markdown_fenced_json(monkeypatch):
    _use_real_llm_path(monkeypatch)

    def fake_request_json(method, url, *, headers, payload):
        return {
            "choices": [
                {
                    "message": {
                        "content": """```json
{
  "dialect_text": "各位评委老师，大家好。我哋係声临其境项目组嘅成员，好荣幸可以参加今次比赛嘅决赛。",
  "pronunciation_note": "保持正式答辩语气。"
}
```"""
                    }
                }
            ]
        }

    monkeypatch.setattr(providers, "_request_json", fake_request_json)

    result = providers.rewrite_to_dialect(
        "各位评委老师你们好。我们是声临其境项目组的成员，很荣幸能够参加这次比赛决赛。",
        "cantonese",
        expression={"emotion_label": "自然", "prosody_instruction": "语气自然，节奏平稳"},
        rag_context="以下是该方言的正确表达参考（请优先使用）：\n- 「评委老师」→ 评委老师 / 评审老师",
    )

    assert result["dialect_text"] == "各位评委老师，大家好。我哋係声临其境项目组嘅成员，好荣幸可以参加今次比赛嘅决赛。"
    assert "```" not in result["dialect_text"]
    assert "dialect_text" not in result["dialect_text"]
    assert result["pronunciation_note"] == "保持正式答辩语气。"


def test_rewrite_to_dialect_does_not_synthesize_unparseable_json(monkeypatch):
    _use_real_llm_path(monkeypatch)
    monkeypatch.setattr(
        providers,
        "_request_json",
        lambda *args, **kwargs: {"choices": [{"message": {"content": "```json\n{bad json\n```"}}]},
    )

    source = "各位评委老师你们好。"
    result = providers.rewrite_to_dialect(source, "cantonese")

    assert result["dialect_text"] == source
    assert "```" not in result["dialect_text"]
