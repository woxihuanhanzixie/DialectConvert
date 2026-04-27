# Copyright 2026 Xiaohongshu. (Author: Kaituo Xu, Kai Huang, Yan Jia, Junjie Chen, Wenpeng Li)

import os
import sys
import warnings
from importlib import import_module
warnings.filterwarnings('ignore')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # 0=ALL, 1=INFO, 2=WARNING, 3=ERROR
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

__version__ = "0.0.1"

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_PACKAGE_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


_LAZY_IMPORTS = {
    "FireRedAsr2System": ("fireredasr2s.fireredasr2system", "FireRedAsr2System"),
    "FireRedAsr2SystemConfig": ("fireredasr2s.fireredasr2system", "FireRedAsr2SystemConfig"),
    "FireRedAsr2": ("fireredasr2s.fireredasr2.asr", "FireRedAsr2"),
    "FireRedAsr2Config": ("fireredasr2s.fireredasr2.asr", "FireRedAsr2Config"),
    "FireRedVad": ("fireredasr2s.fireredvad.vad", "FireRedVad"),
    "FireRedVadConfig": ("fireredasr2s.fireredvad.vad", "FireRedVadConfig"),
    "FireRedStreamVad": ("fireredasr2s.fireredvad.stream_vad", "FireRedStreamVad"),
    "FireRedStreamVadConfig": ("fireredasr2s.fireredvad.stream_vad", "FireRedStreamVadConfig"),
    "FireRedAed": ("fireredasr2s.fireredvad.aed", "FireRedAed"),
    "FireRedAedConfig": ("fireredasr2s.fireredvad.aed", "FireRedAedConfig"),
    "FireRedLid": ("fireredasr2s.fireredlid.lid", "FireRedLid"),
    "FireRedLidConfig": ("fireredasr2s.fireredlid.lid", "FireRedLidConfig"),
    "FireRedPunc": ("fireredasr2s.fireredpunc.punc", "FireRedPunc"),
    "FireRedPuncConfig": ("fireredasr2s.fireredpunc.punc", "FireRedPuncConfig"),
}


def __getattr__(name):
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


# API
__all__ = [
    "__version__",
    "FireRedAsr2System",
    "FireRedAsr2SystemConfig",
    "FireRedAsr2",
    "FireRedAsr2Config",
    "FireRedVad",
    "FireRedVadConfig",
    "FireRedStreamVad",
    "FireRedStreamVadConfig",
    "FireRedAed",
    "FireRedAedConfig",
    "FireRedLid",
    "FireRedLidConfig",
    "FireRedPunc",
    "FireRedPuncConfig",
]
