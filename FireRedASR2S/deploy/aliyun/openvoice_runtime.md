# OpenVoice 云端运行说明

## 目的

- 让 `dialect_service` 在阿里云 ECS 上调用 `OpenVoiceRuntime/run_openvoice_convert.py`
- 保持当前 teacher-first 逻辑不变

## 目录约定

- 项目根目录：`/opt/Competition`
- 业务目录：`/opt/Competition/FireRedASR2S`
- OpenVoice 目录：`/opt/Competition/OpenVoiceRuntime`

## 运行要求

- 单卡 GPU ECS
- 已安装 NVIDIA 驱动与 CUDA 运行时
- 与 `dialect_service` 使用同一 Python 环境优先
- 保证 `runtime_data/models/OpenVoice` 与 checkpoint 已上传

## 环境变量建议

- `VOICE_CONVERSION_PROVIDER=openvoice`
- `VOICE_CONVERSION_DEVICE=cuda`
- `OPENVOICE_PYTHON=` 默认留空，优先复用当前环境

## 验证方式

1. 先在 ECS 上执行一次本地链路：
   - `teacher_wav -> openvoice -> voice_matched_wav`
2. 再执行 `dialect_service` 的 `/api/v1/dialect/pipeline`
3. 确认返回：
   - `tts.gold_teacher.audio_url`
   - `tts.voice_matched.audio_url`
4. 确认 Nginx 反代后公网页面可正常播放
