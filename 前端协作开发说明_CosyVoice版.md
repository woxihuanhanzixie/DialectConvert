# 声临其境前端协作开发说明（CosyVoice 公网链路对齐版）

更新时间：2026-05-13

本文档用于分发给两位同学做前端页面优化。请注意：本轮任务只做网页展示、交互、移动端适配、RAG 看板和方言百科悬浮窗，不修改后端业务逻辑。

## 1. 当前项目口径

项目名称：

**声临其境：AI 赋能的中国濒危方言数字化保护与传承平台**

当前后端主链路将由项目负责人统一改造为：

```text
普通话/语音输入
-> ASR 识别或文本输入
-> 方言语义理解
-> CosyVoice 声音复刻
-> CosyVoice v3-flash 实时方言语音输出
-> 网页展示
```

你们本轮不要改后端链路，不要决定 CosyVoice 怎么调用，不要修改 ASR、LLM、TTS、声音复刻相关 Python 逻辑。你们只负责让网页更适合比赛展示，并保留现有接口字段，方便负责人后续对齐 CosyVoice 后端。

## 2. 代码修改范围

优先修改公网展示页：

```text
FireRedASR2S/public_web/index.html
FireRedASR2S/public_web/styles.css
FireRedASR2S/public_web/app.js
```

本地 Gradio Demo 可以同步修改展示文案，但不是优先项：

```text
FireRedASR2S/web_demo/app.py
FireRedASR2S/web_demo/view_models.py
```

不要修改这些核心后端文件：

```text
FireRedASR2S/dialect_service/
FireRedASR2S/asr_service/
FireRedASR2S/fireredasr2s/dialect_pipeline/
OpenVoiceRuntime/
```

除非负责人明确要求，否则不要改接口、不要改模型调用、不要改环境变量读取逻辑。

## 3. 必须保留的接口字段

前端提交到 `/api/v1/dialect/pipeline` 的字段名必须保留：

```text
file
speaker_ref_audio
text
target_dialect
dialect_style
voice
voice_clone_enabled
voice_clone_provider
```

特别注意：

- `voice_clone_provider` 字段名不要删除。
- 当前可以继续提交旧字段名，负责人后端会把它解释为 `cosyvoice` 或做兼容。
- 可以把页面上显示的 “Qwen Voice Copy” 改成 “CosyVoice 声音复刻”，但不要强行重命名 JSON 字段。
- 不要把 RAG、百科卡片、文化解释内容传进 TTS 或 CosyVoice 输入，它们只用于页面展示。

## 4. 页面文案统一口径

页面主标题：

```text
声临其境
```

页面副标题：

```text
AI 赋能的中国濒危方言数字化保护与传承平台
```

链路说明：

```text
普通话/语音输入 -> 方言语义理解 -> CosyVoice 声音复刻 -> CosyVoice v3-flash 实时方言语音输出
```

旧文案替换建议：

| 旧展示文案 | 新展示文案 |
| --- | --- |
| Qwen Voice Copy | CosyVoice 声音复刻 |
| 最终方言克隆音频 | CosyVoice 复刻方言语音 |
| Gold Teacher | 基础参考音频/兜底音频 |
| Gold Teacher 参考音频 | 基础参考音频/兜底音频 |
| 声音复刻方言语音工作台 | 声临其境方言语音体验台 |

注意：`Gold Teacher` 不要再作为公网主卖点。如果页面里还需要保留它，只把它作为兜底或调试信息展示。

## 5. 分工一：页面 UI 与移动端语音输入

负责人：同学 1

主要文件：

```text
FireRedASR2S/public_web/index.html
FireRedASR2S/public_web/styles.css
FireRedASR2S/public_web/app.js
```

### 5.1 目标

把页面从“技术调试页”优化成“AI+大赛项目展示页”，突出：

- 濒危方言保护
- 侨乡文化与乡音传承
- 青年互动与方言传播
- CosyVoice 声音复刻和实时合成

### 5.2 必须保留的输入能力

页面必须保留三种输入：

1. 主音频上传/录音
2. 音色参考音频上传
3. 文本输入

手机端输入要保留：

