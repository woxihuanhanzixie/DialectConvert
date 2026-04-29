#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Demo1-Step1 ASR evaluation script (Windows/Linux friendly).

Usage example:
python examples_infer/asr/demo1_asr_eval.py \
  --model_dir pretrained_models/FireRedASR2-AED \
  --wav_dir examples_infer/asr/wav \
  --out_prefix examples_infer/asr/out/demo1_asr_result \
  --use_gpu 0 \
  --return_timestamp 1
"""

import argparse
import glob
import json
import os
import statistics
import sys
import time
from pathlib import Path


#保证找到项目运行的环境
def _ensure_repo_import():
    script_dir = Path(__file__).resolve().parent  #找到文件夹
    candidates = [
        Path.cwd(),
        script_dir,
        script_dir.parent,
        script_dir.parent.parent,
        script_dir.parent.parent.parent,
    ]
    for c in candidates:
        pkg_init = c / "fireredasr2s" / "__init__.py"
        if pkg_init.exists():
            if str(c) not in sys.path:
                sys.path.insert(0, str(c))
            return


_ensure_repo_import()

from fireredasr2s.fireredasr2 import FireRedAsr2, FireRedAsr2Config  # noqa: E402
#引入自己的包


def parse_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Demo1-Step1 ASR batch evaluation for FireRedASR2-AED.",
    )
    parser.add_argument(
        "--model_dir",
        default="pretrained_models/FireRedASR2-AED",
        help="Path to FireRedASR2-AED model directory.",
    )
    parser.add_argument("--wav_path", default="", help="Single wav path.")
    parser.add_argument("--wav_dir", default="", help="Directory that contains wav files.")
    parser.add_argument("--wav_scp", default="", help="Kaldi-style wav.scp (uttid wav_path).")
    parser.add_argument(
        "--out_prefix",
        default="examples_infer/asr/out/demo1_asr_result",
        help="Output file prefix. Will generate .txt and .jsonl.",
    )

    parser.add_argument("--use_gpu", type=int, default=0, choices=[0, 1])
    parser.add_argument("--use_half", type=int, default=0, choices=[0, 1])
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--beam_size", type=int, default=3)
    parser.add_argument("--nbest", type=int, default=1)
    parser.add_argument("--decode_max_len", type=int, default=300)
    parser.add_argument("--softmax_smoothing", type=float, default=1.25)
    parser.add_argument("--aed_length_penalty", type=float, default=0.6)
    parser.add_argument("--eos_penalty", type=float, default=1.0)
    parser.add_argument("--return_timestamp", type=int, default=1, choices=[0, 1])
    parser.add_argument("--sort_wav_by_name", type=int, default=1, choices=[0, 1])
    return parser.parse_args()


def load_wavs(args):
    if args.wav_path:
        wavs = [(Path(args.wav_path).stem, args.wav_path)]
    elif args.wav_scp:
        with open(args.wav_scp, "r", encoding="utf-8") as f:
            wavs = [line.strip().split(maxsplit=1) for line in f if line.strip()]
    elif args.wav_dir:
        wav_paths = glob.glob(os.path.join(args.wav_dir, "**", "*.wav"), recursive=True)
        wavs = [(Path(p).stem, p) for p in wav_paths]
    else:
        raise ValueError("Please provide one of --wav_path/--wav_dir/--wav_scp.")

    if args.sort_wav_by_name:
        wavs = sorted(wavs, key=lambda x: x[0])
    if not wavs:
        raise ValueError("No wav files found.")
    return wavs


def chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def main():
    args = parse_args()
    wavs = load_wavs(args)
    Path(args.out_prefix).parent.mkdir(parents=True, exist_ok=True)

    asr_config = FireRedAsr2Config(
        use_gpu=bool(args.use_gpu),
        use_half=bool(args.use_half),
        beam_size=args.beam_size,
        nbest=args.nbest,
        decode_max_len=args.decode_max_len,
        softmax_smoothing=args.softmax_smoothing,
        aed_length_penalty=args.aed_length_penalty,
        eos_penalty=args.eos_penalty,
        return_timestamp=bool(args.return_timestamp),
    )
    model = FireRedAsr2.from_pretrained("aed", args.model_dir, asr_config)

    all_results = []
    total_wall_time = 0.0
    for batch in chunks(wavs, max(1, args.batch_size)):
        batch_uttid = [x[0] for x in batch]
        batch_wav_path = [x[1] for x in batch]
        start = time.perf_counter()
        results = model.transcribe(batch_uttid, batch_wav_path)
        total_wall_time += time.perf_counter() - start
        if results is not None:
            all_results.extend(results)

    out_txt = args.out_prefix + ".txt"
    out_jsonl = args.out_prefix + ".jsonl"

    with open(out_txt, "w", encoding="utf-8") as f_txt, open(
        out_jsonl, "w", encoding="utf-8"
    ) as f_jsonl:
        for r in all_results:
            f_txt.write(f"{r['uttid']}\t{r.get('text', '')}\n")
            f_jsonl.write(json.dumps(r, ensure_ascii=False) + "\n")

    confs = [r.get("confidence", 0.0) for r in all_results if "confidence" in r]
    durs = [r.get("dur_s", 0.0) for r in all_results if "dur_s" in r]
    rtfs = []
    for r in all_results:
        try:
            rtfs.append(float(r.get("rtf", 0.0)))
        except Exception:
            continue

    avg_conf = statistics.mean(confs) if confs else 0.0
    avg_rtf = statistics.mean(rtfs) if rtfs else 0.0
    total_audio_s = sum(durs) if durs else 0.0

    summary = {
        "num_samples": len(all_results),
        "avg_confidence": round(avg_conf, 4),
        "avg_rtf": round(avg_rtf, 4),
        "total_audio_s": round(total_audio_s, 3),
        "total_wall_time_s": round(total_wall_time, 3),
        "output_txt": out_txt,
        "output_jsonl": out_jsonl,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
