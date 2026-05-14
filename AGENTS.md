# Agent Project Notes

更新时间：2026-05-12

## 项目定位

本项目是《声临其境》Demo 一期的工程实现。随着项目演进，为满足“本地独立全流程跑通”与“公网轻量化演示”的不同需求，当前项目并存两条核心技术路线：

1. **公网运行思路（云端轻量化与 API 调用为主）**
2. **原本的本地运行逻辑（本地全流程闭环）**

本项目的核心目标是打通一条可演示的多模态闭环：保证中文语义准确，生成发音和流畅度稳定的方言音频，并实现音色迁移。

---

## 技术路线演进 (Technical Routes)

### 1. 公网运行思路 (Public Cloud Route)
为了实现网页的公网部署，并避免强制依赖昂贵的云端 GPU 服务器，公网路线主要依赖外部 API 调用实现语音转写和生成，利用 LLM 确认中间层的语义内容。
*   **路线 A (端到端语音生成)**：`音频 -> Cosy Voice -> 输出`。利用端到端模型实现快速的方言/音色合成。
*   **路线 B (文本驱动兜底)**：`Text文字 -> LLM (语义内容确定) -> 兜底音频输出 (方言)`。
*   **架构特点**：网页实现不需要重度部署到云端服务器 GPU 上，而是作为 API 调用的编排层。同时保留了多语言的实现，并为后续可能增加的 RAG（检索增强生成）预留了接口。

### 2. 原本的本地运行逻辑 (Original Local Route)
这是本项目最初且目前仍在使用的本地全流程跑通方案，它证明了在本地环境下可以基本实现自给自足的全链路运行。
*   **核心闭环**：`音频输入 -> FireRedASR (处理音频输入转写) -> LLM (文本审查与方言改写) -> Qwen TTS (输出为 Gold Teacher) -> Voice Matched (使用 OpenVoice/RVC clone音色)`。
*   **处理音频输入**：音频输入先经过声学前端、VAD、LID、ASR、Punc (FireRedASR)。
*   **LLM 语义层**：ASR 文本进入 LLM 审查纠错，并生成稳定的中间层文本。
*   **Gold Teacher 层**：Qwen/DashScope TTS 负责“怎么说”，生成发音和流畅度稳定的标准方言音频。
*   **Voice Matched 层**：以 Gold Teacher 音频为源，利用本地 OpenVoice 或 RVC 等音色转换模型，把参考说话人的音色迁移过来，负责“像谁说”。

---

## 当前真实业务逻辑 (基于本地与混合路线)

### 1. 文本与语义层

文本层的目标是保证“意思准、结构清楚、能给后续音频生成使用”。它不是最终音频质量的唯一来源。

主流程：

1. 音频输入先经过声学前端、VAD、LID、ASR、Punc。
2. ASR 文本进入 LLM 审查纠错，修正明显错字、断句、同音字和标点。
3. 如果输入是英文，会先翻译成普通话 pivot 文本。
4. rewrite / pronunciation / prosody 层生成调试文本：
   - `semantic_text`：语义层，页面展示与 Gold Teacher 输入的主要候选。
   - `pronunciation_text`：发音提示层，用于处理高风险词和容易被普通话读法带偏的词。
   - `prosody_text`：韵律提示层，用于连接词、停顿和口语连贯性调试。

注意：这些文本可以辅助 TTS，但不能假设“方言文本直接读出来就合理”。尤其新增四川话、闽南语等方言时，不能只靠替换词表或普通 LLM 改写当作最终方案，最终要看 Gold Teacher 音频是否自然。

### 2. Gold Teacher 音频层

Gold Teacher 是当前音频主链路的发音和流畅度标准。

实现位置：

- `FireRedASR2S/fireredasr2s/dialect_pipeline/tts.py`
  - `synthesize_standard_tts()`：直接调用 Qwen/DashScope TTS。
  - `synthesize_gold_teacher()`：复用 `synthesize_standard_tts()` 生成 teacher 音频，并补充 `teacher_role`、`teacher_input_text`、`teacher_wav_path` 等字段。