```html
<input id="input-audio" type="file" accept="audio/*" capture>
```

可以调整样式，但不要删除 `accept="audio/*"` 和 `capture`。这样手机浏览器可以调起录音或音频上传能力。

### 5.3 页面结构建议

首屏建议包含：

- 顶部项目名：`声临其境`
- 一句项目说明：`让普通话输入生成带有参考音色的方言语音，帮助濒危方言以更年轻、更可互动的方式被看见和听见。`
- 输入区：
  - 主音频
  - 参考音频
  - 文本输入
  - 目标方言选择
  - 生成按钮
- 输出区：
  - `CosyVoice 复刻方言语音`
  - 推荐主输出
  - 总耗时
  - Trace ID
  - 错误/回退信息
- 下方展示区：
  - ASR 原始文本
  - 审查后文本
  - 方言/语义文本
  - 发音提示层
  - 韵律提示层
  - RAG 看板
  - 方言百科悬浮卡片

### 5.4 移动端验收

手机宽度下必须做到：

- 输入区、按钮、音频播放器不重叠。
- 文字不溢出卡片。
- 按钮高度足够点击。
- 音频播放器能正常显示。
- RAG 指标卡片自动换行。
- 方言百科悬浮窗不会超出屏幕太多。

### 5.5 不允许做的事

- 不改 `/api/v1/dialect/pipeline`。
- 不改表单字段名。
- 不删除 `speaker_ref_audio`。
- 不删除 `text` 输入。
- 不把网页做成纯宣传落地页，必须保留可操作的 Demo。
- 不提交 `.env`、API Key、模型、缓存、生成音频。

## 6. 分工二：RAG 看板与方言百科悬浮窗

负责人：同学 2

主要文件：

```text
FireRedASR2S/public_web/app.js
FireRedASR2S/public_web/styles.css
FireRedASR2S/public_web/index.html
FireRedASR2S/web_demo/view_models.py
```

### 6.1 RAG 看板目标

在页面中展示这些指标：

- 最终命中次数
- 发音规则命中
- 韵律规则命中
- RAG 命中率
- RAG 耗时
- 语义相似度

可用字段来源：

```text
rewrite.pronunciation_rule_hits
rewrite.prosody_rule_hits
rewrite.rag_hits
rewrite.pronunciation_rag_hits
rewrite.rag_hit_rate
rewrite.pronunciation_rag_hit_rate
rewrite.rag_recall_rate
rewrite.rag_query_count
rewrite.pronunciation_rag_query_count
rewrite.rag_total
rewrite.rag_latency_ms
rewrite.pronunciation_rag_latency_ms
rewrite.rag_elapsed_ms
rewrite.rag_semantic_similarity
rewrite.rag_avg_similarity
rewrite.rag_top_score
```

如果没有数据，页面显示：

```text
暂无命中
```

或者：

```text
未启用
```

不要让页面报错。

### 6.2 方言百科悬浮窗目标

参考百度百科词条卡片或 NotebookLM 引用弹窗，实现方言词的悬浮解释。

卡片内容包含：

- 方言词
- 命中词
- 普通话释义
- 文化说明
- 使用例句
- 语体
- 来源链接

可用字段来源：

```text
rewrite.cultural_cards
rewrite.cultural_card_terms
```

单张卡片可能包含字段：

```text
id
target_dialect
term
aliases
matched_terms
meaning
cultural_note
usage_example
register
source_label
source_url
```

### 6.3 交互建议

桌面端：

- 方言词显示为 chip 或高亮词。
- 鼠标 hover 时出现百科悬浮窗。
- 点击 chip 时也能保持可读。

手机端：

- hover 不可靠，要支持点击展开。
- 弹窗或卡片不要遮挡整个页面。
- 可改成点击后展开的卡片列表。

### 6.4 不允许做的事

- 不把百科卡片内容传给 CosyVoice。
- 不改后端字段结构。
- 不新增必须依赖联网的百科请求。
- 不把来源写成未经确认的真实机构，已有 `source_label/source_url` 就展示已有来源。
- 不因为字段为空导致页面报错。

## 7. 后端对齐约定

负责人后端会补充 CosyVoice 配置，例如：

