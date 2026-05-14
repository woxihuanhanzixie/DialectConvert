# Gold Teacher + 音色转换 技术规划

## Summary
- 目标是把“不使用音色克隆的系统粤语 TTS”升级为唯一发音金标准，先生成一条 `gold_teacher.wav`，再通过独立的音色转换模块把这条标准粤语语音映射成接近用户原声的音色。
- 首版采用“先抽象接口、本地优先、方案二优先”的路线：主链路按 `文本 -> 系统粤语 TTS -> gold_teacher.wav -> 音色转换 -> final_voice_matched.wav` 设计，不再让文本克隆模型决定粤语发音和韵律。
- 双参考音频策略作为第二阶段增强项保留：`Timbre Ref` 用于“像谁说”，`Prosody Ref` 用于“怎么读”，但首版不把它做成主链路，避免再次把发音控制权交回克隆模型。

## Current State Analysis

### 当前已确认的实现现状
- `fireredasr2s/dialect_pipeline/tts.py`
  - 已有 `synthesize_standard_tts()`，可直接生成系统粤语 TTS 音频。
  - 已有 `synthesize_voice_clone()`，但当前仍是“文本 -> 克隆语音”路线。
  - 仍保留 `synthesize_instruction_teacher()`，说明历史上存在 `Plan B teacher/instruct` 思路，但这条路线已经不适合作为主方案。
- `fireredasr2s/dialect_pipeline/voice_clone.py`
  - 当前只有 `create_qwen_voice()` 和 `synthesize_qwen_vc()`，本质仍是文本驱动克隆。
  - `synthesize_local_clone()` 只是占位，`gpt_sovits` / `fish_speech` 并未落地。
  - 现状中没有真正的 `audio -> audio` 音色转换入口。
- `dialect_service/pipeline_engine.py`
  - 当前已支持 `baseline` 与 `clone` 双路对比。
  - `baseline` 负责系统 TTS 稳定性参考，`clone` 负责文本克隆对照。
  - 现有路由摘要、推荐策略和页面对比机制可复用到新方案。
- `fireredasr2s/dialect_pipeline/config.py`
  - 已有 `voice_clone_provider`、`local_clone_provider` 等配置入口。
  - 当前 provider 枚举仍围绕文本克隆，不足以表达“gold teacher + voice conversion”。
- `web_demo/app.py` 与 `web_demo/view_models.py`
  - 已能展示基线与克隆对比。
  - 适合作为三路展示的基础：`gold teacher`、`旧文本克隆`、`final voice matched`。

### 当前问题根因
- 现有 `qwen_vc` 方案是“文本到克隆语音”，因此它会重新决定专名读法、连接词、连读和停顿。
- 这导致“音色迁移”和“发音控制”绑在同一次生成里，系统粤语 TTS 原本已经具备的自然度被克隆模型覆盖。
- 结论：要达到“像系统 TTS 一样顺，但像用户本人在说”的目标，必须把“怎么说”和“像谁说”拆成两个阶段。

## Assumptions & Decisions

### 已锁定的产品决定
- 发音与流畅度金标准：只认不带克隆的系统粤语 TTS。
- 首版主路线：方案二，`gold_teacher.wav + 参考音频 -> 音色转换`。
- 首版模型策略：先做 provider 抽象，不在计划阶段把具体模型写死。
- 首版部署策略：本地优先，优先选择可在本机单独部署或切换的 provider。

### 本次计划内范围
- 重新定义主链路与接口层，让系统支持“teacher 音频 + voice conversion”。
- 保留旧文本克隆链路，但只作为对照与回退，不再作为推荐主输出。
- 在页面和结果结构中加入 `gold teacher` 与 `final voice matched` 的展示与推荐逻辑。

### 本次计划外范围
- 不在首版主链路中实现双参考音频联合控制。
- 不在首版中做用户批量语料采集与个性化权重训练，只预留接口和数据结构。
- 不承诺首版就把 `GPT-SoVITS`、`Fish Speech`、`RVC`、`OpenVoice` 全部接完，只先统一抽象与预留 provider 接口。

## Proposed Changes

### 1. 重构音频生成主链路

#### 文件
- `dialect_service/pipeline_engine.py`

#### What
- 把现有双路结构升级为三路结构：
  - `gold_teacher`
  - `voice_clone_legacy`
  - `voice_matched`
