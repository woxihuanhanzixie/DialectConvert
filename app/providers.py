from __future__ import annotations

import base64
import json
import shutil
import subprocess
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


def _async_headers(api_key: str | None = None) -> dict[str, str]:
    headers = _headers(api_key)
    headers["X-DashScope-Async"] = "enable"
    return headers


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


def _find_first_url(data: Any) -> str | None:
    if isinstance(data, str) and data.startswith("http"):
        return data
    if isinstance(data, list):
        for item in data:
            found = _find_first_url(item)
            if found:
                return found
        return None
    if isinstance(data, dict):
        for key in ("url", "audio_url", "file_url"):
            value = data.get(key)
            if isinstance(value, str) and value.startswith("http"):
                return value
        for value in data.values():
            found = _find_first_url(value)
            if found:
                return found
    return None


def _download_audio_url(url: str) -> bytes:
    last_error: Exception | None = None
    for attempt in range(settings.max_retries):
        try:
            resp = requests.get(url, timeout=settings.request_timeout_s)
            if resp.status_code in {429, 500, 502, 503, 504}:
                raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            resp.raise_for_status()
            return resp.content
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError, ProviderError) as exc:
            last_error = exc
            if attempt + 1 >= settings.max_retries:
                break
            time.sleep(1.5 * (2**attempt))
    raise ProviderError(str(last_error or "audio download failed"))


