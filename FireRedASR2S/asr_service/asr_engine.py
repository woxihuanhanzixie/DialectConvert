from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from fireredasr2s.fireredasr2 import FireRedAsr2, FireRedAsr2Config
from fireredasr2s.fireredpunc.punc import FireRedPunc, FireRedPuncConfig

from .config import AsrServiceConfig


class AsrEngine:
    def __init__(self, cfg: AsrServiceConfig):
        self.cfg = cfg
        self._asr: FireRedAsr2 | None = None
        self._punc: FireRedPunc | None = None
        self._ascii_cache_root = Path(tempfile.gettempdir()) / "demo1_model_cache"

    def transcribe_file(
        self,
        wav_path: str | Path,
        *,
        enable_punc: bool | None = None,
        return_timestamp: bool = True,
    ) -> dict[str, Any]:
        enable_punc = self.cfg.enable_punc_default if enable_punc is None else enable_punc
        model = self._get_asr(return_timestamp=return_timestamp)
        uttid = Path(wav_path).stem
        t0 = time.perf_counter()
        result = model.transcribe([uttid], [str(wav_path)])[0]
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        text = str(result.get("text", "") or "")
        punc_text = None
        if enable_punc and text:
            punc_results = self._get_punc().process([text], [uttid])
            if punc_results:
                punc_text = punc_results[0].get("punc_text")

        return {
            "uttid": result.get("uttid", uttid),
            "text": text,
            "confidence": result.get("confidence"),
            "timestamp": result.get("timestamp"),
            "punc_text": punc_text,
            "dur_s": result.get("dur_s"),
            "rtf": result.get("rtf"),
            "latency_ms": latency_ms,
        }

    def health(self) -> dict[str, Any]:
        return {
            "model_dir": self.cfg.model_dir,
            "punc_model_dir": self.cfg.punc_model_dir,
            "use_gpu": self.cfg.use_gpu,
            "asr_loaded": self._asr is not None,
            "punc_loaded": self._punc is not None,
        }

    def _get_asr(self, *, return_timestamp: bool) -> FireRedAsr2:
        if self._asr is None or self._asr.config.return_timestamp != return_timestamp:
            asr_cfg = FireRedAsr2Config(
                use_gpu=self.cfg.use_gpu,
                use_half=self.cfg.use_half,
                beam_size=self.cfg.beam_size,
                return_timestamp=return_timestamp,
            )
            model_dir = self._prepare_ascii_model_dir(self.cfg.model_dir)
            self._asr = FireRedAsr2.from_pretrained("aed", str(model_dir), asr_cfg)
        return self._asr

    def _get_punc(self) -> FireRedPunc:
        if self._punc is None:
            punc_cfg = FireRedPuncConfig(use_gpu=self.cfg.use_gpu, sentence_max_length=-1)
            model_dir = self._prepare_ascii_model_dir(self.cfg.punc_model_dir)
            self._punc = FireRedPunc.from_pretrained(str(model_dir), punc_cfg)
        return self._punc

    def _prepare_ascii_model_dir(self, src_dir: str) -> Path:
        src = Path(src_dir)
        try:
            str(src).encode("ascii")
            return src
        except UnicodeEncodeError:
            pass

        dst = self._ascii_cache_root / src.name
        ready_marker = dst / ".ready"
        if ready_marker.exists():
            return dst
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        ready_marker.write_text("ok", encoding="utf-8")
        return dst


_ENGINE: AsrEngine | None = None


def get_asr_engine() -> AsrEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = AsrEngine(AsrServiceConfig.from_env())
    return _ENGINE
