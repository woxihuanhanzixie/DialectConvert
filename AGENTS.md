# AGENTS.md

## 项目定位

“声临其境”是一个方言音色复刻 Web 应用。用户在手机或电脑上录制/上传一段参考语音，系统完成 ASR 转写、方言口语化改写、情绪与语调分析、CosyVoice 音色注册和方言语音合成，最终输出带有用户音色的粤语、四川话或闽南话语音。

## 当前结构

- `app/`: FastAPI 后端。
- `app/main.py`: HTTP 入口，提供首页、健康检查和 `/api/convert`。
- `app/models.py`: API 响应模型，包含识别文本、方言文本、情绪标签、语调提示和音频 URL。
- `app/pipeline.py`: 主链路编排，顺序为清理缓存、ASR、情绪/标点分析、方言改写、音色注册、TTS 合成。
- `app/providers.py`: DashScope/Qwen/CosyVoice API 调用，包括 ASR、LLM 改写、情绪标注、音色注册和语音合成。
- `app/storage.py`: 上传文件、输出文件、元数据、音色缓存和运行时清理。
- `static/`: 单页前端，包含移动端录音、手机系统录音器兜底、上传、提交、结果展示。
- `scripts/deploy_tencent_cloud_tar.sh`: 推荐部署脚本，在 WSL/Ubuntu 或 Linux 中用 tar + ssh 部署到腾讯云。
- `scripts/deploy_tencent_cloud.ps1`: PowerShell 备用部署脚本，不作为首选部署方式。
- `tests/`: 单元测试，覆盖主链路、缓存清理、移动端音频扩展名识别和 TTS 指令拼接。
- `docs/`: 项目计划、执行记录和技术文档。
- `runtime_data/`: 本地/服务器运行时数据目录，已被 `.gitignore` 排除。

## 移动端录音链路

1. HTTPS 或支持安全上下文的浏览器优先使用 `navigator.mediaDevices.getUserMedia` + `MediaRecorder` 网页内录音。
2. 前端通过 `MediaRecorder.isTypeSupported()` 自动选择 `audio/mp4`、`audio/webm`、`audio/ogg` 等可用格式，避免固定 `audio/webm` 导致 iOS/部分安卓失败。
3. 手机 HTTP 页面或浏览器不支持网页内录音时，自动调用 `<input type="file" accept="audio/*" capture="microphone">` 打开系统录音器。
4. 录音完成返回页面后，前端把文件保存到同一个 `selectedFile` 状态，并直接用 `FormData` 作为 `audio` 字段发送到 `/api/convert`。
5. 后端允许 `.m4a`、`.mp4`、`.3gp`、`.3gpp`、`.caf`、`.amr`、`.webm`、`.wav`、`.mp3` 等移动端常见音频格式。

## 语音链路

1. 前端提交 `audio` 和 `dialect`。
2. 后端保存上传文件到 `runtime_data/uploads/{job_id}.{ext}`。
3. `transcribe_audio` 调用 DashScope Paraformer 得到原始 ASR 文本。
4. `analyze_expression` 用 Qwen LLM 恢复标点，并生成 `emotion_label` 与短 `prosody_instruction`。
5. `rewrite_to_dialect` 用带标点文本和情绪提示生成自然方言文本。
6. `build_tts_instruction` 合并官方方言指令和短情绪语调，例如“请用广东话表达，语气焦急，停顿更短。”。
7. `enroll_voice` 注册或复用音色缓存。
8. `synthesize` 使用 CosyVoice 复刻音色生成方言语音。
9. 前端展示 `source_text`、`emotion_label`、`prosody_instruction`、`dialect_text` 和音频。

## 部署约定

优先使用 WSL/Ubuntu 或 Linux 执行部署，避免 PowerShell 在中文路径、ZIP 打包、UTF-8、远端 Linux 文件名上的不稳定问题。

推荐命令：

```bash
cd /mnt/d/dialect\ convert
bash scripts/deploy_tencent_cloud_tar.sh 43.139.53.84 root /opt/dialect-convert 7860 http://43.139.53.84
```

部署后检查：

```bash
curl -s http://43.139.53.84/health
ssh -i ~/.ssh/dialectconvert_key.pem root@43.139.53.84 "systemctl is-active dialect-convert"
```

## 安全约束

- 不提交 `.env`、私钥、API key、上传音频、输出音频和运行缓存。
- 不在日志、文档或提交信息中暴露密钥内容。
- 50G 服务器必须依赖 `cleanup_runtime`、`CLEANUP_AFTER_HOURS` 和音色缓存 TTL 控制磁盘增长。
- CosyVoice `instruction` 保持短句，避免超长指令影响方言输出或触发接口限制。
