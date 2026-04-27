import json
from pathlib import Path

import soundfile as sf
from datasets import load_dataset

base = Path(r"d:/Competition/FireRedASR2S/runtime_data/test_audio")
for sub in ["en", "zh"]:
    (base / sub).mkdir(parents=True, exist_ok=True)

manifest = []

lang_specs = [
    ("en", "en", "english"),
    ("zh-CN", "zh", "chinese"),
]

for cv_lang, out_sub, label in lang_specs:
    ds = load_dataset("mozilla-foundation/common_voice_17_0", cv_lang, split="test", streaming=True)
    count = 0
    for row in ds:
        audio = row.get("audio") or {}
        arr = audio.get("array")
        sr = int(audio.get("sampling_rate", 0) or 0)
        sentence = (row.get("sentence") or "").strip()
        if arr is None or sr <= 0 or len(sentence) < 6:
            continue
        count += 1
        out = base / out_sub / f"{label}_{count:02d}.wav"
        sf.write(str(out), arr, sr)
        manifest.append({"lang": out_sub, "file": str(out), "text_ref": sentence[:200], "sr": sr, "seconds": round(len(arr)/sr,2)})
        if count >= 5:
            break

manifest_path = base / "manifest.json"
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"ok": True, "count": len(manifest), "manifest": str(manifest_path)}, ensure_ascii=False))
