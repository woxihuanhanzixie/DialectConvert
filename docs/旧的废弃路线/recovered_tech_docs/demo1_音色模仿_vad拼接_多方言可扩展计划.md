# Demo1 音色模仿、VAD 拼接参考音频与多方言可扩展计划

## Summary

本轮规划目标是解决 Demo1 当前两类核心问题：

- 粤语文本虽然已从“直译”改为“口语重写”，但仍存在生硬词、风格过于偏香港、后续难以扩展到其他方言的问题。
- 音色模仿链路当前仅做了“去长静音”，还没有按用户期望把参考音频中的长停顿、无效空白和噪点段尽量剔除，并将有效语音段拼接后再用于音色创建。

已确认的用户偏好：

- 音色模仿优先级：`像本人优先`
- 参考音频策略：`VAD 拼接`
- 粤语风格：`广东通用`
- 约束：
  - 不要求完全一模一样，但要更真实、更像主流音色模仿大模型的效果
  - 允许输出语速改变，以保证整体流畅
  - 不能把 prompt 写死成香港粤语，后续要允许扩展到其他方言

本计划的成功标准：

- 参考音频在进入音色克隆前支持“VAD 切段 + 拼接”的新策略，并能在结果中展示参考音频处理方式。
- 粤语改写从“写死香港口语 prompt”升级为“可配置的方言改写策略”，首版默认走“广东通用粤语”。
- TTS/VC 侧新增“流畅度优先”的控制入口，为后续语速、语气、风格指令保留接口。
- 整体方案保持多方言可扩展，不把实现绑死在粤语单一路径。

## Current State Analysis

### 1. 参考音频预处理现状

- 当前参考音频预处理集中在 `FireRedASR2S/asr_service/audio_frontend.py`
- `build_audio_tracks()` 仅支持两种模式：
  - `light_asr_safe`
  - `clone_ref_safe`
- 其中 `clone_ref_safe` 当前只做：
  - 转单声道
  - `trim_long_silence()` 去首尾及大块静音
- 当前没有实现：
  - 基于 VAD 的有效语音段检测
  - 多段拼接
  - 参考音频片段筛选与排序
  - 参考音频专用质量评估字段

相关现状文件：

- `FireRedASR2S/asr_service/audio_frontend.py`
- `FireRedASR2S/asr_service/audio_quality.py`
- `FireRedASR2S/asr_service/audio_io.py`

### 2. 音色模仿链路现状

- 当前音色克隆配置在 `FireRedASR2S/fireredasr2s/dialect_pipeline/config.py`
- 当前 Qwen VC 调用在：
  - `FireRedASR2S/fireredasr2s/dialect_pipeline/voice_clone.py`
  - `FireRedASR2S/fireredasr2s/dialect_pipeline/tts.py`
- 当前网页和服务层已经支持：
  - 主音频自动复用为参考音频
  - `voice_clone_enabled`
  - `voice_clone_provider`
  - 参考音频来源展示
- 但当前还没有：
  - 参考音频处理模式选择
  - 参考音频拼接结果说明
  - “像本人优先 / 流畅优先”的策略开关
  - TTS 语速、风格、指令控制入口

相关现状文件：

- `FireRedASR2S/dialect_service/adapters.py`
- `FireRedASR2S/dialect_service/pipeline_engine.py`
- `FireRedASR2S/web_demo/app.py`
- `FireRedASR2S/web_demo/client.py`
- `FireRedASR2S/web_demo/view_models.py`

### 3. 粤语改写现状

- 当前改写逻辑集中在 `FireRedASR2S/fireredasr2s/dialect_pipeline/rewrite.py`
- 当前实现仍然是单函数 `rewrite_to_cantonese()`
- 当前 prompt 已从“直译”提升为“香港口语粤语重写”，但仍有三个问题：
  - 方言目标写死为“香港口语粤语”
  - 没有抽象出可扩展的方言风格层
  - 没有词级后处理，仍可能出现部分普通话味较重词汇
- 当前服务层 `rewrite_text()` 直接调用 `rewrite_to_cantonese()`，没有 dialect/style 参数透传

相关现状文件：

- `FireRedASR2S/fireredasr2s/dialect_pipeline/rewrite.py`
- `FireRedASR2S/dialect_service/adapters.py`
- `FireRedASR2S/dialect_service/pipeline_engine.py`

### 4. 多方言扩展现状

- 当前 Demo1 仍然默认只服务 `yue`
- `rewrite` 层没有统一的“目标方言 + 风格”抽象
- UI 上也没有多方言风格展示位
- 如果现在继续把 prompt 和函数名写死为 cantonese/hk，会增加后续扩展闽南话、四川话等方言的改造成本

## Proposed Changes

### 1. 参考音频从“去静音”升级为“VAD 拼接参考音频”

#### 1.1 新增参考音频拼接策略

改造文件：

