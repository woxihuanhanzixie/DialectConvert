# Demo1 下一步优化、评估、接口与网页规划

## 1. Summary

目标：

- 基于现有 Demo1 能力，完成“本地可运行、可演示、可扩展”的下一阶段规划。
- 规划重点从“离线脚本可跑”升级为“服务可调用 + 网页可展示 + 结果可评估”。
- 按用户偏好，首版网页采用 `Gradio`，优先做完整演示页，支持音频上传，尽量支持直接录音输入；前端先满足流程展示，不追求最终视觉完成度。
- 所有封装与接口设计必须为下一阶段的微信小程序、RAG、音色克隆、数字人和多方言扩展预留空间。

成功标准：

- Demo1 首版形成清晰的本地运行形态：`音频输入 -> ASR -> TN/改写 -> TTS -> 结果展示`。
- 服务层接口边界明确，后续可直接替换前端或接入小程序。
- 有一套可复现的评估方案，覆盖识别质量、改写质量、TTS 可用性和页面交互体验。
- 网页首版可完成上传/录音、文本展示、音频播放、错误反馈和基础日志展示。

范围：

- In scope：Demo1 下一步优化路线、评估方案、接口规划、网页界面规划、文件结构规划、阶段实施顺序、验收标准。
- Out of scope：本轮不直接实现微信小程序、不做正式 UI 视觉稿、不做云上部署执行、不做 Step3 音色克隆落地。

## 2. Current State Analysis

基于仓库与文档只读核查结果：

### 2.1 文档与目标现状

- `c:\Users\34005\Desktop\大赛\计划书_项目内容.md` 明确项目最终形态是面向濒危方言保护、学习、传播与活化的平台，应用层终态偏向微信小程序/APP 原型。
- `c:\Users\34005\Desktop\大赛\技术文档.md` 明确 Demo1 当前主链路目标为：
  - 普通话语音输入 -> ASR 转文本 -> LLM 方言改写 -> TTS 音色克隆 -> 方言语音输出。
- 结合当前实际代码状态，Demo1 已经完成了“ASR + 粤语改写 + 系统音色 TTS”的离线版验证，但尚未完成 HTTP 服务化和网页化。

### 2.2 已有能力

- ASR 批量评估脚本已存在：
  - `c:\Users\34005\Desktop\大赛\FireRedASR2S\examples_infer\asr\demo1_asr_eval.py`
- Step1 服务化雏形已存在：
  - `c:\Users\34005\Desktop\大赛\FireRedASR2S\asr_service\config.py`
  - `c:\Users\34005\Desktop\大赛\FireRedASR2S\asr_service\schemas.py`
- Step2 离线链路已存在：
  - `c:\Users\34005\Desktop\大赛\FireRedASR2S\fireredasr2s\dialect_pipeline\config.py`
  - `c:\Users\34005\Desktop\大赛\FireRedASR2S\fireredasr2s\dialect_pipeline\tn.py`
  - `c:\Users\34005\Desktop\大赛\FireRedASR2S\fireredasr2s\dialect_pipeline\rewrite.py`
  - `c:\Users\34005\Desktop\大赛\FireRedASR2S\fireredasr2s\dialect_pipeline\tts.py`
  - `c:\Users\34005\Desktop\大赛\FireRedASR2S\fireredasr2s\dialect_pipeline\run_batch_demo.py`
- 已有离线产物证明链路打通：
  - `c:\Users\34005\Desktop\大赛\FireRedASR2S\runtime_data\step2_output\results_audio16k_yue_tts.jsonl`
  - `c:\Users\34005\Desktop\大赛\FireRedASR2S\runtime_data\step2_output\audio\*.wav`

### 2.3 当前缺口

- `asr_service` 只有配置与 schema，没有真正的 `FastAPI` 入口与推理封装。
- `dialect_pipeline` 当前只有离线批处理脚本，没有服务层 API。
- 仓库中没有网页入口，没有 `Gradio/Streamlit` 页面，也没有静态前端。
- 当前结果虽然能落盘，但缺少统一 API 返回结构、trace 标识、前端消费友好字段和评估报告。
- Demo1 当前评估主要偏离线文本/jsonl 输出，还没有形成“接口可用性 + 页面交互体验 + 音频端到端可用性”的综合评估。

### 2.4 已锁定的用户偏好与决策

- 首版网页：`Gradio`
- 首版页面类型：完整演示页
- 首版目标：本地可运行 Demo
- 前端要求：先展示基础流程，不追求完美 UI
- 交互要求：优先支持音频上传；尽量支持直接录音；若浏览器录音链路受限，页面需明确反馈并保留上传兜底
- 架构要求：接口与封装要为下一阶段升级预留空间

## 3. Proposed Changes

