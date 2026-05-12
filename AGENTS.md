# Agent Project Notes

更新时间：2026-05-12

## 项目定位

本项目是《声临其境》Demo 一期的本地工程实现，目标不是单纯做“文本方言翻译”，而是打通一条可演示的多模态闭环：

`普通话/语音输入 -> ASR 识别 -> 文本审查纠错 -> 语义稳定的中文中间层 -> 方言/风格控制 -> Qwen Gold Teacher 音频 -> audio-to-audio 音色迁移 -> Web 演示`

当前 Demo 的核心产品表达是：用户说一段普通话或上传一段音频，系统先保证中文语义准确，再由 Qwen/DashScope TTS 生成一条发音和流畅度稳定的 Gold Teacher 音频，最后用 OpenVoice/RVC 等音色转换模型把这条标准音频映射成接近参考说话人的音色。

重要原则：中间层的 `dialect_text`、`semantic_text`、`pronunciation_text`、`prosody_text` 主要用于语义控制、调试展示、发音提示和后续扩展，不应被理解成最终业务成果。最终用户听到的主结果来自 `gold_teacher` 或 `voice_matched` 音频。

当前 Demo 重点覆盖需求 1、2、6 中的可演示部分：

- 多模态交互核心闭环：普通话录入、ASR/LID/Punc、方言风格生成、个性化音色迁移、后续数字人联动预留。
- 互动学习与社交传播：面向 Z 世代的方言表达、配音和表情包玩法预留。
- 方言与濒危词汇识别转写：通过声学前端、VAD/LID/ASR/Punc 和后续 RAG/语义映射缓解“有音无字”。
- 乡音陪伴与音色模拟：用系统稳定的方言/口语播报作为“怎么说”的标准，再用参考音频承载“像谁说”。

长期技术路线包含 ASR、TTS、RAG、LLM Agent、知识图谱、众包方言树、全球乡音地图、适老化乡音陪伴、数字人驱动、音色转换模型评测等模块。当前代码主要落在 Demo1 的本地后端与 Gradio 演示。

## 当前真实业务逻辑

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

入口：`D:\Competition\FireRedASR2S\web_demo\app.py`

- 使用 Gradio 构建本地演示页面。
- 支持上传音频、浏览器录音、参考音频上传、目标方言/音色策略调整、播放生成音频和查看结构化 JSON。
- 默认演示地址：`http://127.0.0.1:7860`。
- 展示重点应围绕：
  - `Gold Teacher 音频`：负责怎么说。
  - `Voice Matched 音频`：负责像谁说。
  - 文本对比与规则命中：用于调试，不是最终成果。

相关文件：

- `web_demo/client.py`：本地服务/engine 调用客户端。
- `web_demo/view_models.py`：页面展示模型和输出整理。
- `web_demo/run_audio16k_eval.py`：16k 音频评估辅助脚本。

## 核心 Python 包

包目录：`D:\Competition\FireRedASR2S\fireredasr2s`

- `fireredasr2system.py`：FireRed ASR2 系统级编排。
- `fireredasr2s_cli.py`：命令行入口。
- `fireredasr2`：ASR 模型、特征、tokenizer、AED/LLM 模型结构和 WER 工具。
- `fireredlid`：语言识别 LID。
- `fireredpunc`：标点恢复。
- `fireredvad`：VAD、Stream VAD、后处理和音频特征。
- `dialect_pipeline`：Demo1 文本控制与语音生成管线。

`dialect_pipeline` 关键文件：

- `config.py`：`Step2Config`，从 `.env` 或系统环境变量读取 LLM、TTS、音色克隆、输出目录、方言风格等配置。
- `rewrite.py`：普通话到方言/口语风格的中间文本改写。
- `tn.py`：文本规范化。
- `pronunciation.py`、`pronunciation_lexicon.py`：发音提示层、规则词典和 fallback 设置。
- `prosody.py`：韵律提示层规则与 LLM fallback。
- `tts.py`：Qwen/DashScope TTS 调用，包含 `synthesize_gold_teacher()`。
- `voice_clone.py`：Qwen VC legacy、OpenVoice、RVC 等音色克隆/转换相关封装，核心是 `convert_voice_from_teacher()`。
- `dialect_postprocess.py`：方言文本后处理。
- `run_batch_demo.py`：批量 Demo 测试辅助。

## 音色转换运行时

目录：`D:\Competition\OpenVoiceRuntime`

- `run_openvoice_convert.py`：OpenVoice audio-to-audio 音色转换子进程入口。
- `cache/se`：speaker embedding 缓存目录。
- `cache/nvidia_compute`、`cache/numba`：GPU/numba 缓存。
- `import_stack.log`、`tmp_probe_*`：历史调试产物。

OpenVoice 主逻辑：

1. 读取 `teacher_wav`、`ref_audio`、`out_wav`。
2. 加载 `FireRedASR2S/runtime_data/models/OpenVoice/checkpoints_v2/converter`。
3. 抽取 teacher source embedding。
4. 抽取 reference target embedding。
5. 调用 `ToneColorConverter.convert(...)` 输出 voice matched wav。

## 运行数据与模型

主要运行目录：`D:\Competition\FireRedASR2S\runtime_data`