- `FireRedASR2S/dialect_service/adapters.py`
  - `tts_gold_teacher()`：服务层封装，补充 route 信息、耗时、fallback 字段。
- `FireRedASR2S/dialect_service/pipeline_engine.py`
  - 先生成 `gold_teacher` route，再决定是否生成 `voice_matched` route。

业务含义：

- Gold Teacher 负责“怎么说”：发音、顺滑度、句间连接、基础自然度。
- Gold Teacher 不负责“像谁说”：它通常是系统音色。
- 当音色转换失败、未配置或没有参考音频时，主试听应回退到 Gold Teacher，不应让文本克隆结果成为推荐主输出。

### 3. Voice Matched 音色迁移层

Voice Matched 才是“音色模拟”的主目标。它不是重新从文本生成一条克隆语音，而是以 Gold Teacher 音频为 source，再把参考音频中的说话人音色迁移过来。

实现位置：

- `FireRedASR2S/fireredasr2s/dialect_pipeline/voice_clone.py`
  - `convert_voice_from_teacher(teacher_wav_path, ref_audio_path, out_wav, cfg, preferred_name)`：audio-to-audio 音色转换统一入口。
  - `provider == openvoice`：调用 OpenVoiceRuntime 子进程。
  - `provider == rvc`：调用 RVC 子进程。
  - `qwen_vc` 保留为 legacy 文本克隆配置，不是 teacher-first 主链路。
- `OpenVoiceRuntime/run_openvoice_convert.py`
  - 输入 `--teacher-wav`、`--ref-audio`、`--out-wav`。
  - 抽取 teacher wav 的 source speaker embedding。
  - 抽取参考音频的 target speaker embedding。
  - 调用 OpenVoice `ToneColorConverter.convert(...)` 输出 voice matched wav。
- `FireRedASR2S/dialect_service/adapters.py`
  - `tts_voice_match_from_teacher()`：把 `synthesize_voice_matched_from_teacher()` 包成 route 结果。

业务含义：

- Voice Matched 负责“像谁说”：音色、声纹接近、参考说话人特征。
- Voice Matched 不重新决定文本内容、方言发音或韵律；这些应尽量继承 Gold Teacher。
- 如果 voice conversion provider 不可用，`voice_matched` 应清楚返回错误和 fallback reason，页面推荐回退 Gold Teacher。

### 4. Legacy Text Clone 的位置

旧的 Qwen3-TTS-VC 文本克隆路线本质是：`文本 + 参考音频 -> 克隆语音`。它会重新决定发音、停顿和韵律，因此不再适合作为当前主路线。

保留它的意义：

- 兼容历史实验。
- 做对照评估。
- 作为 future fallback 的可能性。

不要把 legacy text clone 作为推荐主输出，也不要把它等同于 teacher-first voice matched。

### 5. 方言转化与多方言扩展

方言转化在当前 Demo 中主要承担三件事：

- 保证语义从普通话输入稳定迁移到目标方言/口语风格。
- 给 Qwen Gold Teacher 提供明确的风格目标和必要的口语提示。
- 给页面和调试日志展示可解释的中间层结果。

新增四川话、闽南语等方言时，正确方向是：

- 在服务/API/UI 层增加目标方言选择。
- 让目标方言影响 Gold Teacher 的合成策略、voice、style instruction 或 prompt。
- 文本层只做辅助，不把词表替换当作最终业务成果。
- 评估重点放在最终 `gold_teacher.wav` 和 `voice_matched.wav` 听感上。

## 工作区结构

工作区根目录：`D:\Competition`

