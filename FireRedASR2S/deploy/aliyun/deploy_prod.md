# Demo1 国内公网部署说明

## 目标架构

- 国内公网轻前端：`public_web/`
- 反向代理：`Nginx`
- 主后端：`dialect_service`
- 主语音能力：`Qwen/DashScope API`
- Voice Matched：`qwen-voice-enrollment -> qwen3-tts-vc-2026-01-22`
- 本地模型：FireRed ASR、OpenVoice、RVC 只保留为后备/评测路线，不作为国内上线默认主链路

## 推荐机器

- 阿里云 ECS Linux
- 首版 API-first 可使用 CPU 机器，建议 2C4G 起步
- 系统盘建议 >= 60GB
- 如继续保留本地 ASR 模型和历史运行数据，数据盘建议 >= 100GB
- 安全组开放：`80`、`443`，后端 `8002` 只监听 `127.0.0.1`，不要直接暴露公网

## 部署步骤

### 1. 上传项目

- 上传整个 `Competition` 目录到 `/opt/Competition`
- 保持：
  - `/opt/Competition/FireRedASR2S`
  - `/opt/Competition/OpenVoiceRuntime` 可保留，但首版国内上线默认不依赖它

### 2. 安装依赖

- 安装 `ffmpeg`
- 安装 `nginx`
- 准备 Python 环境
- 安装 Python 依赖：

```bash
cd /opt/Competition/FireRedASR2S
pip install -r requirements.txt
```

如果暂时不启用本地 ASR/GPU，可后续再瘦身依赖；首版先保持兼容，避免大批量删除。

### 3. 配置环境变量

- 复制 `deploy/aliyun/env.example.prod`
- 生成 `/etc/voice-demo/dialect_service.env`
- 填写：
  - `DEEPSEEK_API_KEY`
  - `DASHSCOPE_API_KEY`
  - `QWEN_TTS_API_KEY`
  - `QWEN_LLM_API_KEY`
  - `PUBLIC_APP_ORIGIN`
  - `CORS_ALLOW_ORIGINS`
- 国内上线默认保留：

```bash
VOICE_MATCH_PROVIDER=qwen_voice_clone
VOICE_CLONE_PROVIDER=qwen_voice_clone
TEXT_CLONE_PROVIDER=qwen_voice_clone
QWEN_VOICE_ENROLLMENT_MODEL=qwen-voice-enrollment
QWEN_VOICE_TARGET_MODEL=qwen3-tts-vc-2026-01-22
QWEN_TTS_VC_MODEL=qwen3-tts-vc-2026-01-22
SPEAKER_REF_AUDIO_MIN_S=10
SPEAKER_REF_AUDIO_MAX_S=20
```

### 4. 启动后端

- 拷贝 `deploy/aliyun/dialect_service.service` 到 `/etc/systemd/system/`
- 执行：

```bash
sudo systemctl daemon-reload
sudo systemctl enable dialect_service
sudo systemctl start dialect_service
sudo systemctl status dialect_service
```

### 5. 配置 Nginx

- 拷贝 `deploy/aliyun/nginx_public.conf` 到 `/etc/nginx/conf.d/demo1.conf`
- 根据实际域名修改 `server_name`
- 域名备案并解析到 ECS 公网 IP；国内用户访问必须使用国内可达域名/IP，不要依赖 `gradio.live`
- 重载 Nginx：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 6. HTTPS

- 推荐使用阿里云免费证书或 `certbot` 配置 HTTPS。
- 如果比赛/演示只临时使用 HTTP，需要确保浏览器允许录音/上传文件；麦克风录音在多数浏览器要求 HTTPS。

### 7. 验证

- 打开 `https://your-domain` 或 `http://your-domain`
- 上传音频
- 上传 10-20 秒单人声参考音频
- 确认：
  - `Gold Teacher` 可播放
  - `Voice Matched` 走 Qwen 声音复刻，可播放或明确回退
  - 三种方言选择可生效

## 成本回退建议

- 若本地 ASR 依赖过重：
  - 优先把 ASR 切到云端 API
  - 保留本地 ASR 作为实验环境
- 若 Qwen 声音复刻不可用：
  - 暂时回退 Gold Teacher
  - 再评估是否云端部署 OpenVoice/RVC

## 后续优化

- 接入云端 ASR provider，减少服务器依赖
- 增加 HTTPS 与域名证书自动续期
- 将音频结果接入 OSS/CDN，降低 ECS 静态文件压力
- RAG 接入 `review` 后、`rewrite` 前的方言词库增强层
