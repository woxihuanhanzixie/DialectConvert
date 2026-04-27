import asyncio
import json
from pathlib import Path
import edge_tts

base = Path(r"d:/Competition/FireRedASR2S/runtime_data/test_audio")
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

async def main():
    manifest = []
    for i, text in enumerate(english, 1):
        out = base / "en" / f"english_{i:02d}.mp3"
        tts = edge_tts.Communicate(text, "en-US-AriaNeural")
        await tts.save(str(out))
        manifest.append({"lang":"en","file":str(out),"ref":text})
    for i, text in enumerate(chinese, 1):
        out = base / "zh" / f"chinese_{i:02d}.mp3"
        tts = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
        await tts.save(str(out))
        manifest.append({"lang":"zh","file":str(out),"ref":text})

    (base / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "total": len(manifest), "manifest": str(base / 'manifest.json')}, ensure_ascii=False))

asyncio.run(main())