- 主推荐结果从“baseline vs clone”改为：
  - `gold_teacher` 作为发音金标准
  - `voice_matched` 作为新主目标
  - `voice_clone_legacy` 仅做历史对照

#### Why
- 避免继续把旧文本克隆结果误当成主方案。
- 让推荐逻辑真正围绕“自然度是否接近系统 TTS、音色是否接近用户”展开。

#### How
- 生成改写文本后，先固定调用系统 TTS 产出 `gold_teacher.wav`。
- 若启用音色转换，则调用新的 voice conversion 抽象接口，把 `gold_teacher.wav` 与用户参考音频转换为 `final_voice_matched.wav`。
- 若音色转换失败，则页面默认推荐 `gold_teacher`，并将 `voice_matched` 标记为失败或回退。
- 旧 `clone` 分支保留，但路由角色改名为 `legacy_text_clone`。

### 2. 在 TTS 层引入 teacher-first 输出

#### 文件
- `fireredasr2s/dialect_pipeline/tts.py`

#### What
- 明确把 `synthesize_standard_tts()` 作为 teacher 生成入口。
- 删除主流程对 `synthesize_instruction_teacher()` 的依赖，仅保留兼容或调试用途。
- 新增 teacher 专用封装，例如：
  - `synthesize_gold_teacher()`

#### Why
- 让代码语义与产品目标一致，避免继续把“teacher/instruct”误认为主路线。

#### How
- `synthesize_gold_teacher()` 直接复用现有 `synthesize_standard_tts()`。
- 返回结构中增加：
  - `teacher_role`
  - `teacher_input_text`
  - `teacher_wav_path`
  - `teacher_audio_meta`

### 3. 抽象音色转换接口

#### 文件
- `fireredasr2s/dialect_pipeline/voice_clone.py`
- `fireredasr2s/dialect_pipeline/config.py`

#### What
- 从“文本克隆”扩展为双接口：
  - 文本克隆接口：保留旧路径
  - 音色转换接口：新路径
- 配置层新增或重命名 provider 概念，区分：
  - `text_clone_provider`
  - `voice_conversion_provider`

#### Why
- 当前 `voice_clone_provider` 语义过窄，既表示文本克隆，又被误用成未来的音色转换 provider。

#### How
- 在 `voice_clone.py` 中新增统一入口，例如：
  - `convert_voice_from_teacher(teacher_wav_path, ref_audio_path, out_wav, cfg, preferred_name)`
- 首版只定义接口与错误处理规范，不把 provider 绑定死：
  - 输入：teacher 音频、参考音频、输出路径、provider 配置
  - 输出：转换音频路径、provider 名称、耗时、错误信息、可能的相似度占位字段
- `config.py` 中新增或重命名相关配置：
  - `VOICE_CONVERSION_PROVIDER`
  - `VOICE_CONVERSION_MODE`
  - `VOICE_CONVERSION_MODEL`
  - `VOICE_CONVERSION_DEVICE`
- 保留 `QWEN_TTS_VC_MODEL` 作为 legacy 文本克隆配置，不再把它当新主方案。

### 4. 调整接口返回结构

#### 文件
- `dialect_service/schemas.py`

#### What
- 在现有 `baseline` / `clone` / `gap_summary` 结构基础上新增：
  - `gold_teacher`
  - `voice_matched`
  - `legacy_text_clone`
  - `recommended_main_output`
  - `voice_match_summary`

#### Why
- 现在的 schema 只能清楚表达“系统 TTS vs 文本克隆”，还不能表达“teacher 音频”和“音色转换结果”。

#### How
- 沿用已有 `TtsRouteResponse` 思路，为三条音频都输出统一字段：
  - 输入文本
  - 输入模式
  - 音频路径
  - 模型/provider
  - 错误
  - 元信息
- 新增 `voice_match_summary`，至少包含：
  - `teacher_is_reference`
  - `voice_matched_available`
  - `voice_match_provider`
  - `voice_match_error`
  - `recommendation_reason`

### 5. 更新页面展示与试听顺序

#### 文件
- `web_demo/app.py`
- `web_demo/view_models.py`

#### What
- 页面从双路对比升级为三路对比：
  - 系统粤语金标准：`gold_teacher`
  - 新主目标：`voice_matched`
  - 历史对照：`legacy_text_clone`