- `AGENTS.md`：本文件，给 Agent 快速接手项目使用。
- `技术文档.md`：项目方案、Demo1 工作流、Demo2/功能 3/4/6 演进说明。
- `任务未完成记录.md`：记录当前未完成任务，主要是 OpenVoice 与 RVC 双模型链路尚未完整闭环。
- `声临其境项目计划书.docx`：项目计划书原文档。
- `.trae/documents`：历史实施计划、测试计划、优化评估等技术记录。
- `FireRedASR2S`：核心源码、服务、模型、运行数据和 Web Demo。
- `OpenVoiceRuntime`：OpenVoice 运行脚本、缓存、speaker embedding 与调试产物。
- `openvoice_gpu_venv`、`.conda_pkgs`：本地 Python/Conda 运行环境和包缓存，通常不作为源码修改对象。

## FireRedASR2S 结构

项目根目录：`D:\Competition\FireRedASR2S`

- `asr_service`：ASR FastAPI 服务，负责音频归一化、声学前端处理、FireRed ASR2 System 调用和降级转写。
- `dialect_service`：方言处理 FastAPI 服务，串联 ASR、审查纠错、方言/风格控制、Gold Teacher TTS、Voice Matched、输出对比。
- `web_demo`：Gradio Web 演示页，面向本地演示完整链路。
- `public_web`：公网轻量前端，纯静态 HTML/JS，适合部署到 Nginx 暴露公网。
- `fireredasr2s`：核心 Python 包，包含 FireRed ASR2、LID、Punc、VAD 与 Demo1 方言/语音管线。
- `docs`：Demo1 局部说明文档和 recovered 技术规划。
- `assets`：示例音频和图片素材。
- `examples_infer`：官方/示例推理输入输出。
- `runtime_data`：运行时模型、上传音频、ASR 输出、Step2 输出、Web Demo 预览等。
- `runtime`、`rvc_runtime_space`：Triton/RVC/OpenVoice 等运行相关目录和依赖空间。
- `pretrained_models`：预训练模型目录。
- `start_demo1_web.ps1`：本地启动 Demo1 Web 的 PowerShell 脚本。

## 核心服务与入口

### ASR 服务

入口：`D:\Competition\FireRedASR2S\asr_service\app.py`

- `GET /healthz`：返回运行能力、plain ASR 和 ASR system 健康状态。
- `POST /api/v1/asr/transcribe`：接收上传音频，归一化为 wav，默认启用 VAD、LID、Punc，优先调用 `FireRedAsr2System`，失败时降级到 plain ASR。

关键文件：

- `asr_service/config.py`：从环境变量读取模型路径、GPU/half、beam、batch、默认 VAD/LID/Punc 开关和声学前端模式。
- `asr_service/system_engine.py`：封装 `FireRedAsr2System`，负责 VAD/LID/ASR/Punc 组合推理、ASCII 模型缓存路径处理、平均置信度与耗时统计。
- `asr_service/asr_engine.py`：plain ASR 降级引擎。
- `asr_service/audio_io.py`：上传音频归一化、转码、临时目录和运行能力探测。
- `asr_service/audio_frontend.py`、`audio_quality.py`：前端声学增强、质量统计与处理策略。
- `asr_service/schemas.py`：ASR API 的 Pydantic 响应结构。

### 方言与音频服务

入口：`D:\Competition\FireRedASR2S\dialect_service\app.py`

- `GET /healthz`：返回支持方言、默认声音和运行配置。
- `POST /api/v1/text/review`：对 ASR 文本进行审查纠错。
- `POST /api/v1/dialect/rewrite`：生成语义/方言/发音/韵律中间文本，主要用于控制与调试。
- `POST /api/v1/dialect/tts`：文本到语音，支持系统音色或历史文本克隆参数。
- `POST /api/v1/dialect/pipeline`：完整链路入口，支持音频文件或纯文本输入，可附带参考音频。

关键文件：

- `dialect_service/pipeline_engine.py`：主编排器 `DialectPipelineEngine`，实现 `process_text`、`process_audio`、`gold_teacher`、`voice_matched`、差异总结、推荐主输出、issue tags 和总耗时。
- `dialect_service/adapters.py`：封装 LLM 审查、英文 pivot 翻译、方言/风格中间层、Qwen/DashScope TTS、Gold Teacher、Voice Match 调用。
- `dialect_service/schemas.py`：Review、Rewrite、TTS、Pipeline、GapSummary、VoiceMatch 等响应结构。

