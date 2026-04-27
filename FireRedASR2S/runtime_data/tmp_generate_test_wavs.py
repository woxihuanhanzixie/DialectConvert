import json
from pathlib import Path
import pyttsx3

base = Path(r"d:/Competition/FireRedASR2S/runtime_data/test_audio_wav")
(base / "en").mkdir(parents=True, exist_ok=True)
(base / "zh").mkdir(parents=True, exist_ok=True)

english = [
    "Hello, this is an English test sample for speech recognition.",
    "Artificial intelligence helps us build better voice applications.",
    "Today we are testing whether the ASR can recognize English correctly.",
    "Please convert this sentence into accurate text with punctuation.",
    "The weather is sunny and I will play football in the afternoon.",
]
chinese = [
    "你好，这是一个中文语音识别测试样本。",
    "我们正在验证系统对普通话的识别准确率。",
    "请把这段语音转换成带标点的文本内容。",
    "今天的天气很好，适合去户外运动。",
    "希望这次测试可以顺利通过并得到稳定结果。",
]

engine = pyttsx3.init()
voices = engine.getProperty('voices')

def pick_voice(keyword: str):
    k = keyword.lower()
    for v in voices:
        txt = f"{v.id} {getattr(v,'name','')} {getattr(v,'languages','')}".lower()
        if k in txt:
            return v.id
    return None

v_en = pick_voice('zira') or pick_voice('en-us') or (voices[0].id if voices else None)
v_zh = pick_voice('huihui') or pick_voice('zh-cn') or (voices[0].id if voices else None)

manifest = []
engine.setProperty('voice', v_en)
for i, t in enumerate(english, 1):
    p = base / 'en' / f'english_{i:02d}.wav'
    engine.save_to_file(t, str(p))
    manifest.append({'lang':'en','file':str(p),'ref':t,'voice':v_en})

engine.setProperty('voice', v_zh)
for i, t in enumerate(chinese, 1):
    p = base / 'zh' / f'chinese_{i:02d}.wav'
    engine.save_to_file(t, str(p))
    manifest.append({'lang':'zh','file':str(p),'ref':t,'voice':v_zh})

engine.runAndWait()
(base / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'ok':True,'total':len(manifest),'voice_en':v_en,'voice_zh':v_zh}, ensure_ascii=False))