def _request_async_task(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = _request_json("POST", url, headers=_async_headers(), payload=payload)
    task_id = data.get("output", {}).get("task_id") or data.get("task_id")
    if not task_id:
        return data
    task_url = f"{settings.dashscope_task_url.rstrip('/')}/{task_id}"
    for _ in range(80):
        task = _request_json("GET", task_url, headers=_headers(), payload={})
        status = task.get("output", {}).get("task_status") or task.get("task_status")
        if status in {"SUCCEEDED", "SUCCESS", "COMPLETED"}:
            return task
        if status in {"FAILED", "CANCELED", "UNKNOWN"}:
            raise ProviderError(f"异步语音任务失败: {str(task)[:500]}")
        time.sleep(2)
    raise ProviderError("异步语音任务超时")


def _audio_for_voice_clone(audio_path: Path) -> Path:
    if audio_path.suffix.lower() in {".wav", ".mp3", ".m4a"}:
        return audio_path
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ProviderError("当前音频格式需要 ffmpeg 转码，请上传 wav/mp3/m4a 或在服务器安装 ffmpeg")
    converted = audio_path.with_suffix(".mp3")
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(audio_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "24000",
        "-b:a",
        "128k",
        str(converted),
    ]
    proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
    if proc.returncode != 0 or not converted.exists() or converted.stat().st_size == 0:
        raise ProviderError(f"音频转码失败，请换 wav/mp3/m4a 文件: {proc.stderr[-300:]}")
    return converted


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
    data = _request_json("POST", settings.asr_base_url, headers=_async_headers(), payload=payload)
    task_id = data.get("output", {}).get("task_id") or data.get("task_id")
    if task_id:
        return _poll_asr_task(task_id)
    text = _extract_text(data)
    if text:
        return text
    raise ProviderError(f"ASR 未返回可用文本: {str(data)[:500]}")


def _poll_asr_task(task_id: str) -> str:
    url = f"{settings.dashscope_task_url.rstrip('/')}/{task_id}"
    for _ in range(40):
        data = _request_json("GET", url, headers=_headers(), payload={})
        status = data.get("output", {}).get("task_status") or data.get("task_status")
        if status in {"SUCCEEDED", "SUCCESS", "COMPLETED"}:
            text = _extract_text(data)
            if text:
                return text
            transcription_url = _find_transcription_url(data)
            if transcription_url:
                transcript = requests.get(transcription_url, timeout=settings.request_timeout_s)
                transcript.raise_for_status()
                text = _extract_text(transcript.json())
                if text:
                    return text
            raise ProviderError(f"ASR 任务完成但未找到文本: {str(data)[:500]}")
        if status in {"FAILED", "CANCELED"}:
            raise ProviderError(f"ASR 任务失败: {str(data)[:500]}")
        time.sleep(2)
    raise ProviderError("ASR 任务超时")


def _find_transcription_url(data: Any) -> str | None:
    if isinstance(data, list):
        for item in data:
            found = _find_transcription_url(item)
            if found:
                return found
    if isinstance(data, dict):
        value = data.get("transcription_url")
        if isinstance(value, str) and value.startswith("http"):
            return value
        for item in data.values():
            found = _find_transcription_url(item)
            if found:
                return found
    return None


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


def analyze_expression(source_text: str) -> dict[str, str]:
    """Restore punctuation and derive a compact emotion/prosody cue for TTS."""
    clean_text = " ".join(source_text.split()).strip()
    if not clean_text:
        return {
            "display_text": "",
            "emotion_label": "自然",
            "prosody_instruction": "自然口语，有轻微起伏",
        }

    fallback_label = _heuristic_emotion_label(clean_text)
    fallback = {
        "display_text": _ensure_sentence_punctuation(clean_text, fallback_label),
        "emotion_label": fallback_label,
        "prosody_instruction": _prosody_for_emotion(fallback_label),
    }
    if settings.enable_mock_when_no_key and not settings.qwen_llm_api_key:
        return fallback

    url = f"{settings.qwen_llm_base_url.rstrip('/')}/chat/completions"
    prompt = f"""
你是中文口语转写整理与语音情感标注专家。请只根据用户原文恢复适合朗读的标点，并判断说话情绪。
要求：
1. 不改写事实，不扩写内容。
2. display_text 必须是带标点的原意文本。
3. emotion_label 用 2-6 个汉字，例如：自然、开心、焦急、惊讶、委屈、严肃、害怕。
4. prosody_instruction 用 8-18 个汉字，描述 TTS 语气节奏，例如：语气焦急，尾音略上扬。
5. 返回 JSON：{{"display_text":"...","emotion_label":"...","prosody_instruction":"..."}}。

用户原文：{clean_text}
""".strip()
    payload = {
        "model": settings.qwen_llm_model,
        "messages": [
            {"role": "system", "content": "你只输出合法 JSON，不输出 Markdown。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    try:
        data = _request_json("POST", url, headers=_headers(settings.qwen_llm_api_key), payload=payload)
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        parsed = json.loads(content)
    except (ProviderError, json.JSONDecodeError, KeyError, TypeError) as exc:
        fallback["prosody_instruction"] = f'{fallback["prosody_instruction"]}；情感分析回退'
        return fallback

    display_text = str(parsed.get("display_text") or fallback["display_text"]).strip()
    emotion_label = _short_text(parsed.get("emotion_label"), fallback_label, 8)
    prosody_instruction = _short_text(
        parsed.get("prosody_instruction"),
        _prosody_for_emotion(emotion_label),
        22,
    )
    return {
        "display_text": _ensure_sentence_punctuation(display_text, emotion_label),
        "emotion_label": emotion_label,
        "prosody_instruction": prosody_instruction,
    }


def _short_text(value: Any, default: str, max_chars: int) -> str:
    text = str(value or default).strip()
    return text[:max_chars] if len(text) > max_chars else text


def _heuristic_emotion_label(text: str) -> str:
    if any(word in text for word in ("吓", "恐怖", "害怕", "怕", "糟了", "完了")):
        return "紧张"
    if any(word in text for word in ("好大", "特别", "太", "真的", "居然")) or "!" in text or "！" in text:
        return "惊讶"
    if any(word in text for word in ("开心", "高兴", "喜欢", "太好了", "哈哈")):
        return "开心"
    if any(word in text for word in ("急", "赶", "快点", "马上", "等一下")):
        return "焦急"
    if any(word in text for word in ("难过", "委屈", "失望", "唉")):
        return "委屈"
    return "自然"


def _prosody_for_emotion(emotion_label: str) -> str:
    mapping = {
        "开心": "语气明亮，节奏轻快",
        "惊讶": "语气夸张，尾音上扬",
        "紧张": "语气紧张，节奏稍快",
        "焦急": "语气焦急，停顿更短",
        "委屈": "语气低落，尾音放轻",
        "严肃": "语气沉稳，停顿清晰",
        "害怕": "语气发紧，音量略低",
    }
    return mapping.get(emotion_label, "自然口语，有轻微起伏")


def _ensure_sentence_punctuation(text: str, emotion_label: str) -> str:
    text = text.strip()
    if not text:
        return text
    if text[-1] in "。！？!?":
        return text
    if emotion_label in {"惊讶", "开心", "紧张", "焦急"}:
        return f"{text}！"
    return f"{text}。"


def rewrite_to_dialect(source_text: str, dialect: str, expression: dict[str, str] | None = None) -> dict[str, str]:
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
    emotion_note = ""
    if expression:
        emotion_note = (
            f"\n原句情绪：{expression.get('emotion_label', '自然')}。"
            f"\n朗读语调：{expression.get('prosody_instruction', '自然口语，有轻微起伏')}。"
        )
    prompt = f"""
你是中国方言口语化改写专家。把用户文本改写为自然、可朗读、适合 TTS 的{dialect_names[dialect]}。
要求：
1. 保留原意，不扩写事实。
2. 输出必须像本地人自然讲话，不要只是普通话换几个词。
3. 保留原句标点承载的停顿、惊讶、焦急、开心或低落等情绪。
4. 避免生僻字堆砌，必要时使用常见汉字表达方言语气。
5. 返回 JSON：{{"dialect_text": "...", "pronunciation_note": "简短说明"}}。

用户文本：{source_text}{emotion_note}
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
    audio_path = _audio_for_voice_clone(audio_path)
    audio_url = media_url_to_public(public_url_for(audio_path))
    if not audio_url.startswith("http"):
        raise ProviderError("音色克隆注册需要 PUBLIC_BASE_URL 指向公网可访问的参考音频")
    payload = {
        "model": settings.qwen_voice_enrollment_model,
        "input": {
            "action": "create_voice",
            "target_model": settings.qwen_voice_target_model,
            "prefix": f"dc{int(time.time()) % 100000000}",
            "url": audio_url,
            "audio_url": audio_url,
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


def synthesize(
    text: str,
    output_path: Path,
    *,
    voice: str,
    model: str | None = None,
    instruction: str | None = None,
    language_hint: str = "zh",
) -> str:
    if settings.enable_mock_when_no_key and not settings.dashscope_api_key:
        output_path.write_bytes(b"")
        return public_url_for(output_path)

    model = model or settings.qwen_tts_model
    base = settings.qwen_tts_base_url.rstrip("/")
    if "/compatible-mode/" in base:
        base = "https://dashscope.aliyuncs.com"
    url = f"{base}/api/v1/services/audio/tts/SpeechSynthesizer"
    payload = {
        "model": model,
        "input": {
            "text": text,
            "voice": voice,
            "format": "mp3",
            "sample_rate": 24000,
            "language_hints": [language_hint],
        },
    }
    if instruction:
        payload["input"]["instruction"] = instruction
    data = _request_json("POST", url, headers=_headers(), payload=payload)
    audio = _extract_audio_from_json(data)
    if audio:
        binary, ext = audio, ".mp3"
    else:
        audio_url = _find_first_url(data)
        if not audio_url:
            raise ProviderError(f"TTS 未返回音频 URL: {str(data)[:500]}")
        binary, ext = _download_audio_url(audio_url), ".mp3"
    final_path = output_path.with_suffix(ext)
    atomic_write_bytes(final_path, binary)
    return public_url_for(final_path)
