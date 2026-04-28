from web_demo.client import run_pipeline_from_audio
from pathlib import Path
import json

result = run_pipeline_from_audio(
    r'd:\Competition\FireRedASR2S\runtime_data\audio_16k\chinese_01_16k.wav',
    speaker_ref_audio=r'd:\Competition\FireRedASR2S\runtime_data\web_demo_refs\20260423_214502_16k.wav',
    enable_punc=True,
    enable_rewrite=True,
    enable_tts=True,
    voice='Kiki',
    segment_max_len=28,
    voice_clone_enabled=True,
    voice_clone_provider='openvoice',
)
out = Path(r'd:\Competition\FireRedASR2S\runtime_data\step2_output\full_pipeline_chinese_01.json')
out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({
    'trace_id': result.get('trace_id'),
    'total_latency_ms': result.get('total_latency_ms'),
    'asr_text': ((result.get('asr') or {}).get('punc_text') or (result.get('asr') or {}).get('text')),
    'gold_teacher': (((result.get('tts') or {}).get('gold_teacher') or {}).get('wav_path')),
    'gold_teacher_error': (((result.get('tts') or {}).get('gold_teacher') or {}).get('error')),
    'voice_matched': (((result.get('tts') or {}).get('voice_matched') or {}).get('wav_path')),
    'voice_matched_error': (((result.get('tts') or {}).get('voice_matched') or {}).get('error')),
    'provider': (((result.get('tts') or {}).get('voice_matched') or {}).get('voice_clone_provider')),
}, ensure_ascii=False))
