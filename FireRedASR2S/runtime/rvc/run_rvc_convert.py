from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run lightweight RVC conversion for Demo1.")
    parser.add_argument("--teacher-wav", required=True)
    parser.add_argument("--out-wav", required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--index-path", default="")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--f0-method", default="harvest")
    parser.add_argument("--f0-up-key", type=int, default=0)
    parser.add_argument("--index-rate", type=float, default=0.5)
    parser.add_argument("--filter-radius", type=int, default=3)
    parser.add_argument("--rms-mix-rate", type=float, default=0.25)
    parser.add_argument("--protect", type=float, default=0.33)
    parser.add_argument("--version", default="v2")
    return parser.parse_args()


def _resolve_device(requested: str) -> str:
    value = (requested or "auto").strip().lower()
    if value in {"", "auto"}:
        try:
            import torch

            return "cuda:0" if torch.cuda.is_available() else "cpu"
        except Exception:  # noqa: BLE001
            return "cpu"
    return requested


def main() -> int:
    args = _parse_args()
    t0 = time.perf_counter()
    teacher_wav = Path(args.teacher_wav).resolve()
    out_wav = Path(args.out_wav).resolve()
    model_path = Path(args.model_path).resolve()
    index_path = Path(args.index_path).resolve() if args.index_path else Path()
    if not teacher_wav.exists():
        raise FileNotFoundError(f"Missing teacher wav: {teacher_wav}")
    if not model_path.exists():
        raise FileNotFoundError(f"Missing RVC model file: {model_path}")

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    device = _resolve_device(args.device)
    try:
        from rvc_python.infer import infer_file
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Missing dependency 'rvc-python'. Install with: "
            "pip install rvc-python==0.1.0"
        ) from exc

    convert_t0 = time.perf_counter()
    infer_file(
        input_path=str(teacher_wav),
        model_path=str(model_path),
        index_path=str(index_path) if index_path.exists() else "",
        device=device,
        f0method=args.f0_method,
        f0up_key=args.f0_up_key,
        opt_path=str(out_wav),
        index_rate=args.index_rate,
        filter_radius=args.filter_radius,
        resample_sr=0,
        rms_mix_rate=args.rms_mix_rate,
        protect=args.protect,
        version=args.version,
    )
    payload = {
        "ok": True,
        "provider": "rvc",
        "wav_path": str(out_wav),
        "teacher_wav_path": str(teacher_wav),
        "model_path": str(model_path),
        "index_path": str(index_path) if index_path.exists() else "",
        "device": device,
        "convert_latency_ms": round((time.perf_counter() - convert_t0) * 1000, 2),
        "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        "audio_bytes": out_wav.stat().st_size if out_wav.exists() else 0,
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        sys.stdout.write(json.dumps({"ok": False, "provider": "rvc", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
