# AGENTS.md

## 项目定位

“声临其境”是一个方言音色复刻 Web 应用。用户在手机或电脑上传/录制一段参考语音，系统完成 ASR 转写、方言口语化改写、音色情感分析、CosyVoice 音色注册与方言语音合成，最终输出带有用户音色的粤语、四川话或闽南话语音。

## 当前结构

- `app/`: FastAPI 后端。
- `app/main.py`: HTTP 入口，提供首页、健康检查和 `/api/convert`。
- `app/models.py`: API 响应模型，包含识别文本、方言文本、情绪标签、语调提示和音频 URL。
- `app/pipeline.py`: 主链路编排，顺序为清理缓存、ASR、情感/标点分析、方言改写、音色注册、TTS 合成。
- `app/providers.py`: DashScope/Qwen/CosyVoice API 调用，包含 ASR、LLM 改写、情感标注、音色注册和语音合成。
- `app/storage.py`: 上传文件、输出文件、元数据、音色缓存和运行时清理。
- `static/`: 单页前端，保留原有录音/上传/提交逻辑，结果区展示带标点识别文本、情绪语调、方言文本和音频。
- `scripts/deploy_tencent_cloud_tar.sh`: 推荐部署脚本，在 WSL/Ubuntu 或 Linux 中用 tar + ssh 部署到腾讯云。
- `scripts/deploy_tencent_cloud.ps1`: PowerShell 备用脚本，不作为首选部署方式。
- `tests/`: 单元测试，覆盖主链路、缓存清理、TTS 指令拼接等关键行为。
- `docs/`: 项目计划、执行记录和技术文档。
- `runtime_data/`: 本地/服务器运行时数据目录，已被 `.gitignore` 排除。

## 语音链路

1. 前端提交 `audio` 和 `dialect`。
2. 后端保存上传文件到 `runtime_data/uploads/{job_id}.{ext}`。
3. `transcribe_audio` 调用 DashScope Paraformer 得到原始 ASR 文本。
4. `analyze_expression` 用 Qwen LLM 恢复标点，并生成 `emotion_label` 与短 `prosody_instruction`。
5. `rewrite_to_dialect` 用带标点文本和情绪提示生成自然方言文本。
6. `build_tts_instruction` 将官方方言指令与短情绪语调合并，例如“请用广东话表达，语气夸张，尾音上扬。”。
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
