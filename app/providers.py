from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

import requests

from .config import settings
from .storage import atomic_write_bytes, media_url_to_public, public_url_for


class ProviderError(RuntimeError):
    pass


def _headers(api_key: str | None = None) -> dict[str, str]:
    key = api_key or settings.dashscope_api_key
    if not key:
        raise ProviderError("缺少 DASHSCOPE_API_KEY/QWEN_TTS_API_KEY")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _request_json(method: str, url: str, *, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(settings.max_retries):
        try:
            resp = requests.request(
                method,
                url,
                headers=headers,
                json=payload,
                timeout=settings.request_timeout_s,
            )
            if resp.status_code in {429, 500, 502, 503, 504}:
                raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            if resp.status_code >= 400:
                raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:500]}")
            return resp.json()
        except (requests.Timeout, requests.ConnectionError, ProviderError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 >= settings.max_retries:
                break
            time.sleep(1.5 * (2**attempt))
    raise ProviderError(str(last_error or "外部 API 调用失败"))


def _request_binary(method: str, url: str, *, headers: dict[str, str], payload: dict[str, Any]) -> tuple[bytes, str]:
    last_error: Exception | None = None
    for attempt in range(settings.max_retries):
        try:
            resp = requests.request(
                method,
                url,
                headers=headers,
                json=payload,
                timeout=settings.request_timeout_s,
            )
            if resp.status_code in {429, 500, 502, 503, 504}:
                raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            if resp.status_code >= 400:
                raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:500]}")
            ctype = resp.headers.get("content-type", "")
            if "application/json" in ctype:
                data = resp.json()
                audio = _extract_audio_from_json(data)
                if audio:
                    return audio, ".mp3"
                raise ProviderError(f"TTS 返回 JSON 但未找到音频字段: {str(data)[:500]}")
            return resp.content, ".mp3"
        except (requests.Timeout, requests.ConnectionError, ProviderError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 >= settings.max_retries:
                break
            time.sleep(1.5 * (2**attempt))
    raise ProviderError(str(last_error or "TTS 调用失败"))


def _extract_audio_from_json(data: dict[str, Any]) -> bytes | None:
    candidates = [
        data.get("audio"),
        data.get("data"),
        data.get("output", {}).get("audio"),
        data.get("output", {}).get("audio_data"),
        data.get("output", {}).get("data"),
    ]
    for item in candidates:
        if isinstance(item, str) and item:
            raw = item.split(",", 1)[-1] if item.startswith("data:") else item
            try:
                return base64.b64decode(raw)
            except Exception:
                continue
    url = data.get("output", {}).get("url") or data.get("url")
    if isinstance(url, str) and url.startswith("http"):
        r = requests.get(url, timeout=settings.request_timeout_s)
        r.raise_for_status()
        return r.content
    return None


def transcribe_audio(audio_path: Path) -> str:
    if settings.enable_mock_when_no_key and not settings.dashscope_api_key:
        return "我想把这句话变成家乡话，让更多年轻人听见方言的味道。"

    audio_url = media_url_to_public(public_url_for(audio_path))
    if not audio_url.startswith("http"):
        raise ProviderError("ASR 需要 PUBLIC_BASE_URL 指向公网可访问地址，本地 localhost 无法被云端拉取音频")

    payload = {
        "model": settings.asr_model,
        "input": {"file_urls": [audio_url]},
        "parameters": {"channel_id": [0], "language_hints": ["zh", "yue", "nan"]},
    }
    data = _request_json("POST", settings.asr_base_url, headers=_headers(), payload=payload)
    task_id = data.get("output", {}).get("task_id") or data.get("task_id")
    if task_id:
        return _poll_asr_task(task_id)
    text = _extract_text(data)
    if text:
        return text
    raise ProviderError(f"ASR 未返回可用文本: {str(data)[:500]}")


def _poll_asr_task(task_id: str) -> str:
    url = f"{settings.asr_base_url}/{task_id}"
    for _ in range(40):
        data = _request_json("GET", url, headers=_headers(), payload={})
        status = data.get("output", {}).get("task_status") or data.get("task_status")
        if status in {"SUCCEEDED", "SUCCESS", "COMPLETED"}:
            text = _extract_text(data)
            if text:
                return text
            raise ProviderError(f"ASR 任务完成但未找到文本: {str(data)[:500]}")
        if status in {"FAILED", "CANCELED"}:
            raise ProviderError(f"ASR 任务失败: {str(data)[:500]}")
        time.sleep(2)
    raise ProviderError("ASR 任务超时")


def _extract_text(data: Any) -> str:
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        parts = [_extract_text(x) for x in data]
        return " ".join(x for x in parts if x).strip()
    if not isinstance(data, dict):
        return ""
    for key in ("text", "transcript", "sentence", "content"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    for key in ("output", "results", "sentences", "transcripts"):
        val = data.get(key)
        text = _extract_text(val)
        if text:
            return text
    return ""


def rewrite_to_dialect(source_text: str, dialect: str) -> dict[str, str]:
    dialect_names = {
        "cantonese": "粤语/广东话",
        "sichuanese": "四川话/川渝口语",
        "hokkien": "闽南话/泉漳厦口语",
    }
    if settings.enable_mock_when_no_key and not settings.qwen_llm_api_key:
        demo = {
            "cantonese": "我想将呢句话变成家乡话，等更多后生仔听到方言嘅味道。",
            "sichuanese": "我想把这句话摆成家乡话，让更多年轻人听得到方言那个味道。",
            "hokkien": "我想共这句话变做咱厝话，予较济少年人听着方言的滋味。",
        }
        return {"dialect_text": demo[dialect], "pronunciation_note": "离线演示文本，真实部署会由 Qwen LLM 生成。"}

    url = f"{settings.qwen_llm_base_url.rstrip('/')}/chat/completions"
    prompt = f"""
你是中国方言口语化改写专家。把用户文本改写为自然、可朗读、适合 TTS 的{dialect_names[dialect]}。
要求：
1. 保留原意，不扩写事实。
2. 输出必须像本地人自然讲话，不要只是普通话换几个词。
3. 避免生僻字堆砌，必要时使用常见汉字表达方言语气。
4. 返回 JSON：{{"dialect_text": "...", "pronunciation_note": "简短说明"}}。

用户文本：{source_text}
""".strip()
    payload = {
        "model": settings.qwen_llm_model,
        "messages": [
            {"role": "system", "content": "你只输出合法 JSON，不输出 Markdown。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.35,
    }
    data = _request_json("POST", url, headers=_headers(settings.qwen_llm_api_key), payload=payload)
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = {"dialect_text": content, "pronunciation_note": "模型未返回 JSON，已按纯文本处理。"}
    return {
        "dialect_text": str(parsed.get("dialect_text") or source_text).strip(),
        "pronunciation_note": str(parsed.get("pronunciation_note") or "").strip(),
    }


def enroll_voice(audio_path: Path, cache_voice_id: str | None = None) -> str:
    if cache_voice_id:
        return cache_voice_id
    if settings.enable_mock_when_no_key and not settings.dashscope_api_key:
        return "mock_voice_id"
    audio_url = media_url_to_public(public_url_for(audio_path))
    if not audio_url.startswith("http"):
        raise ProviderError("音色克隆注册需要 PUBLIC_BASE_URL 指向公网可访问的参考音频")
    payload = {
        "model": settings.qwen_voice_enrollment_model,
        "input": {
            "audio_url": audio_url,
            "target_model": settings.qwen_voice_target_model,
        },
        "parameters": {
            "target_model": settings.qwen_voice_target_model,
        },
    }
    data = _request_json("POST", settings.qwen_voice_enrollment_url, headers=_headers(), payload=payload)
    voice_id = (
        data.get("output", {}).get("voice")
        or data.get("output", {}).get("voice_id")
        or data.get("voice")
        or data.get("voice_id")
    )
    if not voice_id:
        raise ProviderError(f"音色注册未返回 voice_id: {str(data)[:500]}")
    return str(voice_id)


def synthesize(text: str, output_path: Path, *, voice: str, model: str | None = None) -> str:
    if settings.enable_mock_when_no_key and not settings.dashscope_api_key:
        output_path.write_bytes(b"")
        return public_url_for(output_path)

    model = model or settings.qwen_tts_model
    base = settings.qwen_tts_base_url.rstrip("/")
    if "/compatible-mode/" in base:
        url = f"{base}/audio/speech"
        payload = {"model": model, "input": text, "voice": voice, "response_format": "mp3"}
        binary, ext = _request_binary("POST", url, headers=_headers(), payload=payload)
    else:
        url = f"{base}/api/v1/services/aigc/multimodal-generation/generation"
        payload = {
            "model": model,
            "input": {"text": text, "voice": voice},
            "parameters": {"format": "mp3"},
        }
        binary, ext = _request_binary("POST", url, headers=_headers(), payload=payload)
    final_path = output_path.with_suffix(ext)
    atomic_write_bytes(final_path, binary)
    return public_url_for(final_path)

