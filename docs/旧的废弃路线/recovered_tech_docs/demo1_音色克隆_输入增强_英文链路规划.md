# Demo1 下一步规划：音色克隆、输入增强与英文链路

## 1. Summary

目标：

- 在当前 Demo1 已打通 `ASR -> 审查/改写 -> TTS` 的基础上，规划下一阶段的三项升级：
  - 实现“输出与原声音接近”的音色克隆能力；
  - 对输入音频增加轻量增强与质量评估，提升 ASR 与音色克隆稳定性；
  - 支持英文输入，并接入后续“英文 -> 粤语文本 -> 粤语语音”的完整链路。

成功标准：

- 首版音色克隆优先通过 API 路线打通，并保留本地开源方案的扩展接口。
- 输入音频不直接做强降噪，而是优先做轻量增强、质量诊断和双轨保留，避免破坏原音色。
- 英文输入可以在 ASR 侧稳定识别，并进入后续粤语生成链路。
- 所有新增设计都能兼容后续对音色模型、增强策略和语言流程的调整。

范围：

- In scope：音色克隆路线规划、输入增强规划、英文输入链路规划、接口与页面规划、评估方案、风险与阶段顺序。
- Out of scope：本轮不直接实现最终模型训练、不做正式云部署、不做强降噪模型微调。

## 2. Current State Analysis

### 2.1 仓库现状

