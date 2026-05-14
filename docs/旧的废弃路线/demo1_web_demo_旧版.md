# Demo1 Web Demo

## 当前页面已展示内容

- 输入音频质量信息
- 目标方言与方言风格
- 语义转写文本
- 发音转写文本
- 发音规则命中与回退状态
- 参考音频来源
- 参考音频处理模式
- 参考拼接片段数与拼接后时长
- 音色优先级与流畅度模式
- 音色克隆回退原因

## 当前默认策略

- 目标方言：`yue`
- 方言风格：`guangdong_general`
- 参考音频策略：`vad_concat`
- 音色优先级：`high`
- 流畅度模式：`allow_rate_adjust`
## 目标

- 提供本地可运行的 Demo1 网页演示。
- 页面展示完整链路：`音频输入 -> ASR -> 审查纠错 -> TN/粤语改写 -> TTS`。
- 接口封装为后续微信小程序和正式前端预留空间。

## 目录

- `asr_service/app.py`：ASR FastAPI 服务
- `dialect_service/app.py`：审查纠错、改写、TTS、pipeline FastAPI 服务
- `web_demo/app.py`：Gradio 演示页

## 依赖安装

```bash
conda run -n fireredasr2s pip install -r requirements.txt
```

## 环境变量

- 复制 `.env.example` 为 `.env`
- 至少配置：
  - `DEEPSEEK_API_KEY`
  - `QWEN_TTS_API_KEY` 或 `DASHSCOPE_API_KEY`
- Voice Matched 默认走 `openvoice`
- `OPENVOICE_PYTHON` 仅在确实需要独立解释器时再设置；默认直接复用 `fireredasr2s` conda 环境

## 启动方式

### 1. 启动 ASR 服务

```bash
conda run -n fireredasr2s uvicorn asr_service.app:app --host 127.0.0.1 --port 8001
```

### 2. 启动方言服务

```bash
conda run -n fireredasr2s uvicorn dialect_service.app:app --host 127.0.0.1 --port 8002
```

### 3. 启动网页 Demo

```bash
conda run -n fireredasr2s python -m web_demo.app
```

默认地址：

- `http://127.0.0.1:7860`

## 页面功能

### 完整演示页

- 上传音频
- 浏览器录音
- 显示 ASR 原始文本
- 显示审查后文本
- 显示 TN 文本
- 显示粤语文本
- 播放生成的粤语音频
- 展示 JSON 结构化结果

### 结果评估页

- 展示已有样本集统计
- 展示每条样本的文本与音频路径

## 接口

### `GET /healthz`

- `asr_service`
- `dialect_service`

### `POST /api/v1/asr/transcribe`

- 输入：音频文件
- 输出：`text/confidence/timestamp/punc_text/latency_ms`

### `POST /api/v1/text/review`

- 输入：ASR 文本
- 输出：`asr_raw_text/asr_reviewed_text/asr_review_notes`

### `POST /api/v1/dialect/rewrite`

- 输入：普通话文本
- 输出：`tn_text/dialect_text/rewrite_segments`

### `POST /api/v1/dialect/tts`

- 输入：粤语文本
- 输出：`wav_path/audio_url/expires_at`

### `POST /api/v1/dialect/pipeline`

- 输入：音频文件或文本
- 输出：完整链路结构与 `trace_id`

## 常见问题

### 浏览器录音不可用

- 某些环境或浏览器不支持录音权限
- 请改用音频上传
- 建议在 `fireredasr2s` conda 环境中运行，避免 `torch/numpy/pandas` 版本不兼容

### 非 wav 格式上传失败

- 若本机未安装 `ffmpeg`，建议先上传 `wav`
- 或安装 `ffmpeg` 以启用自动转码

### TTS 返回失败

- 检查 `QWEN_TTS_API_KEY` / `DASHSCOPE_API_KEY`
- 检查网络连通性和模型配置