- `models/FireRedASR2-AED`：ASR 模型。
- `models/FireRedPunc`：标点模型。
- `models/FireRedVAD/VAD`：VAD 模型。
- `models/FireRedLID`：LID 模型。
- `models/OpenVoice`：OpenVoice 模型和 vendored 依赖。
- `audio`、`audio_16k`、`test_audio`、`test_audio_wav`：输入、测试和转换音频。
- `asr_output`：ASR 输出。
- `step2_input`、`step2_output`：方言改写/TTS 阶段输入输出。
- `web_demo_uploads`、`web_demo_refs`、`web_demo_preview`：Web Demo 上传、参考音频和预览文件。
- `_debug_clone`：音色克隆调试产物。

这些目录包含大量模型权重、缓存、音频和生成结果，后续开发时应避免无关改动和误删。

## 环境变量

重要配置：

- `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`：LLM 审查、改写与总结。
- `QWEN_TTS_API_KEY` 或 `DASHSCOPE_API_KEY`：Qwen/DashScope TTS。
- `QWEN_TTS_MODEL`、`QWEN_TTS_VOICE`、`QWEN_TTS_LANGUAGE_TYPE`、`QWEN_TTS_PATH`：TTS 模型、声音、语言和接口路径。
- `QWEN_TTS_INSTRUCTION_MODEL`、`QWEN_TTS_TEACHER_VOICE`、`QWEN_TTS_TEACHER_INSTRUCTIONS`：历史 instruction teacher 配置，当前主路线不应默认依赖它。
- `VOICE_CLONE_PROVIDER`、`TEXT_CLONE_PROVIDER`：文本侧音色克隆 provider，主要是 legacy 路线。
- `VOICE_CONVERSION_PROVIDER`、`VOICE_CONVERSION_MODE`、`VOICE_CONVERSION_MODEL`、`VOICE_CONVERSION_DEVICE`：audio-to-audio 音色迁移配置，当前主路线优先关注这里。
- `RVC_PYTHON`、`RVC_MODEL_PATH`、`RVC_INDEX_PATH` 等：RVC 可选 fallback。
- `OPENVOICE_PYTHON`：只有确实需要独立 OpenVoice 解释器时设置。
- `STEP2_OUTPUT_DIR`：方言/TTS 阶段输出目录。

ASR 也支持：

- `ASR_MODEL_DIR`、`PUNC_MODEL_DIR`、`VAD_MODEL_DIR`、`LID_MODEL_DIR`
- `ASR_USE_GPU`、`ASR_USE_HALF`
- `ASR_BEAM_SIZE`、`ASR_BATCH_SIZE`
- `ASR_ENABLE_PUNC`、`ASR_ENABLE_VAD`、`ASR_ENABLE_LID`
- `AUDIO_FRONTEND_MODE`

注意：不要把真实 API Key 写入源码或文档。

## 启动方式

推荐使用项目已有脚本：

```powershell
D:\Competition\FireRedASR2S\start_demo1_web.ps1
```

该脚本会：

- 检查项目或工作区 `.env`。
- 尝试将本机 ffmpeg 加入 PATH。
- 优先使用 `D:\Anaconda\envs\fireredasr2s\python.exe`。
- 设置 `PYTHONPATH` 为项目根目录。
- 执行 `python -m web_demo.app`。

也可以拆分启动：

```powershell
conda run -n fireredasr2s uvicorn asr_service.app:app --host 127.0.0.1 --port 8001
conda run -n fireredasr2s uvicorn dialect_service.app:app --host 127.0.0.1 --port 8002
conda run -n fireredasr2s python -m web_demo.app
```

## 当前已知状态

- 当前主链路已经是 teacher-first：Gold Teacher 先生成标准音频，Voice Matched 再做音色迁移。
- `任务未完成记录.md` 记录：OpenVoice 与 RVC 两条模型链路都要完整跑通，目前 RVC 独立环境安装与依赖冲突尚未闭环。
- Demo1 默认目标方言仍以 `yue` / `guangdong_general` 为主，但后续可扩展四川话、闽南语等目标。
- 默认参考音频策略是 `vad_concat`。
- 音色优先级默认 `high`，流畅度默认 `allow_rate_adjust`。
- Voice Matched 默认可走 `openvoice`，RVC 是可选 fallback。
- Web Demo 已展示输入音频质量、目标方言与风格、语义/发音转写、规则命中、参考音频处理、音色策略、回退原因和结构化结果。

## 后续开发原则

1. 先确认 `.env` 是否配置了可用的 DeepSeek 与 Qwen/DashScope Key。
2. 启动 Web Demo，先验证纯文本链路，再验证音频上传链路。
3. 对音色链路按顺序验证：Gold Teacher、OpenVoice Voice Matched、RVC fallback。
4. 新增方言时，不要只加词表替换；必须考虑 Qwen Gold Teacher 的 voice/style/instruction 能否稳定生成对应方言听感。
5. 中间文本层服务于语义准确和调试，不要把 `dialect_text` 当成最终可交付声音。
6. RVC 问题优先聚焦独立 Python 环境、模型路径、index 路径和依赖冲突，不要改动已可用的 ASR/LLM/TTS 主链路。
7. 下一阶段如做功能 6，应复用现有 VAD/LID/ASR/Punc 输出，再接 RAG/词典/语义向量映射，不建议推翻现有 Demo1 编排。
8. 任何改动都要保持 Gold Teacher 作为长期兜底，Voice Matched 成功时才作为推荐主输出。
