# Demo1 双层文本、发音转写与方言同音优化计划

## Summary

本轮规划要解决的核心问题不是“语义改写不够像粤语”本身，而是：

- 当前系统只有一份改写文本，同时承担“给人看”和“喂给 TTS/VC 发音”两个角色。
- 对固定系统音色来说，同一串汉字有时还能被模型按粤语语境读出来；但在音色克隆路径里，同样的字串更容易被读回普通话或半普通话。
- 因此当前的瓶颈是：**语义文本不等于发音文本**。如果只靠一轮“普通话 -> 粤语书写文本”，仍然无法稳定解决“同样”这类字面没变、但目标读音应当变化的问题。

本轮已锁定的产品决策：

- 文本策略：`双层文本`
  - 一份 `语义转写文本` 用于展示和理解
  - 一份 `发音转写文本` 专门用于 TTS/VC
- 发音修正策略：`规则词典优先`
  - 先用高频词/高频短语规则修正
  - 再按需调用 LLM 做发音补全
  - 后续接入语义向量库/RAG 做检索增强
- 当前测试阶段页面展示：`同时展示两份文本`
  - 后续正式 demo 可再改展示形态

本计划的成功标准：

- 系统输出中明确分离 `semantic_text` 和 `pronunciation_text`
- TTS/VC 默认使用 `pronunciation_text`，不再直接使用展示文本
- 高频歧义词如“同样”这类词，能被优先修正到更符合目标方言发音的输入形式
- 页面和结果结构在测试阶段能同时展示两份文本，便于人工校对
- 实现上为未来 `LLM fallback + RAG 发音检索增强` 留好接口

## Current State Analysis

### 1. 当前只有一层文本

当前改写链路在以下文件中：

- `FireRedASR2S/fireredasr2s/dialect_pipeline/rewrite.py`
- `FireRedASR2S/dialect_service/adapters.py`
- `FireRedASR2S/dialect_service/pipeline_engine.py`

当前状态：

- `rewrite_to_dialect()` 只输出一份 `dialect_text`
- `adapters.py` 中 `rewrite_text()` 也只维护：
  - `tn_text`
  - `dialect_text`
- `pipeline_engine.py` 在进入 TTS 时，直接用：
  - `rewrite["dialect_text"] if rewrite else review_text`

这意味着：

- 当前“展示文本”和“TTS 输入文本”是同一份
- 一旦某些词在字面上没有发生足够的方言化替换，TTS/VC 就可能按普通话或半普通话去读

### 2. 当前没有专门的“发音修正层”

当前与发音最接近的逻辑只有：

- `rewrite.py` 的 LLM prompt
- `dialect_postprocess.py` 的轻量替换规则
- `tts.py` 里把文本直接送入标准 TTS 或 VC

当前缺失：

- 独立的 `pronunciation_text`
- 高频词/短语发音映射词典
- “规则命中 -> LLM fallback” 的发音修正链路
- 发音修正命中记录和可解释结果

### 3. 当前 TTS 路径对发音文本没有区分

当前 TTS 实现位于：

- `FireRedASR2S/fireredasr2s/dialect_pipeline/tts.py`
- `FireRedASR2S/fireredasr2s/dialect_pipeline/voice_clone.py`

当前状态：

- 标准 TTS 和 VC 都直接接收 `text`
- 当前仅支持：
  - `language_type`
  - `instructions`
- 但没有单独的“发音输入文本”入口

因此：

- 即使页面上显示的语义文本“看起来合理”
- 也不能保证 VC 输出会稳定读成目标方言常规发音

### 4. 当前测试页面也只有一份文本语义

当前页面位于：

- `FireRedASR2S/web_demo/app.py`
- `FireRedASR2S/web_demo/view_models.py`

当前状态：

- 页面会展示：
  - `审查后文本`
  - `Rewrite 前文本`
  - `粤语文本`
- 但没有：
  - `语义转写文本`
  - `发音转写文本`
  - 发音词典命中记录
  - 发音 fallback 说明

## Proposed Changes

### 1. 引入“双层文本”结构

改造文件：

- `FireRedASR2S/dialect_service/schemas.py`
- `FireRedASR2S/dialect_service/adapters.py`
- `FireRedASR2S/dialect_service/pipeline_engine.py`