### 3.1 总体实施顺序

建议按三层推进，而不是先堆前端：

1. 先补齐服务层：把现有 ASR 与 Step2 离线流程封装成稳定 API。
2. 再做 `Gradio` 演示层：直接消费本地 API 或本地 Python 服务。
3. 最后补评估与报告层：形成可复跑的指标统计、样本回放和问题归因。

原因：

- 如果先写页面而接口不稳定，后续改动会很大。
- 当前仓库已经有离线脚本基础，最自然的升级方式是“脚本 -> 服务 -> 页面”。

### 3.2 服务层规划

#### A. Step1 ASR 服务

建议在现有 `asr_service` 下补齐：

- `c:\Users\34005\Desktop\大赛\FireRedASR2S\asr_service\app.py`
  - `FastAPI` 入口
  - 提供 `/healthz`、`/api/v1/asr/transcribe`
- `c:\Users\34005\Desktop\大赛\FireRedASR2S\asr_service\asr_engine.py`
  - 统一封装 `FireRedAsr2` 模型加载与推理
  - 复用 `examples_infer/asr/demo1_asr_eval.py` 中的输入处理方式
- `c:\Users\34005\Desktop\大赛\FireRedASR2S\asr_service\audio_io.py`
  - 处理上传文件、录音文件、格式归一化
  - 统一约束输出为 `16kHz / mono / wav`

接口规划：

- `GET /healthz`
  - 返回服务状态、模型是否已加载
- `POST /api/v1/asr/transcribe`
  - 入参：音频文件，附加参数 `enable_punc`, `return_timestamp`
  - 出参：`uttid`, `text`, `confidence`, `timestamp`, `punc_text`, `latency_ms`, `audio_meta`

设计要求：

- 保持与 `asr_service/schemas.py` 一致风格
- 兼容将来接微信小程序上传
- 失败时统一返回错误码，如 `INVALID_AUDIO_FORMAT`, `ASR_ENGINE_ERROR`, `MODEL_NOT_READY`

#### B. Step2 方言与 TTS 服务

建议新增服务目录：