- `FireRedASR2S/asr_service/audio_frontend.py`
- `FireRedASR2S/asr_service/audio_quality.py`
- `FireRedASR2S/asr_service/audio_io.py`

改造内容：

- 在 `audio_frontend.py` 中新增参考音频专用模式，例如：
  - `clone_ref_vad_concat`
- 该模式的行为定义：
  - 对参考音频先做格式统一
  - 使用已有 VAD 能力或阈值规则切出有效语音段
  - 丢弃过短、纯静音、能量过低片段
  - 将中间自然语音段拼接为更紧凑的参考音频
  - 保留原始参考音频与拼接结果两个版本

为什么这样改：

- 用户明确希望“消除大量无关数据噪点”
- 相比直接保留整段音频，VAD 拼接后的参考音频更聚焦于说话人稳定声纹段
- 相比强降噪，VAD 拼接对声纹破坏更小，更符合“像本人优先”的目标

如何落地：

- 在 `audio_quality.py` 中补充参考音频分段质量指标：
  - `speech_ratio`
  - `kept_segments`
  - `concat_duration_s`
  - `dropped_reason`
- 在 `audio_io.py` 的 `normalize_file_to_wav()` 结果中增加：
  - `voice_clone_ref_audio.raw_path`
  - `voice_clone_ref_audio.concat_path`
  - `voice_clone_ref_audio.concat_duration_s`
  - `voice_clone_ref_audio.segment_count`

#### 1.2 明确拼接规则

建议固定首版规则，避免执行阶段再做临时选择：

- 先用 VAD 拿到候选语音段
- 只保留满足以下条件的片段：
  - 片段时长 >= 0.8s
  - 平均能量不低于参考阈值
  - 非过强削波片段
- 若合并后总时长 > 10s：
  - 优先保留中间较稳定的自然语音段
  - 截断到 6~10s 区间
- 若合并后总时长 < 3s：
  - 回退到 `clone_ref_safe`
  - 并记录“拼接后有效语音不足”

### 2. 将“粤语重写”升级为“可扩展方言改写器”

#### 2.1 抽象目标方言与风格

改造文件：

- `FireRedASR2S/fireredasr2s/dialect_pipeline/rewrite.py`
- `FireRedASR2S/dialect_service/adapters.py`
- `FireRedASR2S/dialect_service/pipeline_engine.py`
- `FireRedASR2S/dialect_service/schemas.py`

改造内容：

- 将 `rewrite_to_cantonese()` 抽象为更通用接口，例如规划中的目标形态：
  - `rewrite_to_dialect(text, cfg, target_dialect, dialect_style)`
- 首版仍只实现 `target_dialect="yue"`，但接口不再写死在函数名和 prompt 中
- 新增风格参数：
  - `dialect_style="guangdong_general"` 作为首版默认
  - 保留未来可能的：
    - `hongkong_colloquial`
    - `formal_safe`

为什么这样改：

- 用户已经明确提出：后续不止粤语一种方言，不能现在就写死
- 当前 `rewrite.py` 的 prompt 直接绑定“香港口语粤语”，与用户当前偏好“广东通用”不一致

如何落地：

- `rewrite.py` 中拆分 prompt 生成函数：
  - 通用方言改写系统提示
  - 粤语方言特化提示
  - 风格层提示
- `adapters.py` 的 `rewrite_text()` 增加参数透传：
  - `target_dialect`
  - `dialect_style`
- `pipeline_engine.py` 中把当前硬编码粤语链路改成配置驱动

#### 2.2 增加“普通话味”后处理层

改造文件：

- `FireRedASR2S/fireredasr2s/dialect_pipeline/rewrite.py`
- 可新增：
  - `FireRedASR2S/fireredasr2s/dialect_pipeline/dialect_postprocess.py`

改造内容：

- 在 LLM 输出后增加一层轻量文本后处理
- 首版仅做“广东通用粤语”清洗，不做激进替换
- 针对高频生硬词增加黑名单和替换规则，例如：
  - “非常” -> “真系/好”
  - “事情” -> “事”
  - “造成” -> “搞到/变成”
  - “不可逆” -> “好难救返/冇得补救”

为什么这样改：

- 单靠 prompt 仍会出现个别生硬词
- 后处理规则层可以提高稳定性，也方便以后按不同方言扩展词表

### 3. 音色模仿目标从“完全复刻”改为“声纹优先、韵律可调”

#### 3.1 增加音色策略与流畅度策略

改造文件：

- `FireRedASR2S/fireredasr2s/dialect_pipeline/config.py`
- `FireRedASR2S/dialect_service/adapters.py`
- `FireRedASR2S/dialect_service/pipeline_engine.py`
- `FireRedASR2S/dialect_service/schemas.py`

改造内容：

- 在配置和请求层新增以下规划字段：
  - `speaker_similarity_priority`
  - `reference_audio_strategy`
  - `tts_fluency_mode`
  - `tts_style_instructions`
