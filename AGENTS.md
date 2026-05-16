# AGENTS.md

## 项目定位

本仓库是“声临其境: AI 赋能的中国濒危方言数字化保护与传承平台”的归档重建版。当前交付目标是一个可在小型腾讯云服务器运行的 Web 应用：用户用手机录音或上传音频，系统转写原始语音，将语义改写为粤语、四川话或闽南话，再用云端音色克隆能力生成“用户音色说方言”的结果。

## 当前结构

- `app/`: FastAPI 后端主代码。
- `app/main.py`: HTTP 入口、静态页面、上传接口、健康检查。
- `app/pipeline.py`: ASR、方言改写、音色注册、TTS/VC 合成的编排层。
- `app/providers.py`: DashScope/Qwen API 调用封装，含重试、错误处理和音频提取。
- `app/storage.py`: 上传命名、输出文件、音色缓存、临时文件清理。
- `app/config.py`: `.env` 配置读取，不打印任何密钥。
- `static/`: 手机端友好的单页 Web 前端。
- `scripts/run_dev.ps1`: 本地开发启动脚本。
- `scripts/deploy_tencent_cloud.ps1`: 腾讯云部署脚本，使用本地 SSH 私钥上传并创建 systemd 服务。
- `tests/`: 本地单元测试，覆盖上传文件处理和主编排偏好克隆音色结果的行为。
- `docs/`: 原项目文档与本次执行记录。
- `runtime_data/`: 运行时上传、输出和音色缓存目录，不应提交 Git。

## 主链路

1. 前端录音或上传音频。
2. 后端保存到 `runtime_data/uploads/{job_id}.{ext}`。
3. ASR 使用 DashScope Paraformer 生成 `source_text`。
4. Qwen LLM 将 `source_text` 改写成自然方言口语文本。
5. Qwen Voice Enrollment 复用或创建 `voice_id`。
6. Qwen TTS/VC 使用同一个 `target_model` 生成克隆音色方言语音。
7. 若克隆失败，返回 Gold Teacher 标准方言音频并显示明确警告，不伪装成克隆成功。

## 关键配置

- `DASHSCOPE_API_KEY`: DashScope/Qwen 语音能力密钥。
- `QWEN_LLM_API_KEY`: Qwen/OpenAI-compatible LLM 密钥，缺省可复用 `DASHSCOPE_API_KEY`。
- `PUBLIC_BASE_URL`: 部署后的公网地址，例如 `http://服务器IP:7860`。云端 ASR/音色注册需要能拉取上传音频。
- `QWEN_VOICE_ENROLLMENT_MODEL`: 默认 `qwen-voice-enrollment`。
- `QWEN_VOICE_TARGET_MODEL`: 默认 `qwen3-tts-vc-2026-01-22`。
- `QWEN_TTS_MODEL`: Gold Teacher 标准 TTS 模型。
- `QWEN_TTS_VOICE`: Gold Teacher 默认声音。

## 安全约束

- 不提交 `.env`、私钥、运行时音频或缓存文件。
- 不在日志或文档中输出 API key、SSH 私钥内容或用户上传音频的敏感信息。
- 运行时文件默认按 `CLEANUP_AFTER_HOURS` 清理，避免 50G 服务器被上传文件占满。

