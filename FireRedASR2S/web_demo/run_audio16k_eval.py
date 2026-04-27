from __future__ import annotations

import json
from pathlib import Path

from web_demo.client import run_pipeline_from_audio


def main() -> None:
    audio_dir = Path("runtime_data/audio_16k")
    out = Path("runtime_data/step2_output/results_audio16k_web_pipeline.jsonl")
    rows = []
    for p in sorted(audio_dir.glob("*.wav")):
        result = run_pipeline_from_audio(
            str(p),
            enable_punc=True,
            enable_rewrite=True,
            enable_tts=True,
            voice="Kiki",
            segment_max_len=28,
        )
        rows.append(
            {
                "uttid": p.stem,
                "asr_text": result["asr"].get("punc_text") or result["asr"].get("text", ""),
                "reviewed_text": result["review"].get("asr_reviewed_text", ""),
                "yue_text": (result["rewrite"] or {}).get("dialect_text", ""),
                "tts_wav_path": (result["tts"] or {}).get("wav_path", ""),
                "tts_error": (result["tts"] or {}).get("error", ""),
                "trace_id": result["trace_id"],
                "total_latency_ms": result["total_latency_ms"],
            }
        )

    out.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows), encoding="utf-8")
    print(
        json.dumps(
            {
                "total": len(rows),
                "tts_ok": sum(1 for x in rows if not x["tts_error"]),
                "tts_failed": sum(1 for x in rows if x["tts_error"]),
                "out": str(out),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