- 首版固定默认决策：
  - `speaker_similarity_priority = high`
  - `reference_audio_strategy = vad_concat`
  - `tts_fluency_mode = allow_rate_adjust`

为什么这样改：

- 用户已经明确说明“不需要完全一模一样”
- 更合理的产品定义应该是：
  - 声纹接近
  - 粤语播报自然
  - 语速允许调整

#### 3.2 为 TTS 指令控制预留接口

改造文件：

- `FireRedASR2S/fireredasr2s/dialect_pipeline/tts.py`
- `FireRedASR2S/fireredasr2s/dialect_pipeline/voice_clone.py`
- `FireRedASR2S/dialect_service/adapters.py`

改造内容：

- 对标准 TTS 和 VC TTS 都预留 `instructions` 或等价控制字段
- 首版执行策略：
  - 若 provider 支持自然语言指令控制，则传入“语速略平稳、停顿自然、保持口语流畅”的风格指令
  - 若当前 VC 路径不支持，则仅在标准 TTS / instruct 模型侧保留接口，不阻断主链路

注意：

- 本计划不要求现阶段把 provider 立即切成 `qwen3-tts-instruct-flash`
- 但要求把接口层设计好，避免后续二次重构

### 4. 页面与结果展示同步升级

改造文件：

- `FireRedASR2S/web_demo/app.py`
- `FireRedASR2S/web_demo/client.py`
- `FireRedASR2S/web_demo/view_models.py`

改造内容：

- 在页面结果中增加参考音频处理方式展示：
  - 原始参考音频
  - VAD 拼接参考音频
  - 保留片段数
  - 拼接后总时长
- 增加文本风格说明：
  - 目标方言
  - 方言风格
- 增加音色模仿策略说明：
  - `像本人优先`
  - `语速允许调整`

为什么这样改：

- 当前页面只能看到“是否启用音色克隆”
- 用户无法判断系统到底用了哪种参考音频策略，也无法知道输出偏差来自文本还是音色

### 5. 文档同步更新

改造文件：

- `技术文档.md`
- `FireRedASR2S/docs/demo1_voice_clone_plan.md`
- `FireRedASR2S/docs/demo1_audio_frontend.md`
- `FireRedASR2S/docs/demo1_web_demo.md`

改造内容：

- 将“音色模仿目标”重新定义为：
  - 声纹接近优先
  - 韵律允许重建
  - 通过参考音频清洗和拼接减少无关噪声
- 记录“广东通用粤语”作为当前默认风格，而非香港口语写死
- 说明多方言可扩展策略：
  - 目标方言与风格分层配置

## Assumptions & Decisions

### 已锁定决策

- 当前优先目标不是完全复刻原声，而是“更真实、像本人、可流畅播报”
- 参考音频策略采用 `VAD 拼接`
- 粤语文本风格采用 `广东通用`
- 方言改写实现不再允许函数名与 prompt 写死为香港粤语
- TTS 允许调整语速来提升流畅度

### 关键假设

- 现有 `FireRedVAD` 已可复用于参考音频切段，不需要再引入一套新的 VAD 工具
- 当前 Qwen VC 路径仍作为首版主实现，本地开源 provider 暂不作为本轮主路径
- 粤语自然度问题的首要提升空间仍在“重写策略 + 后处理”，而不是先上更复杂模型

### 本轮不做

- 不新增真正的多方言模型实现
- 不做本地音色克隆模型训练
- 不在本轮规划中引入全新的外部音频降噪模型
- 不要求先完成所有方言，只要求把接口和 prompt 结构改成可扩展

## Verification Steps

### 1. 参考音频拼接验收

对同一条参考音频，结果中必须能看到：

- 原始参考音频路径
- 拼接后参考音频路径
- 保留片段数
- 拼接后总时长
- 若拼接失败，明确回退原因

验收标准：

- 拼接后音频无明显爆音、断裂、极短碎片串联问题
- 在 3~10 秒范围内优先保留稳定说话段

### 2. 粤语文本自然度验收

用当前样本 `20260423_214650.wav` 验收：

- 改写结果应明显减少普通话味重词汇
- 不应默认偏向香港本地俚语
- 文本更接近广东通用口语表达

人工验收项：

- 是否顺口
- 是否保义
- 是否可直接播报

### 3. 可扩展性验收

从代码结构上确认：

- `rewrite` 层存在 `target_dialect` / `dialect_style` 透传
- prompt 生成函数可根据方言和风格切换
- 页面和结果结构中能体现当前方言与风格

### 4. 音色模仿验收

对同一条主音频分别对比：

- 原始整段参考
- 仅去静音参考
- VAD 拼接参考

评估项：

- 声纹相似度
- 粤语播报流畅度
- 停顿是否自然
- 是否明显减少“空白停顿带来的不稳定感”

### 5. 页面可解释性验收

页面必须能让用户直接看到：

- 当前参考音频处理方式
- 当前目标方言与风格
- 当前音色模仿策略
- 当前是否允许语速调整
- 回退原因与错误信息
