from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from fireredasr2s import FireRedAsr2System, FireRedAsr2SystemConfig
from fireredasr2s.fireredasr2 import FireRedAsr2Config
from fireredasr2s.fireredlid import FireRedLidConfig
from fireredasr2s.fireredpunc import FireRedPuncConfig
from fireredasr2s.fireredvad import FireRedVadConfig

from .config import AsrServiceConfig


class AsrSystemEngine:
    def __init__(self, cfg: AsrServiceConfig):
        self.cfg = cfg
        self._system: FireRedAsr2System | None = None
        self._ascii_cache_root = Path(tempfile.gettempdir()) / "demo1_model_cache"

    def process_file(
        self,
        wav_path: str | Path,
        *,
        enable_vad: bool | None = None,
        enable_lid: bool | None = None,
        enable_punc: bool | None = None,
    ) -> dict[str, Any]:
        system = self._get_system(
            enable_vad=self.cfg.enable_vad_default if enable_vad is None else enable_vad,
            enable_lid=self.cfg.enable_lid_default if enable_lid is None else enable_lid,
            enable_punc=self.cfg.enable_punc_default if enable_punc is None else enable_punc,
        )
        t0 = time.perf_counter()
        result = system.process(str(wav_path), Path(wav_path).stem)
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        detected_languages: list[dict[str, Any]] = []
        for sentence in result.get("sentences", []):
            lang = sentence.get("lang")
            if not lang:
                continue
            detected_languages.append(
                {
                    "lang": lang,
                    "confidence": sentence.get("lang_confidence", 0),
                    "start_ms": sentence.get("start_ms"),
                    "end_ms": sentence.get("end_ms"),
                }
            )
        return {
            "uttid": result.get("uttid", Path(wav_path).stem),
            "text": result.get("text", ""),
            "confidence": _avg_asr_confidence(result.get("sentences", [])),
            "timestamp": None,
            "punc_text": result.get("text", ""),
            "vad_segments_ms": [list(x) for x in result.get("vad_segments_ms", [])],
            "sentences": result.get("sentences", []),
            "words": result.get("words", []),
            "detected_languages": detected_languages,
            "latency_ms": latency_ms,
        }

    def health(self) -> dict[str, Any]:
        return {
            "vad_model_dir": self.cfg.vad_model_dir,
            "lid_model_dir": self.cfg.lid_model_dir,
            "asr_model_dir": self.cfg.model_dir,
            "punc_model_dir": self.cfg.punc_model_dir,
            "system_ready": self._system is not None,
            "system_supported": self._system_supported(),
        }

    def _get_system(self, *, enable_vad: bool, enable_lid: bool, enable_punc: bool) -> FireRedAsr2System:
        if self._system is None:
            vad_config = FireRedVadConfig(
                use_gpu=self.cfg.use_gpu,
                smooth_window_size=5,
                speech_threshold=0.4,
                min_speech_frame=20,
                max_speech_frame=2000,
                min_silence_frame=10,
                merge_silence_frame=50,
                extend_speech_frame=5,
                chunk_max_frame=30000,
            )
            lid_config = FireRedLidConfig(
                use_gpu=self.cfg.use_gpu,
                use_half=self.cfg.use_half if self.cfg.use_gpu else False,
            )
            asr_config = FireRedAsr2Config(
                use_gpu=self.cfg.use_gpu,
                use_half=self.cfg.use_half,
                beam_size=self.cfg.beam_size,
                nbest=1,
                decode_max_len=0,
                softmax_smoothing=1.25,
                aed_length_penalty=0.6,
                eos_penalty=1.0,
                return_timestamp=True,
            )
            punc_config = FireRedPuncConfig(use_gpu=self.cfg.use_gpu, sentence_max_length=25)
            system_cfg = FireRedAsr2SystemConfig(
                vad_model_dir=str(self._prepare_ascii_model_dir(self.cfg.vad_model_dir)),
                lid_model_dir=str(self._prepare_ascii_model_dir(self.cfg.lid_model_dir)),
                asr_type="aed",
                asr_model_dir=str(self._prepare_ascii_model_dir(self.cfg.model_dir)),
                punc_model_dir=str(self._prepare_ascii_model_dir(self.cfg.punc_model_dir)),
                vad_config=vad_config,
                lid_config=lid_config,
                asr_config=asr_config,
                punc_config=punc_config,
                asr_batch_size=max(1, self.cfg.batch_size),
                punc_batch_size=max(1, self.cfg.batch_size),
                enable_vad=enable_vad and Path(self.cfg.vad_model_dir).exists(),
                enable_lid=enable_lid and Path(self.cfg.lid_model_dir).exists(),
                enable_punc=enable_punc,
            )
            self._system = FireRedAsr2System(system_cfg)
        return self._system

    def _prepare_ascii_model_dir(self, src_dir: str) -> Path:
        src = Path(src_dir)
        if not src.exists():
            return src
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

    def _system_supported(self) -> bool:
        return Path(self.cfg.model_dir).exists() and Path(self.cfg.punc_model_dir).exists()


def _avg_asr_confidence(sentences: list[dict[str, Any]]) -> float | None:
    values = [float(s["asr_confidence"]) for s in sentences if s.get("asr_confidence") is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 4)


_ENGINE: AsrSystemEngine | None = None


def get_asr_system_engine() -> AsrSystemEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = AsrSystemEngine(AsrServiceConfig.from_env())
    return _ENGINE