- 当前仓库已经有 Demo1 的网页与服务化入口：
  - `c:\Users\34005\Desktop\大赛\FireRedASR2S\asr_service\`
  - `c:\Users\34005\Desktop\大赛\FireRedASR2S\dialect_service\`
  - `c:\Users\34005\Desktop\大赛\FireRedASR2S\web_demo\`
- 当前 Step2 配置与 TTS 仅支持系统音色：
  - `c:\Users\34005\Desktop\大赛\FireRedASR2S\fireredasr2s\dialect_pipeline\config.py`
  - `c:\Users\34005\Desktop\大赛\FireRedASR2S\fireredasr2s\dialect_pipeline\tts.py`
- 当前 `dialect_service/pipeline_engine.py` 使用 `asr_service.asr_engine`，只调用纯 ASR + Punc，没有接入 `FireRedASR2System` 的 VAD/LID 联动。
- 当前输入音频处理仅做格式统一：
  - `c:\Users\34005\Desktop\大赛\FireRedASR2S\asr_service\audio_io.py`
  - 现有能力只有：转 `16kHz / mono / wav`、重采样、声道合并；
  - 没有响度归一、削峰检查、静音裁剪、质量评分、降噪分支。

### 2.2 FireRedASR2S 可直接复用的能力

基于 `README.md` 与代码核查：

- `FireRedASR2` 原生支持：
  - 中文普通话
  - 20+ 方言/口音
  - 英文
  - 中英混说
- `FireRedPunc` 支持中英文标点恢复。
- `FireRedLID` 支持 100+ 语言与 20+ 中文方言/口音识别。
- `FireRedVAD` 支持多语种语音活动检测。
- `fireredasr2s/fireredasr2system.py` 已经把 `VAD + LID + ASR + Punc` 串成统一系统入口。

这说明：

- “英文输入 ASR”不是新增模型能力，而是把当前 Demo1 从“只用 ASR 模块”升级为“优先用 ASR System 入口”。
- “输入音频需不需要增强”的答案是：需要，但首版更适合做轻量增强和质量评估，而不是先做强降噪。

### 2.3 当前缺口

#### A. 音色克隆

- 当前 `tts.py` 只支持 `qwen3-tts-flash` 一类系统音色。
- 当前配置没有 `speaker_ref_audio`、`voice_clone_provider`、`clone_mode` 等字段。
- 当前接口没有上传参考音频的能力。
- 当前网页没有“原声参考音频”输入位和“音色相似度/来源说明”展示位。

#### B. 输入增强

- 当前输入只做格式转换，没有质量量化指标。
- 当前对音频噪声、响度波动、削波、长静音、录音质量差异缺乏结构化诊断。
- 当前没有区分“ASR 工作音频”和“音色克隆参考音频”。

#### C. 英文链路

- 当前 `dialect_service` 的改写逻辑默认假设输入是中文。
- 当前 `review` 与 `rewrite` 提示词是中文/粤语场景，没有英文分支。
- 当前 pipeline 不输出语言识别信息，也没有英文转粤语的中间状态字段。

### 2.4 已确认的用户偏好与决策

- 音色克隆：双路线规划
  - 首版先用 API
  - 同时预留本地开源克隆接口
- 英文输入：首版走“英文转粤语”
- 输入增强：首版采用轻量增强
- 约束：
  - 要保留原音色空间，不能为了识别效果强行破坏声纹
  - 后续音色方案可能变化，因此接口与数据结构要保留可替换性

### 2.5 结合外部模型信息的判断

- Qwen TTS 体系中已经有面向声音复刻的 `qwen3-tts-vc`，适合作为首版 API 克隆路线。
- 同时，本地开源零样本/小样本音色克隆可以预留 `GPT-SoVITS` / `Fish-Speech` 一类 provider 接口，但不建议首版直接把本地训练/部署作为主路径。

## 3. Proposed Changes

### 3.1 总体阶段顺序

建议分 3 个阶段推进：

1. 先升级输入与 ASR 主链路：
   - 接入 `FireRedAsr2System`
   - 加入轻量增强与质量诊断
   - 输出语言识别结果
2. 再接入音色克隆：
   - 首版接 `Qwen3-TTS-VC`
   - 保留本地开源 provider 抽象
3. 最后扩英文到粤语的完整页面与评估闭环

原因：

- 如果不先解决输入质量和语言识别，音色克隆和英文链路都会建立在不稳定输入之上。
- 当前仓库已经有 `VAD/LID/Punc` 能力，优先串起来性价比最高。

### 3.2 输入音频增强规划

#### 核心决策

首版不做“强降噪优先”，而是采用“双轨输入 + 轻量增强”：

- `raw_audio`
  - 保留原始上传音频
  - 用于后续音色克隆参考
- `work_audio`
  - 用于 ASR / VAD / LID
  - 做轻量增强，但尽量不改变音色特征

#### 为什么不先强降噪

- 音色克隆最怕参考音频被过度处理，强降噪、AGC、去混响会直接改变声纹和动态。
- 当前你关注“原声音一致”，所以必须优先保护参考音频。
- 更合理的做法是：
  - 对 ASR 工作流使用轻量增强；
  - 对音色参考保留原始音频，同时只做诊断，不默认重处理。

#### 建议新增/改造文件

- `c:\Users\34005\Desktop\大赛\FireRedASR2S\asr_service\audio_io.py`
  - 扩展为双轨输出：
    - `raw_path`
    - `work_path`
  - 增加轻量处理：
    - 峰值检查
    - RMS/响度估计
    - 静音占比估计
    - 长静音裁剪
    - 可选轻量峰值归一
- 新增 `c:\Users\34005\Desktop\大赛\FireRedASR2S\asr_service\audio_quality.py`
  - 计算质量分与风险标签：
    - `clipping_ratio`
    - `silence_ratio`
    - `rms_db`
    - `peak_db`
    - `duration_s`
    - `quality_score`
    - `quality_flags`
- 新增 `c:\Users\34005\Desktop\大赛\FireRedASR2S\asr_service\audio_frontend.py`
  - 集中处理增强策略：
    - `none`
    - `light_asr_safe`
    - `clone_ref_safe`

#### 首版增强策略

- `light_asr_safe`：
  - 统一采样率与单声道
  - 静音裁剪
  - 削波/过载检测
  - 轻量峰值归一
  - 不引入重度频谱降噪
- `clone_ref_safe`：
  - 保留原始音频
  - 只做时长裁剪和格式统一
  - 不做 AGC / 强降噪 / 频谱重塑

### 3.3 ASR 主链路升级规划

#### 核心决策

把当前 Demo1 从“直接调 `FireRedAsr2`”升级为“优先调 `FireRedAsr2System`”。

原因：

- `FireRedAsr2System` 已经包含：
  - VAD
  - LID
  - ASR
  - Punc
- 这对 noisy input、英文输入、后续多语言分支都更合适。

#### 建议新增/改造文件

- `c:\Users\34005\Desktop\大赛\FireRedASR2S\asr_service\system_engine.py`
  - 封装 `FireRedAsr2System`
  - 返回：
    - `text`
    - `sentences`
    - `lang`
    - `lang_confidence`
    - `vad_segments_ms`
    - `words`
- `c:\Users\34005\Desktop\大赛\FireRedASR2S\asr_service\schemas.py`
  - 增加：
    - `audio_quality`
    - `detected_languages`
    - `vad_segments_ms`
    - `sentences`
- `c:\Users\34005\Desktop\大赛\FireRedASR2S\asr_service\app.py`
  - 增加参数：
    - `enable_vad`
    - `enable_lid`
    - `frontend_mode`
  - 输出工作音频与质量信息

#### 首版行为

- 中文/英文/中英混说音频统一先过：
  - `audio_frontend`
  - `FireRedAsr2System`
- 以 `LID` 的主语言输出决定后续 rewrite 分支。

### 3.4 英文输入链路规划

#### 核心决策

首版英文链路采用“英文识别 -> 英文审查 -> 英文转粤语语义改写 -> 粤语 TTS/VC”。

但为了最大化复用现有中文改写链路，建议引入一个中间字段：

- `pivot_text_zh`

推荐流程：

1. `ASR System` 输出英文文本与语言标签
2. `English Review`
   - 修正英文 ASR 的标点、断句、明显错词
3. `English -> Pivot Chinese`
   - 把英文语义稳定翻译成普通话中间文本
4. `Pivot Chinese -> Cantonese Rewrite`
   - 复用当前更成熟的粤语改写逻辑
5. `TTS / VC`

#### 为什么推荐加 `pivot_text_zh`

- 当前现有 `review/rewrite` 逻辑明显偏中文和粤语。
- 直接“英文 -> 粤语”虽然可行，但 prompt 稳定性和可调试性更差。
- 有 `pivot_text_zh` 后：
  - 页面更容易展示中间态；
  - 人工审核更直观；
  - 后续支持其他外语时也能复用。

#### 建议新增/改造文件

- `c:\Users\34005\Desktop\大赛\FireRedASR2S\dialect_service\adapters.py`
  - 增加：
    - `review_asr_text_en()`
    - `translate_en_to_pivot_zh()`
    - `rewrite_to_cantonese_from_pivot()`
- `c:\Users\34005\Desktop\大赛\FireRedASR2S\dialect_service\schemas.py`
  - 增加字段：
    - `input_lang`
    - `pivot_text_zh`
    - `translation_notes`
- `c:\Users\34005\Desktop\大赛\FireRedASR2S\dialect_service\pipeline_engine.py`
  - 根据 `lang` 分流：
    - `zh*` -> 现有中文链路
    - `en` -> 英文 review + pivot + 粤语 rewrite

### 3.5 音色克隆规划

#### 核心决策

采用双路线 Provider 抽象：

- 主路线：
  - `provider=qwen_vc`
  - 使用 `qwen3-tts-vc`
- 预留路线：
  - `provider=gpt_sovits`
  - `provider=fish_speech`

#### 为什么 API 先行

- 当前目标是 Demo1 下一步验证和竞赛展示，不是立即自建复杂 TTS 集群。
- API 路线更快得到“原音色接近”的结果，便于先验证产品体验。
- 同时要在架构上保留本地 provider，避免后续被单一路线锁死。

#### 建议新增/改造文件

- `c:\Users\34005\Desktop\大赛\FireRedASR2S\fireredasr2s\dialect_pipeline\config.py`
  - 新增：
    - `voice_clone_provider`
    - `qwen_tts_vc_model`
    - `speaker_ref_audio_max_s`
    - `speaker_ref_audio_min_s`
    - `speaker_ref_keep_raw`
    - `local_clone_provider`
- `c:\Users\34005\Desktop\大赛\FireRedASR2S\fireredasr2s\dialect_pipeline\tts.py`
  - 从“单一系统音色 TTS”扩展为统一接口：
    - `synthesize_standard_tts()`
    - `synthesize_voice_clone()`
  - 增加 `Qwen VC` 调用封装
- 新增 `c:\Users\34005\Desktop\大赛\FireRedASR2S\fireredasr2s\dialect_pipeline\voice_clone.py`
  - 统一 provider 适配层：
    - `qwen_vc`
    - `gpt_sovits`
    - `fish_speech`
- `c:\Users\34005\Desktop\大赛\FireRedASR2S\dialect_service\schemas.py`
  - 在 `TtsRequest` 和 `PipelineResponse` 中增加：
    - `voice_clone_enabled`
    - `speaker_ref_audio`
    - `voice_clone_provider`
    - `speaker_similarity_note`
    - `clone_mode`
- `c:\Users\34005\Desktop\大赛\FireRedASR2S\dialect_service\app.py`
  - `pipeline` 接口支持上传：
    - 主输入音频
    - 参考音频 `speaker_ref_audio`
- `c:\Users\34005\Desktop\大赛\FireRedASR2S\dialect_service\pipeline_engine.py`
  - 当 `voice_clone_enabled=1` 时：
    - 优先用参考音频克隆；
    - 没有参考音频则回退系统音色；
    - 记录回退信息。

#### 参考音频策略

首版对参考音频设置明确约束：

- 建议时长：
  - 3~10 秒
- 条件：
  - 单人说话
  - 少背景音
  - 少混响
  - 少音乐/环境声
- 处理原则：
  - 保留原始声纹；
  - 仅做轻量裁剪与格式统一；
  - 不做强降噪。

### 3.6 网页与交互规划

建议改造：

- `c:\Users\34005\Desktop\大赛\FireRedASR2S\web_demo\app.py`

新增界面元素：

- 主音频输入
- 参考音频输入（用于音色克隆）
- 前端策略显示：
  - 原始音频质量分
  - 工作音频质量分
  - 是否触发风险标记
- 语言识别展示：
  - `zh mandarin / zh-yue / en`
- 英文链路展示：
  - `ASR 原文`
  - `Review 后文本`
  - `Pivot 中文`
  - `粤语文本`
- 音色输出说明：
  - `系统音色 / 克隆音色`
  - `provider`
  - `参考音频是否生效`
  - `回退原因`

#### 页面上的关键说明

- 若输入音频质量差，不直接拒绝，而是：
  - 提示“建议重录”
  - 同时允许继续跑
- 若参考音频质量不达标：
  - 回退系统音色
  - 页面明确展示回退原因

### 3.7 评估方案

#### A. 输入音频评估

新增指标：

- `quality_score`
- `clipping_ratio`
- `silence_ratio`
- `peak_db`
- `rms_db`
- `vad_coverage`

#### B. 英文链路评估

新增样本组：

- 3~5 条纯英文校园句子
- 3~5 条中英混说句子

评估项：

- 英文 ASR 可读性
- `LID` 识别正确率
- `pivot_text_zh` 语义保持
- 最终粤语文本与原英文语义一致性

#### C. 音色克隆评估

首版采用主观人工评估：

- 音色相似度：1-5
- 内容可懂度：1-5
- 方言自然度：1-5
- 情绪/停顿保真度：1-5

关键对照组：

- 系统音色输出
- Qwen VC 输出

#### D. 人工审核必须保留

对每条音频，至少审核：

- 原始音频质量是否达标
- 语言识别是否正确
- 审查后文本是否保义
- `pivot_text_zh` 是否准确
- 粤语文本是否保义
- 克隆音色是否接近原声

### 3.8 文档规划

建议新增：

- `c:\Users\34005\Desktop\大赛\FireRedASR2S\docs\demo1_voice_clone_plan.md`
  - 音色克隆架构、provider 说明、参考音频规范
- `c:\Users\34005\Desktop\大赛\FireRedASR2S\docs\demo1_audio_frontend.md`
  - 输入增强策略、质量评分说明
- `c:\Users\34005\Desktop\大赛\FireRedASR2S\docs\demo1_english_pipeline.md`
  - 英文 -> 粤语链路说明

## 4. Assumptions & Decisions

关键假设：

- 当前优先目标仍是 Demo1 本地可演示，而不是一次性追求生产级音色克隆质量。
- 首版音色克隆更适合作为“体验验证”，不是最终声纹强一致方案。
- 输入音频质量问题会直接影响：
  - ASR 稳定性
  - 语言识别
  - 参考音频克隆效果

关键决策（已锁定）：

- 音色路线：双路线规划
- 首版主路线：Qwen VC API
- 本地开源路线：保留接口，不作为首版主执行
- 英文链路：英文输入最终转粤语输出
- 输入增强：轻量增强优先
- 参考音频：保留 raw，不默认强降噪
- ASR 升级：优先切到 `FireRedAsr2System`

## 5. Verification Steps

### 5.1 输入增强验收

1. 上传原始音频后，返回：
   - `raw_path`
   - `work_path`
   - `quality_score`
   - `quality_flags`
2. 对同一条音频：
   - `raw_audio` 保留不变
   - `work_audio` 可用于 ASR
3. 对有噪点或响度不稳的样本：
   - 页面能显示质量风险，而不是静默失败

### 5.2 ASR System 验收

1. 中文样本返回 `lang=zh*`
2. 英文样本返回 `lang=en`
3. 中英混说样本能正常出文本，且句级语言信息可展示

### 5.3 英文链路验收

1. 英文音频进入 pipeline
2. 输出：
   - `asr_text_en`
   - `reviewed_text_en`
   - `pivot_text_zh`
   - `dialect_text_yue`
3. 最终成功生成粤语语音

### 5.4 音色克隆验收

1. 上传 3~10 秒参考音频
2. 调用 `qwen3-tts-vc` 成功生成输出音频
3. 页面显示：
   - 当前 provider
   - 是否使用克隆
   - 回退原因
4. 若参考音频不达标：
   - 自动回退系统音色
   - 不中断整条任务

### 5.5 阶段交付验收

最终应形成：

- 输入增强与质量评分模块
- 基于 `FireRedAsr2System` 的 ASR 主链路
- 英文到粤语的完整文本/语音链路
- 基于 Qwen VC 的首版音色克隆能力
- 保留本地开源克隆 provider 扩展接口
- 对应页面、接口和评估文档
