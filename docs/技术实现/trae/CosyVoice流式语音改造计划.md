# CosyVoice 流式语音改造计划

## 背景与当前状态
目前系统采用**非流式（Non-streaming）**方式调用 CosyVoice API 合成方言与克隆语音。
- **流程**：ASR 识别出完整文本 -> 发送完整文本给 CosyVoice HTTP API -> 等待服务端合成完毕 -> 返回完整音频文件的 URL 或 Base64 数据 -> 客户端播放。
- **优点**：架构简单，状态管理容易，稳定性高，适合当前版本的快速部署和演示。
- **缺点**：首字延迟（Time to First Tone, TTFT）较长，特别是长文本场景下，用户需要等待整段音频合成完毕才能听到声音。

## 后续流式（Streaming）改造方案

为了提升用户体验并实现接近实时的语音交互，后续计划将音频生成改造为流式输出。根据阿里云 CosyVoice API 官方文档，可通过 HTTP SSE (Server-Sent Events) 方式实现流式返回。

### 1. 核心层改造 (`fireredasr2s/dialect_pipeline/cosyvoice.py`)
- **开启 SSE**：在调用 CosyVoice API 时，请求 Header 中新增 `"X-DashScope-SSE": "enable"`。
- **解析流式响应**：
  - 处理 `sentence-begin`：获取开始信号。
  - 处理 `sentence-synthesis`：提取 `output.sentence.words.audio.data` 中返回的 Base64 格式音频切片。
  - 处理 `sentence-end`：结束当前句子的流。
- **生成器模式**：将原先返回单一文件的逻辑，改为使用 Python 的 `yield` 关键字，逐步产出（yield）解码后的二进制音频块。

### 2. 服务层改造 (`dialect_service/app.py` & `dialect_service/pipeline_engine.py`)
- **新增流式接口**：在 FastAPI 服务中增加如 `POST /api/v1/dialect/stream-audio` 的路由。
- **数据转发**：使用 FastAPI 的 `StreamingResponse`，将底层 `cosyvoice.py` 生成的音频二进制流直接透传给客户端，`media_type` 设置为 `audio/mp3`（或请求的格式）。

### 3. 前端展示层改造 (`public_web/app.js` & `web_demo/app.py`)
- **分片接收**：前端不再等待完整的 JSON 响应和 `audio_url`，而是通过 Fetch API 的 `response.body.getReader()` 逐步读取二进制流数据。
- **流式播放器**：
  - 引入 Web Audio API 或 MediaSource Extensions (MSE)。
  - 将接收到的音频 Chunk 动态送入 AudioBuffer 进行连续播放，从而实现“边生成边播放”，大幅降低用户的感知延迟。

## 实施路线图 (Roadmap)
1. **API 对接**：在后端独立脚本中跑通 CosyVoice 的 SSE 接口，确认音频切片的连续性。
2. **后端流式服务**：完成 `StreamingResponse` 封装，并进行本地接口测试。
3. **前端播放器替换**：重构 Web 端的音频播放组件，支持流式解码播放。
4. **双链路并存测试**：保留当前的非流式 Pipeline 作为 Fallback 兜底，将前端默认请求切换到流式接口，验证在弱网下的稳定性。