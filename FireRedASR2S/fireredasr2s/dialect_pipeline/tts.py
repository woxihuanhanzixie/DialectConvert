from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .config import Step2Config
from .voice_clone import convert_voice_from_teacher, create_qwen_voice, synthesize_local_clone, synthesize_qwen_vc


def synthesize_standard_tts(text: str, out_wav: Path, cfg: Step2Config) -> dict[str, object]:
    if not cfg.qwen_tts_api_key:
        return {
            "ok": False,
            "wav_path": "",
            "audio_url": "",
            "expires_at": "",
            "error": "Missing QWEN_TTS_API_KEY or DASHSCOPE_API_KEY",
        }

    payload = {
        "model": cfg.qwen_tts_model,
        "input": {
            "text": text,
            "voice": cfg.qwen_tts_voice,
            "language_type": cfg.qwen_tts_language_type,
        },
    }
    instruction_mode_active = False
    if "instruct" in cfg.qwen_tts_model and cfg.tts_style_instructions:
        payload["instructions"] = cfg.tts_style_instructions
        instruction_mode_active = True

    req = urllib.request.Request(
        url=f"{cfg.qwen_tts_base_url}{cfg.qwen_tts_path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {cfg.qwen_tts_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=cfg.timeout_s) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        audio_url = _get_in(data, "output", "audio", "url")
        expires_at = str(_get_in(data, "output", "audio", "expires_at") or "")
        if not audio_url:
            return {
                "ok": False,
                "wav_path": "",
                "audio_url": "",
                "expires_at": "",
                "error": f"Missing output.audio.url in TTS response: {raw[:500]}",
                "instruction_mode_active": instruction_mode_active,
                "tts_style_instructions": cfg.tts_style_instructions,
            }

        out_wav.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(str(audio_url), timeout=cfg.timeout_s) as audio_resp:
            out_wav.write_bytes(audio_resp.read())
        return {
            "ok": True,
            "wav_path": str(out_wav),
            "audio_url": str(audio_url),
            "expires_at": expires_at,
            "error": "",
            "instruction_mode_active": instruction_mode_active,
            "tts_style_instructions": cfg.tts_style_instructions,
        }
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        return {
            "ok": False,
            "wav_path": "",
            "audio_url": "",
            "expires_at": "",
            "error": f"HTTP {e.code}: {detail}",
            "instruction_mode_active": instruction_mode_active,
            "tts_style_instructions": cfg.tts_style_instructions,
        }
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "wav_path": "",
            "audio_url": "",
            "expires_at": "",
            "error": str(e),
            "instruction_mode_active": instruction_mode_active,
            "tts_style_instructions": cfg.tts_style_instructions,
        }


def synthesize_voice_clone(
    text: str,
    out_wav: Path,
    cfg: Step2Config,
    *,
    ref_audio_path: str | Path,
    preferred_name: str,
) -> dict[str, object]:
    if not cfg.qwen_tts_api_key:
        return {
            "ok": False,
            "wav_path": "",
            "audio_url": "",
            "expires_at": "",
            "voice": "",
            "error": "Missing QWEN_TTS_API_KEY or DASHSCOPE_API_KEY",
        }
    try:
        if cfg.voice_clone_provider == "qwen_vc":
            voice_info = create_qwen_voice(ref_audio_path, cfg, preferred_name=preferred_name)
            result = synthesize_qwen_vc(text, voice_info["voice"], out_wav, cfg)
            return {
                "ok": True,
                "wav_path": result["wav_path"],
                "audio_url": result["audio_url"],
                "expires_at": result["expires_at"],
                "voice": result["voice"],
                "error": "",
                "instruction_mode_active": False,
                "tts_style_instructions": cfg.tts_style_instructions,
            }
        if cfg.voice_clone_provider in {"gpt_sovits", "fish_speech"}:
            synthesize_local_clone(text, out_wav, cfg, ref_audio_path=ref_audio_path, preferred_name=preferred_name)
        return {
            "ok": False,
            "wav_path": "",
            "audio_url": "",
            "expires_at": "",
            "voice": "",
            "error": f"Unsupported voice clone provider: {cfg.voice_clone_provider}",
            "instruction_mode_active": False,
            "tts_style_instructions": cfg.tts_style_instructions,
        }
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "wav_path": "",
            "audio_url": "",
            "expires_at": "",
            "voice": "",
            "error": str(e),
            "instruction_mode_active": False,
            "tts_style_instructions": cfg.tts_style_instructions,
        }


def synthesize_gold_teacher(text: str, out_wav: Path, cfg: Step2Config) -> dict[str, object]:
    result = synthesize_standard_tts(text, out_wav, cfg)
    result["teacher_role"] = "gold_standard_pronunciation"
    result["teacher_input_text"] = text
    result["teacher_wav_path"] = result.get("wav_path", "")
    return result


def synthesize_voice_matched_from_teacher(
    teacher_wav_path: str | Path,
    ref_audio_path: str | Path,
    out_wav: Path,
    cfg: Step2Config,
    *,
    preferred_name: str,
) -> dict[str, object]:
    return convert_voice_from_teacher(
        teacher_wav_path,
        ref_audio_path,
        out_wav,
        cfg,
        preferred_name=preferred_name,
    )


def synthesize_qwen_tts(text: str, out_wav: Path, cfg: Step2Config) -> dict[str, object]:
    return synthesize_standard_tts(text, out_wav, cfg)


def synthesize_instruction_teacher(text: str, out_wav: Path, cfg: Step2Config) -> dict[str, object]:
    original_model = cfg.qwen_tts_model
    original_voice = cfg.qwen_tts_voice
    original_instructions = cfg.tts_style_instructions
    try:
        cfg.qwen_tts_model = cfg.qwen_tts_instruction_model
        cfg.qwen_tts_voice = cfg.qwen_tts_teacher_voice
        cfg.tts_style_instructions = cfg.qwen_tts_teacher_instructions
        result = synthesize_standard_tts(text, out_wav, cfg)
        result["teacher_model"] = cfg.qwen_tts_instruction_model
        result["teacher_voice"] = cfg.qwen_tts_teacher_voice
        return result
    finally:
        cfg.qwen_tts_model = original_model
        cfg.qwen_tts_voice = original_voice
        cfg.tts_style_instructions = original_instructions


def _get_in(data: dict[str, Any], *keys: str) -> Any:
    cur: Any = data
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur
