# CosyVoice v3-flash 低延迟公网链路改造

更新时间：2026-05-13

## 目标

公网 Demo1 主链路从旧的 Qwen-TTS / Qwen voice clone 切换为 CosyVoice：

`文本或 ASR 文本 -> 本地轻量清洗 -> CosyVoice 声音复刻可选创建 voice_id -> cosyvoice-v3-flash 实时合成 -> 浏览器播放`

低延迟优先。最终音频不再等待 LLM 方言改写、pronunciation_text 或 prosody_text。页面仍可展示调试文本，但主试听结果来自 CosyVoice v3-flash。

## 固定配置

- 北京地域 HTTP Base：`https://dashscope.aliyuncs.com/api/v1`
- 北京地域 WebSocket：`wss://dashscope.aliyuncs.com/api-ws/v1/inference/`
- 声音复刻接口：`/services/audio/tts/customization`
- 创建音色模型：`voice-enrollment`
- 绑定合成模型：`cosyvoice-v3-flash`
- 输出格式：`mp3`
- 采样率：`22050`
- 系统音色兜底：`longanyang`

推荐环境变量：

```env
VOICE_MATCH_PROVIDER=cosyvoice
VOICE_CLONE_PROVIDER=cosyvoice
TEXT_CLONE_PROVIDER=cosyvoice
VOICE_CONVERSION_MODE=cosyvoice_realtime
COSYVOICE_BASE_URL=https://dashscope.aliyuncs.com/api/v1
COSYVOICE_WS_URL=wss://dashscope.aliyuncs.com/api-ws/v1/inference/
COSYVOICE_ENROLLMENT_MODEL=voice-enrollment
COSYVOICE_TARGET_MODEL=cosyvoice-v3-flash
COSYVOICE_SYSTEM_VOICE=longanyang
COSYVOICE_AUDIO_FORMAT=mp3
COSYVOICE_SAMPLE_RATE=22050
```

## 声音复刻

参考音频会先归一化并复制到：

`runtime_data/step2_output/ref_audio/{trace_id}.wav`

后端通过现有 `/api/v1/files/audio/...` 生成公网 URL，再调用 CosyVoice 声音复刻：

```json
{
  "model": "voice-enrollment",
  "input": {
    "action": "create_voice",
    "target_model": "cosyvoice-v3-flash",
    "prefix": "demo",
    "url": "PUBLIC_REFERENCE_AUDIO_URL",
    "language_hints": ["zh"]
  }
}
```

优先读取 `output.voice_id`，兼容旧字段 `output.voice`。缓存 key 为参考音频 sha256、公网 URL、`cosyvoice-v3-flash` 和北京地域 Base URL。

## 实时接口

新增：

- `POST /api/v1/dialect/realtime-session`
- `WebSocket /api/v1/dialect/stream/{stream_id}`

前端先创建 session，拿到 `stream_url` 后立即建立 WebSocket。浏览器不直连 DashScope，API Key 只留在后端。

无参考音频时直接使用 `COSYVOICE_SYSTEM_VOICE`，保证用户输入后尽快听到结果。有参考音频时先创建或复用 `voice_id`，再开始流式合成。

## 方言控制

当前只允许：

- `yue`：`请使用自然广东话/粤语表达，保持原意。`
- `sichuan`：`请使用自然四川话表达，保持原意。`
- `minnan`：`请使用自然闽南语表达，保持原意。`

朗读文本取本地轻量清洗后的用户文本或 ASR 文本，不再把 LLM 改写结果作为主音频输入。
