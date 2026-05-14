# 本地运行说明：CosyVoice 公网版

更新时间：2026-05-14

## 1. 当前唯一推荐演示链路

本项目当前用于比赛展示和公网演示的主链路是 CosyVoice 低延迟链路，不再把 Gold Teacher、OpenVoice、RVC 作为主展示路线。

推荐讲法：

```text
音频输入 -> ASR 识别成文本 -> 文本轻量清洗 -> CosyVoice v3-flash -> 方言音频输出
文本输入 -> 本地清洗/可选 LLM -> CosyVoice v3-flash -> 兜底方言音频输出
```

当前 Demo 支持三种方言：

- 粤语
- 四川话
- 闽南语

页面主结果来自 CosyVoice 实时方言语音。文本改写、RAG、文化卡片等内容主要用于解释和展示，不是最终音频质量的唯一来源。

## 2. 当前已实现能力

公网展示页：

```text
D:\Competition\FireRedASR2S\public_web\index.html
D:\Competition\FireRedASR2S\public_web\app.js
D:\Competition\FireRedASR2S\public_web\styles.css
```

已具备：

- 主音频上传或手机录音入口。
- 音色参考音频上传入口。
- 文本直接输入入口。
- 目标方言选择：粤语、四川话、闽南语。
- CosyVoice v3-flash 实时语音播放。
- 实时链路失败时，自动调用非实时兜底音频。
- 展示推荐主输出、总耗时、Trace ID、错误/降级原因。
- 展示 ASR 文本、最终朗读文本、方言发音指令、RAG/文化百科占位信息。

后端主要入口：

```text
D:\Competition\FireRedASR2S\dialect_service\app.py
D:\Competition\FireRedASR2S\dialect_service\pipeline_engine.py
D:\Competition\FireRedASR2S\fireredasr2s\dialect_pipeline\cosyvoice.py
```

关键接口：

- `GET /healthz`：检查服务状态和 CosyVoice 配置。
- `POST /api/v1/dialect/realtime-session`：创建实时合成会话。
- `WebSocket /api/v1/dialect/stream/{stream_id}`：浏览器接收实时音频流。
- `POST /api/v1/dialect/pipeline`：非实时兜底链路。

## 3. 环境变量

运行前至少需要配置 DashScope/Qwen 的 TTS Key。不要把真实 Key 写进源码或文档。

推荐配置：

```env
DASHSCOPE_API_KEY=你的 Key
QWEN_TTS_API_KEY=你的 Key

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

可选：

```env
COSYVOICE_TEXT_ONLY_USE_DEFAULT_VOICE=true
COSYVOICE_TEXT_ONLY_REWRITE=false
```

建议比赛演示时优先关闭等待时间较长的 LLM 改写，让主音频先稳定出来。

## 4. 本地启动方式

进入项目目录：

```powershell
cd D:\Competition\FireRedASR2S
```

推荐使用已有脚本：

```powershell
.\start_demo1_web.ps1
```

脚本会尽量自动处理：

- 读取项目 `.env`。
- 设置 `PYTHONPATH`。
- 加入 ffmpeg 路径。
- 启动本地 Gradio Demo。

如果只看公网静态页，可以直接打开：

```text
D:\Competition\FireRedASR2S\public_web\index.html
```

如果要联调接口，需要后端服务可访问：

```text
http://127.0.0.1:8002
```

公网展示页默认会请求：

```text
/api/v1/dialect/realtime-session
/api/v1/dialect/stream/{stream_id}
/api/v1/dialect/pipeline
```

## 5. 演示流程

建议现场按这个顺序演示：

1. 打开网页，确认右上角服务状态显示在线。
2. 选择目标方言，例如粤语。
3. 输入一句普通话文本，点击“实时生成方言语音”。
4. 播放 CosyVoice 输出音频。
5. 再上传一段音频或手机录音，展示“音频输入也能走同一条链路”。
6. 如有合适的参考音频，再展示音色参考功能；如果失败，说明系统会自动使用系统音色兜底。

推荐测试文本：

```text
欢迎大家来到声临其境，我们希望让更多年轻人听见家乡话，也愿意把家乡话继续传下去。
```

## 6. 汇报时不要再作为主线讲的内容

以下内容已经归档为旧实验或后续探索，不能在当前 PPT 中说成已经完整跑通：

- Gold Teacher 作为主音频路线。
- OpenVoice 音色迁移。
- RVC 音色转换。
- Qwen Voice Copy 作为当前公网主链路。
- 数字人驱动已经完整联动。
- 方言树数据库和全球乡音地图已经完成。

正确讲法是：

```text
当前可演示的是 CosyVoice 三方言实时语音 Demo。
Gold Teacher、OpenVoice、RVC 等路线是早期探索，已经归档为旧路线。
方言树、乡音地图、数字人联动是后续扩展方向。
```

## 7. 常见问题

### 服务未连接

检查 `http://127.0.0.1:8002/healthz` 是否可访问。

### 实时播放失败

系统会自动尝试 `/api/v1/dialect/pipeline` 生成非实时兜底音频。页面会显示错误或降级原因。

### 没有参考音频

可以直接使用系统音色 `longanyang` 兜底，不影响主流程展示。

### 参考音频复刻失败

多数原因是参考音频太短、太长、采样率不合适或公网 URL 不可访问。演示时不要卡在这里，直接用系统音色兜底继续讲主功能。

## 8. 当前文档入口

项目文档统一放在根目录：

```text
D:\Competition\docs
```

分类：

- `汇报材料`：PPT、讲稿、给文书队友看的说明。
- `技术实现`：当前真实可运行链路和部署说明。
- `旧的废弃路线`：旧技术规划和历史实验记录。
