# Qwen API 云端重构目标与大纲：Voice Matched 必须上线

更新时间：2026-05-12

## Summary

- 快速上线版必须实现 `voice_matched`，并把“声音复刻”作为产品亮点，而不是可选实验项。
- 默认实现使用 Qwen 官方声音复刻 API：`qwen-voice-enrollment -> qwen3-tts-vc-2026-01-22`。
- 只有当 Qwen API 无法满足效果、合规、稳定性或调用限制时，才考虑云端部署 OpenVoice/RVC 等模型。
- 不大批量删除原有文件；本地模型链路保留为备用、评测和兜底，删除必须先提交清单审核。

## 官方文档

- Qwen 声音复刻官方文档：
  - `https://help.aliyun.com/zh/model-studio/qwen-tts-voice-cloning?spm=a2c4g.11186623.0.0.260c1c4dnNv33P`
- Qwen 语音生成官方文档：
  - `https://help.aliyun.com/zh/model-studio/qwen-tts?spm=a2c4g.11186623.help-menu-2400256.d_0_3_5_2.260c1c4dnNv33P&scm=20140722.H_2879134._.OR_help-T_cn~zh-V_1`

关键约束：

- 声音复刻无需训练，官方说明可用约 `10~20` 秒参考音频生成定制音色。
- 创建音色使用 `qwen-voice-enrollment`。
- 创建音色时必须指定 `target_model`。
- 后续 TTS 合成时的模型必须与 `target_model` 一致，否则会合成失败。
- 上线默认模型使用 `qwen3-tts-vc-2026-01-22`，优先使用非实时/单向合成，便于 Web 端保存和播放最终音频。

## Target Pipeline

1. 音频输入
   - 用户上传普通话、方言或多语言音频。
   - 线上目标为云端 ASR API 完成转写；当前本地 FireRed ASR 保留为兼容实现。
2. 文本确认
   - LLM 审查 ASR 文本，修正错字、断句、同音误识别和标点。
   - 生成 `semantic_text` 作为语义确认主文本。
   - 保留 `dialect_text`、`pronunciation_text`、`prosody_text` 作为方言、发音和韵律控制层。
3. Gold Teacher
   - 使用 Qwen TTS 生成标准音频。
   - 负责“怎么说”：语义准确、发音稳定、韵律自然。
4. Voice Matched
   - 上传参考音频后，调用 `qwen-voice-enrollment` 创建或复用 cloned voice。
   - 使用同一个 `target_model=qwen3-tts-vc-2026-01-22` 调用 Qwen TTS VC 合成最终声音。
   - 负责“像谁说”：复刻参考说话人的音色。
   - Web 页面必须展示并播放 `voice_matched` 结果；失败时展示明确错误，并回退 Gold Teacher。

## Key Changes

- `voice_matched` 从“本地 OpenVoice/RVC 优先”改成“Qwen 声音复刻 API 优先”。
- 新增或明确配置：
  - `VOICE_MATCH_PROVIDER=qwen_voice_clone`
  - `QWEN_VOICE_ENROLLMENT_MODEL=qwen-voice-enrollment`
  - `QWEN_VOICE_TARGET_MODEL=qwen3-tts-vc-2026-01-22`
  - `DASHSCOPE_API_KEY`
  - `QWEN_VOICE_CACHE_DIR`
- 参考音频处理：
  - 接收 `wav/mp3/m4a/aac/ogg/webm/flac`。
  - 上线前校验时长、大小、采样率、声道和音频可读性。
  - 默认参考音频时长范围为 `10~20` 秒。
  - 不满足条件时提示用户重新上传，不静默进入低质量复刻。
- 音色缓存：
  - 对同一参考音频和同一 `target_model` 生成的 `voice` 做本地缓存。
  - 缓存记录包含 `voice`、`target_model`、`enrollment_model`、参考音频摘要、创建时间和状态。
- fallback 策略：
  - Qwen voice enrollment 失败：返回 Gold Teacher，并显示 `voice_matched_failed`。
  - Qwen VC 合成失败：返回 Gold Teacher，并保留错误原因。
  - 仅当 Qwen API 路线长期不可用或效果不达标时，再启用云端 OpenVoice/RVC 部署方案。

## Implementation Notes

- 当前代码中的 Qwen 底座位于：
  - `FireRedASR2S/fireredasr2s/dialect_pipeline/voice_clone.py`
  - `FireRedASR2S/fireredasr2s/dialect_pipeline/tts.py`
- 当前服务编排位于：
  - `FireRedASR2S/dialect_service/adapters.py`
  - `FireRedASR2S/dialect_service/pipeline_engine.py`
- 当前 Web Demo 位于：
  - `FireRedASR2S/web_demo/app.py`
  - `FireRedASR2S/web_demo/client.py`
  - `FireRedASR2S/web_demo/view_models.py`
- OpenVoice/RVC 不删除，只从默认主链路降级为后备技术路线。
- 多语言、多方言和未来 RAG 继续保留：
  - 多方言入口仍由 `target_dialect`、`dialect_style`、中间层文本和 Qwen TTS/VC 控制。
  - RAG 预留在 `review` 之后、`rewrite` 之前，用于方言词汇、地域知识和濒危词语义补充。

## Test Plan

- 文档验收：
  - 两条官方链接完整写入 Markdown。
  - 明确 `voice_matched` 是上线必做项。
  - 明确 Qwen API 优先，云端模型部署只是后备方案。
- API 验收：
  - 参考音频能成功创建 cloned voice。
  - 使用相同 `target_model` 能生成 `voice_matched.wav`。
  - `target_model` 不一致时能捕获错误并返回可读提示。
- 产品验收：
  - Web 页面同时展示 Gold Teacher 与 Voice Matched。
  - Voice Matched 成功时作为推荐主输出。
  - Voice Matched 失败时自动回退 Gold Teacher，但不能假装复刻成功。
- 多语言/方言验收：
  - 粤语、四川话、闽南语入口保留。
  - 中间层文本只用于控制和展示，最终验收以 Gold Teacher 与 Voice Matched 听感为准。

