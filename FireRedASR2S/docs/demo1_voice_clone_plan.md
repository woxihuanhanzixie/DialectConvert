# Demo1 音色克隆说明

## 目标

- 支持使用参考音频生成与原声更接近的粤语语音。
- 首版优先接入 `Qwen3-TTS-VC`。
- 同时预留本地 provider 扩展位：`gpt_sovits`、`fish_speech`。

## 当前实现

- 配置入口：
  - `VOICE_CLONE_PROVIDER`
  - `QWEN_TTS_VC_MODEL`
  - `QWEN_TTS_CUSTOMIZATION_PATH`
  - `SPEAKER_REF_AUDIO_MIN_S`
  - `SPEAKER_REF_AUDIO_MAX_S`
  - `SPEAKER_SIMILARITY_PRIORITY`
  - `REFERENCE_AUDIO_STRATEGY`
  - `TTS_FLUENCY_MODE`
  - `TTS_STYLE_INSTRUCTIONS`
- 统一封装位置：
  - `fireredasr2s/dialect_pipeline/voice_clone.py`
  - `fireredasr2s/dialect_pipeline/tts.py`
  - `dialect_service/adapters.py`

## 推荐参考音频

- 时长：3~10 秒
- 说话人：单人
- 场景：少背景音、少混响、无配乐
- 处理原则：保留原始音色，不默认强降噪；优先采用 `VAD 拼接` 去掉长停顿和无效空白

## 当前策略定义

- 目标：
  - 优先保留说话人声纹相似度
  - 不要求完全逐帧复刻原音节奏
  - 允许语速和停顿为流畅度做调整
- 发音输入：
  - 页面展示 `semantic_text`
  - TTS/VC 实际优先使用 `pronunciation_text`
  - 首版先做高频词规则修正，后续再接 LLM fallback / RAG
- 首版默认：
  - `speaker_similarity_priority = high`
  - `reference_audio_strategy = vad_concat`
  - `tts_fluency_mode = allow_rate_adjust`

## 当前回退策略

- 未提供参考音频：回退系统音色
- 克隆失败：回退系统音色并记录 `fallback_reason`
- 本地 provider：保留接口，暂未启用