改造内容：

- 将当前单一 `dialect_text` 扩展为双层结果：
  - `semantic_text`
  - `pronunciation_text`
- 保留 `dialect_text` 作为兼容字段，但其定义要明确：
  - 建议兼容期内仍指向 `semantic_text`
- 新增辅助字段：
  - `pronunciation_mode`
  - `pronunciation_rule_hits`
  - `pronunciation_fallback_used`
  - `pronunciation_notes`

为什么这样改：

- 用户当前指出的问题，本质上就是“给人看”和“给模型发音”不能继续共用一份文本
- 如果不先把结构拆开，后续无论词典、LLM 还是 RAG 都没有稳定落点

如何落地：

- `rewrite_text()` 先输出 `semantic_text`
- 再单独生成 `pronunciation_text`
- TTS 层改成默认使用 `pronunciation_text`

### 2. 新增“发音修正层”，采用规则词典优先

改造文件：

- 新增：
  - `FireRedASR2S/fireredasr2s/dialect_pipeline/pronunciation.py`
- 可能补充：
  - `FireRedASR2S/fireredasr2s/dialect_pipeline/pronunciation_lexicon.json`
  - 或 `pronunciation_lexicon.py`
- 调用入口：
  - `FireRedASR2S/dialect_service/adapters.py`

改造内容：

- 新增发音修正主流程，例如规划中的目标形态：
  - `build_pronunciation_text(semantic_text, cfg, target_dialect, dialect_style)`
- 处理顺序固定为：
  1. 高频词典规则替换
  2. 若命中不足或存在高风险词，再触发 LLM fallback
  3. 返回最终 `pronunciation_text`

首版词典规则内容：

- 重点覆盖“字面不变但目标方言读音不该按普通话读”的高频词和短语
- 先收敛到少量高价值词，不做大而全词库
- 词典项建议至少记录：
  - `source`
  - `semantic_form`
  - `pronunciation_form`
  - `target_dialect`
  - `dialect_style`
  - `priority`
  - `notes`

为什么这样改：

- 用户已经明确希望“先高频词后调用 LLM”
- 这类问题最适合先用规则锁住高频确定性错误，再把 LLM 留给长尾和歧义场景

### 3. 发音修正不直接等于“更重的语义改写”

改造文件：

- `FireRedASR2S/fireredasr2s/dialect_pipeline/rewrite.py`
- `FireRedASR2S/fireredasr2s/dialect_pipeline/dialect_postprocess.py`
- 新增：
  - `FireRedASR2S/fireredasr2s/dialect_pipeline/pronunciation.py`

改造内容：

- 保持职责分层：
  - `rewrite.py` 负责语义自然度和口语表达
  - `pronunciation.py` 负责发音输入优化
- 不把所有发音替换都继续堆进 `rewrite.py` 或 `dialect_postprocess.py`

为什么这样改：

- “语义正确”与“发音正确”是两个不同目标
- 如果继续混在一起，后续既不方便扩词典，也不方便接 RAG

### 4. 为 LLM fallback 和后续 RAG 预留接口

改造文件：

- `FireRedASR2S/fireredasr2s/dialect_pipeline/config.py`
- 新增：
  - `FireRedASR2S/fireredasr2s/dialect_pipeline/pronunciation.py`
- 调用入口：
  - `FireRedASR2S/dialect_service/adapters.py`

改造内容：

- 新增配置项：
  - `PRONUNCIATION_MODE=rule_first`
  - `PRONUNCIATION_LLM_FALLBACK=1`
  - `PRONUNCIATION_RAG_ENABLED=0`
  - `PRONUNCIATION_TARGET_DIALECT=yue`
- 在 `pronunciation.py` 中预留两个扩展点：
  - `llm_pronunciation_fallback(...)`
  - `rag_pronunciation_lookup(...)`

首版执行决策：

- 默认开启 `rule_first`
- 默认允许 `LLM fallback`
- 默认关闭 `RAG`
- 结果结构中记录是否使用了 fallback

为什么这样改：

- 用户已经明确给出了路线：
  - 现在先高频词
  - 后续接向量库/RAG
- 因此本轮规划必须把这条路线体现在代码结构上

### 5. TTS 层改为优先吃“发音文本”

