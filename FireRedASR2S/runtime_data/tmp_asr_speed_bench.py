import json
import time
from pathlib import Path
from web_demo.client import run_pipeline_from_audio

files = [
    r"runtime_data/test_audio_wav/en/english_01.wav",
    r"runtime_data/test_audio_wav/en/english_02.wav",
    r"runtime_data/test_audio_wav/en/english_03.wav",
]
rows = []
start = time.perf_counter()
for f in files:
    t0 = time.perf_counter()
    r = run_pipeline_from_audio(
        f,
        enable_punc=True,
        enable_rewrite=False,
        enable_tts=False,
        voice_clone_enabled=False,
        voice_clone_provider="none",
    )
    rows.append({
        "file": f,
        "total_latency_ms": r.get("total_latency_ms", 0),
        "wall_ms": round((time.perf_counter() - t0) * 1000, 2),
        "asr_text": ((r.get("asr") or {}).get("punc_text") or "")[:80],
    })

out = Path(r"d:/Competition/FireRedASR2S/runtime_data/test_audio_wav/asr_speed_bench.json")
out.write_text(json.dumps({"rows": rows, "batch_wall_ms": round((time.perf_counter() - start) * 1000, 2)}, ensure_ascii=False, indent=2), encoding="utf-8")
print(str(out))
