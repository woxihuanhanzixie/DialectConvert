from __future__ import annotations

import argparse
import hashlib
import json
import types
import sys
import time
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run OpenVoice tone color conversion for Demo1.")
    parser.add_argument("--teacher-wav", required=True)
    parser.add_argument("--ref-audio", required=True)
    parser.add_argument("--out-wav", required=True)
    parser.add_argument("--openvoice-repo", required=True)
    parser.add_argument("--converter-dir", default="")
    parser.add_argument("--cache-dir", default="")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--message", default="demo1")
    return parser.parse_args()


def _file_sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _resolve_device(requested: str) -> str:
    import torch

    value = (requested or "auto").strip().lower()
    if value in {"", "auto"}:
        return "cuda:0" if torch.cuda.is_available() else "cpu"
    if value.startswith("cuda") and not torch.cuda.is_available():
        return "cpu"
    return requested


def _load_embedding(cache_path: Path, device: str):
    import torch

    if cache_path.exists():
        return torch.load(str(cache_path), map_location=device)
    return None


def main() -> int:
    args = _parse_args()
    t0 = time.perf_counter()
    teacher_wav = Path(args.teacher_wav).resolve()
    ref_audio = Path(args.ref_audio).resolve()
    out_wav = Path(args.out_wav).resolve()
    openvoice_repo = Path(args.openvoice_repo).resolve()
    converter_dir = Path(args.converter_dir).resolve() if args.converter_dir else (openvoice_repo / "checkpoints_v2" / "converter")
    cache_dir = Path(args.cache_dir).resolve() if args.cache_dir else (Path(__file__).resolve().parent / "cache" / "se")

    if not teacher_wav.exists():
        raise FileNotFoundError(f"Missing teacher wav: {teacher_wav}")
    if not ref_audio.exists():
        raise FileNotFoundError(f"Missing reference audio: {ref_audio}")
    if not converter_dir.exists():
        raise FileNotFoundError(f"Missing converter dir: {converter_dir}")

    vendor_dir = openvoice_repo / "_vendor"
    if str(openvoice_repo) not in sys.path:
        sys.path.append(str(openvoice_repo))
    if vendor_dir.exists() and str(vendor_dir) not in sys.path:
        sys.path.append(str(vendor_dir))

    class _DummyWatermarkModel:
        def to(self, _device):
            return self

        def encode(self, signal, _message_tensor):
            return signal

        def decode(self, signal):
            return signal

    wavmark_stub = types.ModuleType("wavmark")
    wavmark_stub.load_model = lambda: _DummyWatermarkModel()
    sys.modules["wavmark"] = wavmark_stub

    import torch
    from openvoice.api import ToneColorConverter

    device = _resolve_device(args.device)
    config_path = converter_dir / "config.json"
    checkpoint_path = converter_dir / "checkpoint.pth"
    if not config_path.exists():
        raise FileNotFoundError(f"Missing OpenVoice config: {config_path}")
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Missing OpenVoice checkpoint: {checkpoint_path}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    out_wav.parent.mkdir(parents=True, exist_ok=True)

    src_cache = cache_dir / f"src_{_file_sha1(teacher_wav)}.pth"
    tgt_cache = cache_dir / f"tgt_{_file_sha1(ref_audio)}.pth"

    converter = ToneColorConverter(str(config_path), device=device)
    converter.watermark_model = None
    converter.load_ckpt(str(checkpoint_path))

    src_se = _load_embedding(src_cache, device)
    if src_se is None:
        src_se = converter.extract_se(str(teacher_wav), se_save_path=str(src_cache))

    tgt_se = _load_embedding(tgt_cache, device)
    if tgt_se is None:
        tgt_se = converter.extract_se(str(ref_audio), se_save_path=str(tgt_cache))

    convert_t0 = time.perf_counter()
    converter.convert(
        audio_src_path=str(teacher_wav),
        src_se=src_se,
        tgt_se=tgt_se,
        output_path=str(out_wav),
        message=args.message,
    )
    result = {
        "ok": True,
        "provider": "openvoice",
        "wav_path": str(out_wav),
        "teacher_wav_path": str(teacher_wav),
        "reference_wav_path": str(ref_audio),
        "converter_dir": str(converter_dir),
        "device": device,
        "source_embedding_cache": str(src_cache),
        "target_embedding_cache": str(tgt_cache),
        "convert_latency_ms": round((time.perf_counter() - convert_t0) * 1000, 2),
        "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        "audio_bytes": out_wav.stat().st_size if out_wav.exists() else 0,
    }
    sys.stdout.write(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        payload = {
            "ok": False,
            "provider": "openvoice",
            "error": str(exc),
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False))
        raise SystemExit(1)
