from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .config import Step2Config
from .rewrite import rewrite_to_cantonese
from .tn import prepare_text_for_llm, split_sentences
from .tts import synthesize_qwen_tts


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Step2 local demo: TN + Cantonese rewrite (LLM) + Qwen TTS.",
    )
    p.add_argument("--from_asr_txt", default="runtime_data/asr_output/demo1_asr_result_16k_rerun.txt")
    p.add_argument("--manual_txt", default="runtime_data/step2_input/manual_10.txt")
    p.add_argument("--output_jsonl", default="")
    p.add_argument("--provider", default="", choices=["", "deepseek", "qwen"])
    p.add_argument("--skip_rewrite", type=int, default=0, choices=[0, 1])
    p.add_argument("--enable_tts", type=int, default=0, choices=[0, 1])
    p.add_argument("--segment_max_len", type=int, default=28)
    p.add_argument("--max_samples", type=int, default=0, help="0 means all")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = Step2Config.from_env()
    if args.provider:
        cfg.provider = args.provider

    samples = []
    samples.extend(load_asr_txt(args.from_asr_txt))
    samples.extend(load_plain_txt(args.manual_txt, prefix="manual"))
    if args.max_samples > 0:
        samples = samples[: args.max_samples]

    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_jsonl or str(cfg.output_dir / "results.jsonl")

    rows = []
    for uttid, text in samples:
        tn_text = prepare_text_for_llm(text)
        segments = split_sentences(tn_text, max_len=args.segment_max_len)
        if not segments:
            segments = [tn_text]
        if args.skip_rewrite == 1:
            rw = {
                "ok": True,
                "yue_text": "。".join(segments),
                "degrade_mode": True,
                "llm_model": "skip_rewrite",
                "llm_latency_ms": 0.0,
                "llm_error": "",
            }
        else:
            rw = rewrite_batch_segments(segments, cfg)
        tts_info = {"ok": True, "wav_path": "", "error": ""}
        if args.enable_tts == 1:
            wav_path = cfg.output_dir / "audio" / f"{uttid}.wav"
            tts_info = synthesize_qwen_tts(str(rw["yue_text"]), wav_path, cfg)
        rows.append(
            {
                "uttid": uttid,
                "source_text": text,
                "tn_text": tn_text,
                "rewrite_segments": segments,
                "yue_text": rw["yue_text"],
                "degrade_mode": rw["degrade_mode"],
                "llm_model": rw["llm_model"],
                "llm_latency_ms": rw["llm_latency_ms"],
                "llm_error": rw["llm_error"],
                "provider": cfg.provider,
                "tts_enabled": args.enable_tts == 1,
                "tts_model": cfg.qwen_tts_model,
                "tts_voice": cfg.qwen_tts_voice,
                "tts_language_type": cfg.qwen_tts_language_type,
                "tts_wav_path": tts_info["wav_path"],
                "tts_audio_url": tts_info.get("audio_url", ""),
                "tts_expires_at": tts_info.get("expires_at", ""),
                "tts_error": tts_info["error"],
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        )

    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(
        json.dumps(
            {
                "num_samples": len(rows),
                "provider": cfg.provider,
                "output_jsonl": out,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def rewrite_batch_segments(segments: list[str], cfg: Step2Config) -> dict[str, object]:
    texts: list[str] = []
    total_latency = 0.0
    degrade = False
    model = ""
    errors: list[str] = []

    for seg in segments:
        rw = rewrite_to_cantonese(seg, cfg)
        texts.append(str(rw["yue_text"]).rstrip("。"))
        total_latency += float(rw["llm_latency_ms"])
        degrade = degrade or bool(rw["degrade_mode"])
        model = str(rw["llm_model"])
        if rw["llm_error"]:
            errors.append(str(rw["llm_error"]))

    return {
        "yue_text": "。".join([t for t in texts if t]).strip() + ("。" if texts else ""),
        "degrade_mode": degrade,
        "llm_model": model or "unknown",
        "llm_latency_ms": round(total_latency, 2),
        "llm_error": " | ".join(errors),
    }


def load_asr_txt(path: str) -> list[tuple[str, str]]:
    p = Path(path)
    if not p.exists():
        return []
    rows: list[tuple[str, str]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if "\t" in line:
            uttid, text = line.split("\t", 1)
        else:
            uttid, text = f"asr_{len(rows)+1:04d}", line
        rows.append((uttid, text.strip()))
    return rows


def load_plain_txt(path: str, prefix: str) -> list[tuple[str, str]]:
    p = Path(path)
    if not p.exists():
        return []
    rows: list[tuple[str, str]] = []
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        rows.append((f"{prefix}_{i:04d}", text))
    return rows


if __name__ == "__main__":
    main()
