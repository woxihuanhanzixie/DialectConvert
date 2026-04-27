# -*- coding: utf-8 -*-
import json
from pathlib import Path
from web_demo.client import run_pipeline_from_audio

result = run_pipeline_from_audio(
    r'c:\Users\34005\Desktop\大赛\FireRedASR2S\runtime_data\audio_16k\20260423_214727.wav',
    speaker_ref_audio='',
    enable_punc=True,
    enable_rewrite=True,
    enable_tts=True,
    voice='Kiki',
    segment_max_len=28,
    voice_clone_enabled=True,
    voice_clone_provider='openvoice',
)
out = Path(r'c:\Users\34005\Desktop\大赛\FireRedASR2S\runtime_data\step2_output\debug_openvoice_full_214727.json')
out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(out)
print(json.dumps({
    'recommended_main_output': (result.get('tts') or {}).get('recommended_main_output'),
    'gold_teacher': ((result.get('tts') or {}).get('gold_teacher') or {}).get('wav_path'),
    'voice_matched': ((result.get('tts') or {}).get('voice_matched') or {}).get('wav_path'),
    'voice_matched_error': ((result.get('tts') or {}).get('voice_matched') or {}).get('error'),
    'legacy_text_clone': ((result.get('tts') or {}).get('legacy_text_clone') or {}).get('wav_path'),
}, ensure_ascii=False, indent=2))