```text
VOICE_MATCH_PROVIDER=cosyvoice
VOICE_CLONE_PROVIDER=cosyvoice
COSYVOICE_BASE_URL=https://dashscope.aliyuncs.com/api/v1
COSYVOICE_WS_URL=wss://dashscope.aliyuncs.com/api-ws/v1/inference/
COSYVOICE_ENROLLMENT_MODEL=voice-enrollment
COSYVOICE_SYNTHESIS_MODEL=cosyvoice-v3-flash
```

前端不要直接依赖这些环境变量。前端只需要展示后端返回的结果。

前端需要兼容这些旧 route 字段：

```text
tts.cloned_dialect
tts.voice_matched
tts.qwen_cloned_dialect
tts.gold_teacher
tts.recommended_main_output
```

展示名可以改成 CosyVoice，但 JSON 字段兼容先不要删。这样负责人改后端时不会因为前端字段被删而无法联调。

建议 `app.js` 的展示名：

```text
cloned_dialect -> CosyVoice 复刻方言语音
voice_matched -> CosyVoice 声音复刻结果
qwen_cloned_dialect -> CosyVoice 复刻方言语音（兼容旧字段）
gold_teacher -> 基础参考音频/兜底音频
baseline -> 基础参考音频/兜底音频
legacy_text_clone -> 历史文本克隆结果
```

## 8. 推荐使用 AI 辅助开发

你们可以使用 ChatGPT、通义千问、Claude、DeepSeek、豆包等 AI 工具辅助写前端代码，但必须把边界说清楚：只改前端展示，不改业务逻辑。

### 8.1 给 AI 的总提示词

可以直接复制下面这段给 AI：

```text
我正在做一个 AI+大赛项目《声临其境：AI 赋能的中国濒危方言数字化保护与传承平台》。

请只帮我修改前端页面展示，不要改后端业务逻辑，不要改接口字段名，不要改接口地址。

当前后端主链路会由负责人改成：CosyVoice 声音复刻 + cosyvoice-v3-flash 实时合成。

我需要优化这些文件：
- FireRedASR2S/public_web/index.html
- FireRedASR2S/public_web/styles.css
- FireRedASR2S/public_web/app.js

必须保留提交字段：
- file
- speaker_ref_audio
- text
- target_dialect
- dialect_style
- voice
- voice_clone_enabled
- voice_clone_provider

必须保留请求地址：
- /api/v1/dialect/pipeline

页面文案要统一为：
- 项目名：声临其境
- 副标题：AI 赋能的中国濒危方言数字化保护与传承平台
- 主链路：普通话/语音输入 -> 方言语义理解 -> CosyVoice 声音复刻 -> CosyVoice v3-flash 实时方言语音输出

请帮我优化页面视觉和移动端响应式，并把旧的 Qwen Voice Copy 展示文案改成 CosyVoice 声音复刻。但 JSON 字段兼容不要删除。
```

### 8.2 同学 1 给 AI 的提示词

```text
请你扮演前端 UI 工程师，帮我优化 public_web 页面。

目标：
1. 让页面更像 AI+竞赛项目展示网站。
2. 保留可操作 Demo，不要做成纯宣传页。
3. 手机端能上传或录制音频。
4. 页面主题突出濒危方言保护、侨乡文化、青年互动、乡音传承。

可修改：
- index.html 的结构和静态文案
- styles.css 的视觉和响应式
- app.js 的用户可见文案

不可修改：
- 表单字段名
- /api/v1/dialect/pipeline 接口
- 后端 Python 文件
- 业务逻辑

请输出具体代码修改建议，并说明每个修改对应哪个文件。
```

### 8.3 同学 2 给 AI 的提示词