### Web Demo

- **本地调试前端**：`D:\Competition\FireRedASR2S\web_demo\app.py` (Gradio, 端口 7860)。
  - 支持上传音频、参考音频上传、目标方言调整、播放生成音频和查看结构化 JSON 调试信息。
- **公网轻量前端**：`D:\Competition\FireRedASR2S\public_web\index.html` (静态 HTML/JS)。
  - 面向演示的简洁页面，仅包含核心功能。

## 音色转换运行时

目录：`D:\Competition\OpenVoiceRuntime`

- `run_openvoice_convert.py`：OpenVoice audio-to-audio 音色转换子进程入口。
- `cache/se`：speaker embedding 缓存目录。
- `cache/nvidia_compute`、`cache/numba`：GPU/numba 缓存。

OpenVoice 主逻辑：

1. 读取 `teacher_wav`、`ref_audio`、`out_wav`。
2. 加载 `FireRedASR2S/runtime_data/models/OpenVoice/checkpoints_v2/converter`。
3. 抽取 teacher source embedding。
4. 抽取 reference target embedding。
5. 调用 `ToneColorConverter.convert(...)` 输出 voice matched wav。

## 环境变量

重要配置：

- `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`：LLM 审查、改写与总结。
- `QWEN_TTS_API_KEY` 或 `DASHSCOPE_API_KEY`：Qwen/DashScope TTS。
- `QWEN_TTS_MODEL`、`QWEN_TTS_VOICE`、`QWEN_TTS_LANGUAGE_TYPE`、`QWEN_TTS_PATH`：TTS 模型、声音、语言和接口路径。
- `VOICE_CLONE_PROVIDER`、`TEXT_CLONE_PROVIDER`：文本侧音色克隆 provider，主要是 legacy 路线。
- `VOICE_CONVERSION_PROVIDER`、`VOICE_CONVERSION_MODE`、`VOICE_CONVERSION_MODEL`、`VOICE_CONVERSION_DEVICE`：audio-to-audio 音色迁移配置，当前主路线优先关注这里。
- `RVC_PYTHON`、`RVC_MODEL_PATH`、`RVC_INDEX_PATH` 等：RVC 可选 fallback。
- `STEP2_OUTPUT_DIR`：方言/TTS 阶段输出目录。

ASR 也支持：

- `ASR_MODEL_DIR`、`PUNC_MODEL_DIR`、`VAD_MODEL_DIR`、`LID_MODEL_DIR`
- `ASR_USE_GPU`、`ASR_USE_HALF`
- `ASR_BEAM_SIZE`、`ASR_BATCH_SIZE`
- `ASR_ENABLE_PUNC`、`ASR_ENABLE_VAD`、`ASR_ENABLE_LID`
- `AUDIO_FRONTEND_MODE`

注意：不要把真实 API Key 写入源码或文档。

## 后续开发原则

1. **路线清晰**：明确当前是在开发“公网 API 编排路线”还是“本地全流程路线”。公网路线尽量不增加对云端 GPU 的依赖。
2. **Gold Teacher 兜底**：任何改动都要保持 Gold Teacher 作为长期兜底，Voice Matched 成功时才作为推荐主输出。
3. **文本层定位**：中间文本层服务于语义准确和调试，不要把 `dialect_text` 当成最终可交付声音。
4. **功能演进**：后续增加多语言支持或 RAG 时，应复用现有 VAD/LID/ASR/Punc 输出，再接 RAG/词典/语义向量映射，不建议推翻现有 Demo1 编排。
5. **本地能力兼容**：即使公网切换至轻量化架构，也需保证原本的本地闭环逻辑能够通过独立的调试接口与 Gradio 正常运作。
