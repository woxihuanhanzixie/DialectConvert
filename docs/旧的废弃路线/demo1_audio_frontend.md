# Demo1 输入音频前处理说明

## 目标

- 为 ASR 提供更稳定的工作音频。
- 保留原始参考音频，避免破坏声纹。

## 当前策略

- `raw_audio`
  - 保留原始上传音频的统一格式版本
  - 用于参考音频与质量评估
- `work_audio`
  - 用于 ASR
  - 应用轻量前处理：
    - 转 `16kHz / mono / wav`
    - 长静音裁剪
    - 轻量峰值归一
- `clone_ref_vad_concat`
  - 用于音色克隆参考音频
  - 先裁掉长静音
  - 再检测有效语音段
  - 过滤过短、能量过低、削波明显的片段
  - 在 3~10 秒范围内拼接更紧凑的参考音频

## 参考音频新增指标

- `speech_segment_count`
- `speech_ratio`
- `concat_duration_s`
- `concat_applied`
- `concat_fallback_reason`
- `detected_segments`

## 质量指标

- `quality_score`
- `quality_flags`
- `peak_db`
- `rms_db`
- `silence_ratio`
- `clipping_ratio`

## 当前限制

- 不做强降噪
- 不做 AGC
- 不做去混响

原因：这些处理会影响后续音色克隆的原始声纹保真度；首版优先通过 `VAD 拼接` 减少无效停顿，而不是用更重的降噪链路。