改造文件：

- `FireRedASR2S/dialect_service/adapters.py`
- `FireRedASR2S/dialect_service/pipeline_engine.py`
- `FireRedASR2S/fireredasr2s/dialect_pipeline/tts.py`
- `FireRedASR2S/fireredasr2s/dialect_pipeline/voice_clone.py`

改造内容：

- `tts_text()` 不再默认只接 `semantic_text`
- 需要明确新增/透传：
  - `tts_input_text`
  - `tts_input_mode`
- 规则：
  - 若存在 `pronunciation_text`，TTS/VC 默认用它
  - 若发音修正失败，再回退到 `semantic_text`

为什么这样改：

- 这是本轮需求的核心落点
- 否则即使前面做了双层文本，最终音频仍然会继续用旧文本发音

### 6. 测试页面同时展示两份文本

改造文件：

- `FireRedASR2S/web_demo/app.py`
- `FireRedASR2S/web_demo/view_models.py`

改造内容：

- 当前测试阶段页面新增展示项：
  - `语义转写文本`
  - `发音转写文本`
  - `发音规则命中`
  - `是否触发 LLM fallback`
- 页面中的 `粤语文本` 槽位需要拆分或重命名，避免混淆

为什么这样改：

- 用户已经明确表示“现在测试时同时展示两份”
- 这能直接帮助定位：
  - 问题到底出在语义改写
  - 还是出在发音文本构建

### 7. 文档同步更新

改造文件：

- `技术文档.md`
- `FireRedASR2S/docs/demo1_voice_clone_plan.md`
- `FireRedASR2S/docs/demo1_web_demo.md`
- 可新增：
  - `FireRedASR2S/docs/demo1_pronunciation_layer.md`

改造内容：

- 记录新的链路定义：
  - `ASR -> 审查 -> 语义改写 -> 发音修正 -> TTS/VC`
- 说明双层文本机制：
  - `semantic_text`
  - `pronunciation_text`
- 记录高频词规则优先、LLM fallback、后续 RAG 扩展路线

## Assumptions & Decisions

### 已锁定决策

- 本轮核心问题定义为“方言发音输入层缺失”，而不是继续单纯加重语义改写
- 系统采用 `双层文本`
- 发音修正采用 `规则词典优先`
- 测试阶段页面 `同时展示两份文本`
- LLM 放在词典规则之后
- RAG 不是本轮实现重点，但必须为后续预留接口

### 关键假设

- 现有标准 TTS 与 VC 对同一文本的发音表现确实存在差异，因此不能把固定音色结果直接当作克隆路径的等价代理
- 高频问题词的收益足够高，先做小词典能显著改善体验
- 当前方言仍以 `yue` 为首个落地目标，双层文本结构先围绕粤语打通，再扩到其他方言

### 本轮不做

- 不做完整 RAG 发音知识库建设
- 不做完整粤拼/音标级显式输入体系
- 不把“标准 TTS 对照校正”作为首版主路径
- 不要求一次性覆盖所有歧义词，只要求先打通结构与高频词链路

## Verification Steps

### 1. 结构验收

结果结构中必须新增并正确返回：

- `semantic_text`
- `pronunciation_text`
- `pronunciation_mode`
- `pronunciation_rule_hits`
- `pronunciation_fallback_used`

### 2. TTS 输入验收

从代码路径上确认：

- 标准 TTS 使用 `pronunciation_text`
- VC 也使用 `pronunciation_text`
- 若发音修正失败，有清晰回退到 `semantic_text` 的逻辑

### 3. 高频词验收

至少选择一批高频词作为首版样例验证，例如：

- `同样`
- `如果`
- `这样`
- `那个`
- `这个`

验收标准：

- 页面展示的 `semantic_text` 与 `pronunciation_text` 可不同
- 实际播报更接近目标方言常规读法

### 4. 页面验收

测试页面必须能同时看到：

- 语义转写文本
- 发音转写文本
- 发音规则命中信息
- 发音 fallback 说明

### 5. 扩展性验收

从代码结构确认：

- 高频词词典和发音构建逻辑独立于 `rewrite.py`
- LLM fallback 是单独函数，不与规则层混写
- RAG 接口位已经预留，不需要再推翻结构重做
