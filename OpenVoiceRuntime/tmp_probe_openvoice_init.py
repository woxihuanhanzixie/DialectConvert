import sys, time
openvoice_repo = r'd:\Competition\FireRedASR2S\runtime_data\models\OpenVoice'
vendor_dir = openvoice_repo + r'\_vendor'
if openvoice_repo not in sys.path:
    sys.path.append(openvoice_repo)
if vendor_dir not in sys.path:
    sys.path.append(vendor_dir)

import torch
print('TORCH_FILE', torch.__file__, flush=True)
print('CUDA_AVAILABLE_BEFORE', torch.cuda.is_available(), flush=True)

t=time.perf_counter()
from openvoice.api import ToneColorConverter
print('IMPORT_OPENVOICE_API_MS', round((time.perf_counter()-t)*1000,2), flush=True)
print('CUDA_AVAILABLE_AFTER', torch.cuda.is_available(), flush=True)
cfg = r'd:\Competition\FireRedASR2S\runtime_data\models\OpenVoice\checkpoints_v2\converter\config.json'
t=time.perf_counter()
obj = ToneColorConverter(cfg, device='cuda:0')
print('INIT_CONVERTER_MS', round((time.perf_counter()-t)*1000,2), flush=True)
print('OK', flush=True)
