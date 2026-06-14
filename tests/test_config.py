import importlib

import app.config as config


def test_qwen_llm_key_can_fall_back_to_deepseek(monkeypatch):
    monkeypatch.setenv("QWEN_LLM_API_KEY", "")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "")
    monkeypatch.setenv("QWEN_TTS_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-leaked")

    reloaded = importlib.reload(config)

    assert reloaded.settings.qwen_llm_api_key == "sk-leaked"
