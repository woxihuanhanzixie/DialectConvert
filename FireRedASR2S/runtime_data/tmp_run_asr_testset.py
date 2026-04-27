import json
import sys
from pathlib import Path

project = Path(r"d:/Competition/FireRedASR2S")
if str(project) not in sys.path:
    sys.path.insert(0, str(project))

from web_demo.client import run_pipeline_from_audio

base = project / "runtime_data" / "test_audio"
manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
rows = []

for item in manifest:
    path = item["file"]
    res = run_pipeline_from_audio(
        path,
        enable_punc=True,
        enable_rewrite=False,
        enable_tts=False,
        voice="Kiki",
        segment_max_len=28,
        voice_clone_enabled=False,
        voice_clone_provider="none",
    )
    asr = res.get("asr") or {}
    rows.append({
        "lang": item["lang"],
        "file": path,
        "ref": item["ref"],
        "asr": asr.get("punc_text") or asr.get("text") or "",
        "asr_latency_ms": asr.get("latency_ms", 0),
    })

out = base / "asr_eval.json"
out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"ok": True, "count": len(rows), "out": str(out)}, ensure_ascii=False))