- `c:\Users\34005\Desktop\大赛\FireRedASR2S\dialect_service\`

建议新增文件：

- `dialect_service\app.py`
  - `FastAPI` 入口
  - 提供 `/healthz`、`/api/v1/dialect/rewrite`、`/api/v1/dialect/tts`、`/api/v1/dialect/pipeline`
- `dialect_service\schemas.py`
  - 明确请求/响应模型
- `dialect_service\pipeline_engine.py`
  - 复用 `fireredasr2s\dialect_pipeline` 现有逻辑
- `dialect_service\adapters.py`
  - 把 `tn.py`、`rewrite.py`、`tts.py` 的输入输出统一适配成接口层字段

接口规划：

- `POST /api/v1/dialect/rewrite`
  - 入参：`text`, `target_dialect`, `provider`, `segment_max_len`
  - 出参：`source_text`, `tn_text`, `rewrite_segments`, `dialect_text`, `degrade_mode`, `llm_model`, `llm_latency_ms`
- `POST /api/v1/dialect/tts`
  - 入参：`text`, `voice`, `model`, `language_type`
  - 出参：`wav_path`, `audio_url`, `expires_at`, `tts_model`, `tts_voice`, `latency_ms`, `error`
- `POST /api/v1/dialect/pipeline`
  - 入参：音频文件或文本；参数 `enable_asr`, `enable_rewrite`, `enable_tts`
  - 出参：完整链路结构：
    - `source_audio`
    - `asr`
    - `rewrite`
    - `tts`
    - `trace_id`
    - `total_latency_ms`

关键决策：

- 首版 `target_dialect` 先只支持 `yue`
- 首版 `pipeline` 支持两种输入：
  - 音频输入：走 `ASR -> Rewrite -> TTS`
  - 文本输入：跳过 ASR，直接 `Rewrite -> TTS`
- 首版 TTS 仍沿用当前已跑通的 `qwen3-tts-flash + Kiki`
- 所有接口都返回结构化中间态，方便页面完整展示

### 3.3 网页界面规划（Gradio）

建议新增目录：

- `c:\Users\34005\Desktop\大赛\FireRedASR2S\web_demo\`

建议新增文件：

- `web_demo\app.py`
  - `Gradio` 页面入口
- `web_demo\client.py`
  - 调用 `asr_service` 与 `dialect_service` 的本地客户端
- `web_demo\view_models.py`
  - 页面展示字段整理

首版页面结构：

#### 页面 1：完整演示页（主页面）

左侧输入区：

- 音频上传
- 浏览器录音组件
- 参数区：
  - 目标方言：默认粤语
  - 改写提供方：默认 DeepSeek
  - TTS 音色：默认 Kiki，可预留 Rocky
  - 开关：是否启用标点、是否启用 TTS

中间结果区：

- ASR 文本
- TN 文本
- 粤语改写文本
- 每步耗时
- 降级提示/错误提示

右侧输出区：

- 原音频播放器
- 生成的粤语音频播放器
- 下载按钮
- JSON 结果折叠面板

页面交互原则：

- 点击一次“开始转换”触发完整链路
- 每个阶段完成后立即展示结果，避免用户只看到最终失败
- 当录音不可用时，页面显式提示“当前环境录音不可用，请改用上传”

#### 页面 2：结果评估页（次页面，可同一 Gradio 内 Tab）

展示内容：

- 当前样本集运行统计
- 成功/失败条数
- 平均 ASR 耗时、平均改写耗时、平均 TTS 耗时
- 样本清单表格
- 点击样本查看：
  - 源文本
  - 粤语文本
  - 生成音频
  - 错误信息

原因：

- 符合技术文档里的“评估与展示并重”
- 也符合竞赛答辩对“结果可视化、链路清晰、指标可讲”的需求

### 3.4 音频输入与格式处理规划

当前技术文档明确输入规范为 `16kHz / 16-bit / mono / wav`，但网页端用户上传和浏览器录音通常不满足此规范，因此需要统一做格式处理。

建议：

- 服务层统一接收常见格式：`wav/mp3/m4a/webm`
- 内部统一转为 `16k mono wav`
- 页面层不承担格式转换责任，只负责提示和提交

实现决策：

- 若本地环境可用 `ffmpeg`，优先用 `ffmpeg`
- 若 `ffmpeg` 不可用，接口启动时检查并返回能力标识给页面
- 页面根据能力标识显示：
  - “录音可用且支持自动转码”
  - 或“仅支持 wav 上传”

这部分是首版必须明确反馈的点，不能“静默失败”。

### 3.5 Demo1 优化重点

#### A. 文本链路优化

- 在 `rewrite` 前增加一层“ASR 审查/纠错”步骤，不再直接把 ASR 文本送入方言改写。
- 优化 `tn.py` 的断句策略，减少长句被切坏的问题
- 增加 `tn_diff` 或规范化变更记录，便于人工核查
- 增加改写提示词中的输出约束，减少口语化不足、重复、半句残留

优先关注当前已有暴露问题的样本：

- 长句分段错裂
- ASR 残缺导致改写结果不自然
- 个别样本存在“同样嘅库里都系世界上非”这类不完整片段

建议把文本链路从三段改为四段：

1. `ASR`
2. `ASR Review / Repair`
3. `TN + Rewrite`
4. `TTS`

新增的 `ASR Review / Repair` 目标：

- 基于上下文修正明显 ASR 错误
- 修正同音字/近音字误识别，如“话/画”、“他/她/它”、“在/再”
- 修正明显断裂句和残句
- 保留原始 ASR 文本，避免“纠错后不可追溯”

建议新增服务与字段：

- 新增接口：
  - `POST /api/v1/text/review`
- 新增返回字段：
  - `asr_raw_text`
  - `asr_reviewed_text`
  - `asr_review_notes`
  - `review_degrade_mode`
  - `review_model`
  - `review_latency_ms`

建议实现策略：

- 第一层：规则校验
  - 标点重复
  - 异常断句
  - 明显 OCR/ASR 脏字符
- 第二层：LLM 语境修正
  - 给定“这是 ASR 结果，请在不改变原意的前提下，只修正明显识别错误和同音错字”
  - 严格禁止自由改写和扩写
- 第三层：回退机制
  - 若 LLM 无法确认，则保留原始 ASR 文本
  - 页面展示“原始文本 vs 审查后文本”供人工核查

#### B. TTS 链路优化

- 为 TTS 增加 `latency_ms` 统计
- 增加本地音频下载成功校验
- 增加音频文件大小、时长等基础元数据
- 首版支持 `Kiki/Rocky` 两种粤语音色切换

#### C. 工程优化

- 增加 `.env.example`
- 把当前 CLI 命令整理为文档与启动说明
- 为页面运行准备统一启动脚本
- 接口层统一 `trace_id`

### 3.6 评估方案规划

#### A. 功能评估

验证 5 类能力：

1. 音频上传后可稳定返回 ASR 文本
2. ASR 文本可先经过审查/纠错并输出修正结果
3. 修正后的文本可稳定生成粤语文本
4. 粤语文本可稳定生成音频
5. 页面可完整展示全链路结果

#### B. 质量评估

ASR：

- 空结果率
- 文本可读性
- 关键信息保留率

ASR 审查/纠错：

- 明显错字修正率
- 同音字纠错有效率
- 误修正率
- 人工可接受率

粤语改写：

- 语义保持
- 粤语自然度
- 长句稳定性

TTS：

- 可播放率
- 音频完整性
- 主观自然度

网页：

- 上传成功率
- 录音成功率
- 首屏反馈时间
- 端到端完成时间

#### C. 指标口径

建议形成首版基线表：

- `num_samples`
- `asr_success_rate`
- `review_success_rate`
- `rewrite_success_rate`
- `tts_success_rate`
- `avg_asr_latency_ms`
- `avg_review_latency_ms`
- `avg_rewrite_latency_ms`
- `avg_tts_latency_ms`
- `avg_total_latency_ms`
- `audio_playable_rate`

质量打分建议采用人工 5 分制：

- ASR 可读性：1-5
- 审查后文本准确性：1-5
- 粤语自然度：1-5
- TTS 自然度：1-5
- 页面演示流畅度：1-5

人工审核必须作为正式验收项，而不是可选项：

- 每条样本至少审核：
  - 原始音频表达的核心意思是否被 ASR 识别正确
  - 审查后文本是否比原始 ASR 更接近真实语义
  - 粤语改写是否和审查后文本语义一致
  - TTS 读出来的内容是否与最终粤语文本一致

#### D. 验收样本建议

分三组：

- A 组：`runtime_data/audio_16k` 的 9 条现有样本
- B 组：人工 10 条短句
- C 组：1~3 条校园场景真实录音（宿舍/教室）

### 3.7 文档与报告规划

建议新增：

- `c:\Users\34005\Desktop\大赛\FireRedASR2S\docs\demo1_web_demo.md`
  - 启动说明
  - 页面说明
  - 接口说明
  - 常见问题
- `c:\Users\34005\Desktop\大赛\FireRedASR2S\runtime_data\step2_output\report_demo1_web.md`
  - 每轮运行后的样本统计与问题记录

原因：

- 竞赛展示需要“可讲述的交付物”
- 后续切换到小程序或正式前端时，这份文档可以直接做接口协作依据

## 4. Assumptions & Decisions

关键假设：

- 近期重点仍是 Demo1 的本地演示与可视化，而非直接上云上线。
- 网页首版只要清晰、稳定、能展示链路即可，不需要正式产品化 UI。
- 页面首版可接受以 Gradio 为壳，但接口层必须按后续可替换前端来设计。

关键决策（已锁定）：

- 网页框架：`Gradio`
- 页面范围：完整演示页优先
- 运行形态：本地 Demo 优先
- 后端接口：`FastAPI`
- 首版目标方言：粤语
- 首版改写通道：DeepSeek 默认，Qwen 预留
- 首版 TTS：Qwen3-TTS 系统音色方案，先不做音色克隆
- 前端交互：上传优先，录音为增强能力；若浏览器录音或转码受限，必须及时提示

## 5. Verification Steps

### 5.1 服务层验收

1. 启动 `asr_service` 后，`/healthz` 返回可用状态。
2. 上传一条 `wav` 到 `/api/v1/asr/transcribe`，返回 `text/confidence/latency_ms`。
3. 调用 `/api/v1/text/review`，返回原始 ASR 文本与审查后文本。
4. 调用 `/api/v1/dialect/rewrite`，返回 `tn_text/dialect_text`。
5. 调用 `/api/v1/dialect/tts`，返回 `wav_path/audio_url`。
6. 调用 `/api/v1/dialect/pipeline`，返回完整链路结构与 `trace_id`。

### 5.2 网页验收

1. 本地打开 Gradio 页面。
2. 上传音频后，页面展示：
   - 原音频
   - ASR 原始文本
   - 审查后文本
   - TN 文本
   - 粤语文本
   - 粤语音频播放器
3. 若浏览器录音可用，录音后可完成同样流程。
4. 若录音不可用或转码失败，页面出现明确提示，而不是无响应。
5. 页面支持人工对照查看“原始 ASR -> 审查后文本 -> 粤语文本”的三级变化。

### 5.3 样本验收

1. 使用 `runtime_data/audio_16k` 的 9 条样本完整跑通。
2. 使用人工 10 条短句跑通文本链路与 TTS 链路。
3. 每条样本进行人工审核并记录：
   - 原始音频真实语义
   - ASR 原始输出是否对齐
   - 审查后文本是否修正成功
   - 粤语改写是否保义
   - TTS 是否朗读正确
4. 抽样试听并记录以下问题：
   - ASR 错词
   - ASR 纠错误修正
   - 改写偏义
   - TTS 播放异常
   - 页面交互卡顿

### 5.4 阶段交付验收

最终应形成：

- 可运行的本地 API 服务
- 可运行的 Gradio 演示页
- 一份接口说明
- 一份评估结果报告
- 一份下一阶段升级接口保留说明
