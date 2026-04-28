from gradio_client import Client, handle_file
import json
c = Client('http://127.0.0.1:7860/')
res = c.predict(
    audio_path=handle_file(r'd:\Competition\FireRedASR2S\runtime_data\audio_16k\chinese_01_16k.wav'),
    speaker_ref_audio=handle_file(r'd:\Competition\FireRedASR2S\runtime_data\web_demo_refs\20260423_214502_16k.wav'),
    enable_punc=True,
    enable_tts=True,
    voice='Kiki',
    segment_max_len=28,
    voice_clone_enabled=True,
    voice_clone_provider='openvoice',
    api_name='/process_audio',
)
print(json.dumps({'teacher_audio': res[12], 'voice_matched_audio': res[14], 'legacy_clone_audio': res[16]}, ensure_ascii=False, indent=2))
