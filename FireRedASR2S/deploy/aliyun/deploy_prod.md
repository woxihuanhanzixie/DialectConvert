# Demo1 国内公网部署说明

## 目标架构

- 国内公网轻前端：`public_web/`
- 反向代理：`Nginx`
- 主后端：`dialect_service`
- 主语音能力：`DashScope/Qwen API`
- ASR：公网默认 `api_only`，只走云 ASR
- Voice Matched：首版公网稳定版默认关闭，页面清楚展示 Gold Teacher 回退
- 本地模型：FireRed ASR、OpenVoice、RVC 只保留为后续手动恢复/评测路线，不作为国内上线默认主链路，也不在公网页面展示

## 推荐机器

- 阿里云 ECS Linux
- 首版 API-first 可使用 CPU 机器，2C2G 可跑 Gold Teacher 稳定版，建议 2C4G 起步
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
pip install -r deploy/aliyun/requirements-prod.txt
```

公网 Gold Teacher 稳定版使用轻量依赖，不安装本地 FireRed ASR、OpenVoice、RVC 和 GPU 版 PyTorch。若后续要恢复本地模型评测，再单独安装完整 `requirements.txt` 并准备模型目录。

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
- 国内上线默认保留 Gold Teacher 稳定版：

```bash
VOICE_MATCH_PROVIDER=none
VOICE_CONVERSION_PROVIDER=none
VOICE_CLONE_PROVIDER=qwen_voice_clone
TEXT_CLONE_PROVIDER=qwen_voice_clone
ASR_PROVIDER=api_only
DISABLE_LOCAL_ASR=1
ENABLE_LOCAL_ASR_FALLBACK=0
QWEN_VOICE_ENROLLMENT_MODEL=qwen-voice-enrollment
QWEN_VOICE_TARGET_MODEL=qwen3-tts-vc-2026-01-22
QWEN_TTS_VC_MODEL=qwen3-tts-vc-2026-01-22
SPEAKER_REF_AUDIO_MIN_S=10
SPEAKER_REF_AUDIO_MAX_S=20
```

不要把 `VOICE_MATCH_PROVIDER` 设置为 `qwen_voice_clone`。该路线是 `文本 + 参考音频 -> 克隆语音`，会重新决定发音和韵律；当前公网首版必须保持 `Gold Teacher` 作为推荐主输出。

不要开启 `ENABLE_LOCAL_ASR_FALLBACK`。当前公网版本的 ASR 只走 DashScope/Qwen API；FireRed 本地模型留在仓库中，后续需要时再单独恢复。

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
- 临时公网 IP 交付时可使用 `server_name 43.139.53.84 _;`
- 如后续绑定域名，再修改 `server_name`、`PUBLIC_APP_ORIGIN` 和 `CORS_ALLOW_ORIGINS`
- 重载 Nginx：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 6. HTTPS

- 推荐使用阿里云免费证书或 `certbot` 配置 HTTPS。
- 如果比赛/演示只临时使用 HTTP，需要确保浏览器允许录音/上传文件；麦克风录音在多数浏览器要求 HTTPS。

### 7. 验证

- 打开 `http://43.139.53.84`，或后续绑定后的域名
- 上传音频
- 确认：
  - `Gold Teacher` 可播放
  - 页面展示 RAG 命中率/耗时/语义相似度看板
  - 页面展示文化百科悬浮卡，鼠标悬停或聚焦可查看词义、文化说明和例句
  - 页面不展示 FireRed 本地模型、OpenVoice、RVC、Voice Matched 控件
  - 三种方言选择可生效

## 成本回退建议

- 若本地 ASR 依赖过重：
  - 优先把 ASR 切到云端 API
  - 保留本地 ASR 作为实验环境
- 若后续需要 Voice Matched：
  - 优先评估更高内存机器或独立推理服务
  - OpenVoice/RVC 必须保持 teacher-first audio-to-audio 语义
  - Qwen 声音复刻只能作为独立对照路线，不应冒充 Voice Matched

## 后续优化

- 接入云端 ASR provider，减少服务器依赖
- 增加 HTTPS 与域名证书自动续期
- 将音频结果接入 OSS/CDN，降低 ECS 静态文件压力
- RAG 接入 `review` 后、`rewrite` 前的方言词库增强层