```text
请你扮演前端交互工程师，帮我完成 RAG 看板和方言百科悬浮窗。

数据来自后端返回 JSON 的 rewrite 字段：
- rewrite.cultural_cards
- rewrite.cultural_card_terms
- rewrite.pronunciation_rule_hits
- rewrite.prosody_rule_hits
- rewrite.rag_hits
- rewrite.pronunciation_rag_hits
- rewrite.rag_hit_rate
- rewrite.rag_latency_ms
- rewrite.rag_top_score

需求：
1. RAG 看板展示最终命中次数、发音规则命中、韵律规则命中、RAG 命中率、RAG 耗时、语义相似度。
2. 方言百科卡片参考百度百科或 NotebookLM 悬浮解释。
3. 桌面端 hover 展示，手机端点击展开。
4. 无数据时显示空状态，不报错。
5. 只做展示，不把 RAG 或百科内容传给 TTS/CosyVoice。

请优先修改：
- public_web/app.js
- public_web/styles.css
- public_web/index.html
```

### 8.4 使用 AI 后必须人工检查

AI 写完代码后，必须人工检查：

- 有没有误删表单字段。
- 有没有改接口地址。
- 有没有改后端 Python 业务逻辑。
- 有没有把 `voice_clone_provider` 改名。
- 有没有把 RAG/百科内容加入提交表单。
- 手机端是否能正常显示。
- 浏览器控制台是否有 JS 报错。

## 9. 本地运行与自测

进入项目：

```powershell
cd FireRedASR2S
```

启动本地服务可优先使用：

```powershell
.\start_demo1_web.ps1
```

如果只看公网静态页面，可打开：

```text
FireRedASR2S/public_web/index.html
```

如果需要联调接口，确保后端服务可访问：

```text
http://127.0.0.1:8002
```

页面默认会请求：

```text
/api/v1/dialect/pipeline
```

## 10. 提交规范

不要直接改 `main`。每个人从最新主分支开自己的分支。

同学 1：

```bash
git pull origin main
git checkout -b feature/ui-mobile-cosyvoice
git add FireRedASR2S/public_web FireRedASR2S/web_demo
git commit -m "feat: align public web UI with CosyVoice theme"
git push origin feature/ui-mobile-cosyvoice
```

同学 2：

```bash
git pull origin main
git checkout -b feature/rag-culture-popover
git add FireRedASR2S/public_web FireRedASR2S/web_demo
git commit -m "feat: add RAG dashboard and cultural popover"
git push origin feature/rag-culture-popover
```

如果你只改了 `public_web`，就只 add 对应目录：

```bash
git add FireRedASR2S/public_web
```

## 11. 提交给负责人的内容

每个人完成后发给负责人：

- 分支名
- 修改了哪些文件
- 页面截图或手机录屏
- 本地测试结果
- 已知问题
- 是否使用 AI，以及 AI 主要帮你改了什么

示例：

```text
分支：feature/ui-mobile-cosyvoice
修改文件：
- FireRedASR2S/public_web/index.html
- FireRedASR2S/public_web/styles.css
- FireRedASR2S/public_web/app.js

完成内容：
- 改为“声临其境”主题首屏
- 适配手机端输入
- 将 Qwen Voice Copy 展示文案改为 CosyVoice 声音复刻

自测：
- Chrome 打开正常
- 手机窄屏无重叠
- 生成按钮仍提交到 /api/v1/dialect/pipeline

已知问题：
- 后端 CosyVoice 字段还未最终对齐，当前仍兼容旧 route 字段显示
```

## 12. 最终验收标准

提交前必须满足：

- 页面可打开，无 JS 报错。
- 手机窄屏下无重叠、按钮不可点、文字溢出等问题。
- 主音频、参考音频、文本输入入口都还在。
- 生成按钮仍提交到 `/api/v1/dialect/pipeline`。
- 返回结果后能显示推荐输出、总耗时、Trace ID、ASR/审查/方言文本。
- RAG 看板和文化百科区域无数据时显示空状态，不报错。
- 页面文案已经从旧 Qwen 主链路改为 CosyVoice 主链路。
- 不提交 `.env`、API Key、模型、缓存、生成音频。

## 13. 最重要的边界

本轮前端同学只负责“页面对齐”和“展示体验”。负责人会继续处理：

- CosyVoice 后端迁移
- 接口字段最终统一
- 云服务器部署
- 后端主链路验收
- 最终合并

请不要为了页面效果修改后端业务逻辑。前端只要保留字段、保留接口、做好展示，就能方便后续统一联调。
