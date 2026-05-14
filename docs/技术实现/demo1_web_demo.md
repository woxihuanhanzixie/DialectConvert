# Demo1 Web Demo：CosyVoice 公网版

更新时间：2026-05-14

## 当前定位

当前 Demo1 的公网展示页是一个可操作的 CosyVoice 方言实时语音工作台，不是旧版 Gold Teacher / OpenVoice / RVC 调试页。

推荐主链路：

```text
音频输入 -> ASR -> 文本轻量清洗 -> CosyVoice v3-flash -> 方言音频输出
文本输入 -> 本地清洗/可选 LLM -> CosyVoice v3-flash -> 方言音频输出
```

## 页面入口

```text
D:\Competition\FireRedASR2S\public_web\index.html
```

相关文件：

```text
D:\Competition\FireRedASR2S\public_web\app.js
D:\Competition\FireRedASR2S\public_web\styles.css
```

## 已支持方言

- 粤语：`yue:guangdong_general`
- 四川话：`sichuan:sichuan_general`
- 闽南语：`minnan:minnan_general`

## 页面功能

- 主音频上传或手机录音。
- 音色参考音频上传。
- 文本直接输入。
- 目标方言选择。
- 系统音色兜底选择。
- 创建 CosyVoice 实时会话。
- WebSocket 接收并播放实时音频。
- 实时失败时自动调用非实时兜底链路。
- 展示推荐主输出、总耗时、Trace ID、错误信息。
- 展示 ASR 原始文本、最终朗读文本、方言发音指令、实时策略。
- 预留 RAG 指标和文化百科悬浮卡展示区。

## 后端接口

- `GET /healthz`
- `POST /api/v1/dialect/realtime-session`
- `WebSocket /api/v1/dialect/stream/{stream_id}`
- `POST /api/v1/dialect/pipeline`

## 注意事项

- Gold Teacher、OpenVoice、RVC 不是当前公网主路线。
- Qwen Voice Copy 相关文档已归档为旧路线。
- 文本改写、RAG、文化卡片主要服务展示和后续扩展，不应阻塞主音频输出。
- 演示时优先保证 CosyVoice 音频能快速播放。