#### Why
- 让用户听感判断直接围绕“系统标准是否保住”“音色是否更像用户”展开。

#### How
- 默认试听顺序：
  1. `gold_teacher`
  2. `voice_matched`
  3. `legacy_text_clone`
- 页面增加说明：
  - `gold_teacher` 负责“怎么说”
  - `voice_matched` 负责“像谁说”
  - `legacy_text_clone` 仅供对照
- 现有差距摘要改成：
  - `teacher_vs_voice_matched`
  - `teacher_vs_legacy_clone`

### 6. 保留双参考增强项的接口预留

#### 文件
- `fireredasr2s/dialect_pipeline/config.py`
- `dialect_service/schemas.py`
- `web_demo/app.py`

#### What
- 为第二阶段双参考能力预留字段：
  - `timbre_ref_audio`
  - `prosody_ref_audio`
  - `prosody_guidance_mode`

#### Why
- 用户已经明确提出“音色参考 + 韵律参考”的增强方向。
- 虽然首版不做主链路，但应避免未来再次大改接口。

#### How
- 首版只保留可空字段和展示位，不纳入默认推理路径。
- 页面上用“高级设置/后续能力预留”方式表达，不进入主交互路径。

### 7. 新 provider 选型原则

#### 规划决策
- 首版不在计划中写死某一个模型，但明确分层：
  - `RVC/OpenVoice` 更贴近“teacher 音频 -> 音色转换”的目标，可优先作为 voice conversion provider 的候选接口语义。
  - `GPT-SoVITS/Fish Speech` 作为本地可扩展 provider 预留，但不把它们在首版里默认绑定为唯一实现。

#### 结论
- 这次规划里必须声明“需要音色转换模型”，但不必在计划阶段把模型唯一化。
- 计划会把“模型是必需组件”写清楚，而不是继续假设现有 `qwen_vc` 可以充当 voice conversion。

## Implementation Steps

### 阶段 1：主链路改造
1. 在 `tts.py` 中显式抽出 `gold_teacher` 生成函数。
2. 在 `pipeline_engine.py` 中把 teacher 音频生成提前为固定步骤。
3. 保留 `legacy_text_clone` 旧分支，但改成非推荐结果。

### 阶段 2：音色转换抽象
1. 在 `voice_clone.py` 中新增 `convert_voice_from_teacher()` 抽象接口。
2. 在 `config.py` 中新增 voice conversion 相关配置。
3. 在 `schemas.py` 中新增 `gold_teacher` / `voice_matched` 结构。

### 阶段 3：页面与调试结构升级
1. 在 `web_demo/app.py` 中增加三路播放与下载。
2. 在 `web_demo/view_models.py` 中增加 teacher-first 推荐说明。
3. 调整差距摘要与推荐逻辑。

### 阶段 4：增强项预留
1. 为 `timbre_ref_audio` / `prosody_ref_audio` 预留字段。
2. 不纳入首版默认推理，只留 schema 和 UI 占位。

## Verification Steps
- 结构验证
  - 确认接口返回中存在 `gold_teacher`、`voice_matched`、`legacy_text_clone` 三个结果块。
  - 确认推荐主输出默认为 `gold_teacher` 或 `voice_matched`，不会再优先推荐 `legacy_text_clone`。
- 生成验证
  - 以 `20260423_214727.wav` 作为首个回归样本。
  - 校验 `gold_teacher.wav` 成功生成，且对应输入文本与基线语义层一致。
  - 当 voice conversion provider 可用时，校验 `final_voice_matched.wav` 成功生成。
- 页面验证
  - 页面展示三路音频与试听顺序说明。
  - 差距摘要能清楚说明“teacher 是发音标准”“voice matched 是音色目标”。
- 失败验证
  - 如果 voice conversion provider 未配置或失败，页面明确回退到 `gold_teacher`，不影响主试听链路。

## Risks
- 当前仓库没有现成的本地 voice conversion 落地代码，首版的主要工作不是“微调 prompt”，而是建立新主链路和 provider 抽象。
- 如果后续选定的本地 VC 模型对粤语 teacher 音频的保真度不足，仍可能出现音色像了但清晰度下降的问题，因此需要保留 `gold_teacher` 作为长期稳定兜底。
- 双参考方案会明显增加接口复杂度和数据管理复杂度，因此只建议作为第二阶段增强，而不是首版直接并入主链路。
