# AGENTS.md

## 项目定位

"声临其境"是一个方言音色复刻 Web 应用。用户在手机或电脑上录制/上传一段参考语音，系统完成 ASR 转写、方言口语化改写、情绪与语调分析、CosyVoice 音色注册和方言语音合成，最终输出带有用户注册音色的粤语、四川话或闽南话语音。

## 当前结构

- `app/`: FastAPI 后端。
- `app/main.py`: HTTP 入口，提供首页、健康检查、`/api/convert`、`/api/preview-audio` 和 `/api/speak-with-voice`。
- `app/models.py`: API 响应模型。
- `app/pipeline.py`: 当前主链路编排，顺序为清理缓存、ASR、情绪/标点分析、**RAG 方言知识检索**、方言改写、CosyVoice 方言 instruction 构造、系统音色合成、音色注册/缓存复用、用户音色方言合成。
- `app/providers.py`: DashScope/Qwen/CosyVoice API 调用，包括 ASR、LLM 改写（含 RAG 上下文注入）、情绪标注、音色注册和语音合成。
- `app/rag/`: **方言 RAG 语义增强模块**（详见「RAG 方言语义增强」节）。
  - `__init__.py`: 模块入口。
  - `graph.py`: 方言知识图谱扩展接口，默认无 provider；后续 Neo4j/NetworkX/RDF 可通过 `set_dialect_graph_provider()` 注入。
  - `knowledge_base.py`: JSON 知识库加载、缓存、关键词检索。
  - `retriever.py`: jieba 分词 + 关键词匹配检索器，返回 prompt 可注入片段。
  - `data/cantonese.json`: 粤语词汇对照表（40+ 条目）。
  - `data/sichuanese.json`: 四川话词汇对照表（40+ 条目）。
  - `data/hokkien.json`: 闽南话词汇对照表（40+ 条目）。
- `app/storage.py`: 上传文件、输出文件、元数据、音色缓存和运行时清理。
- `app/audio_utils.py`: 音频预览、时长检测、移动端格式兼容和错误识别。
- `static/`: 单页前端。
- `scripts/deploy_tencent_cloud_tar.sh`: 推荐部署脚本。
- `scripts/deploy_tencent_cloud.ps1`: PowerShell 备用部署脚本。
- `tests/`: 单元测试。
- `docs/`: 技术文档与执行记录。
- `runtime_data/`: 本地/服务器运行时数据目录，已被 `.gitignore` 排除。

## 当前真实语音链路

1. 前端提交 `audio` 和 `dialect`（`cantonese`、`sichuanese`、`hokkien`）。
2. 后端保存上传文件。
3. `transcribe_audio` 调用 DashScope Paraformer `paraformer-v2` 得到原始 ASR 文本。
4. `analyze_expression` 用 Qwen LLM 恢复标点，生成 `emotion_label` 与 `prosody_instruction`。
5. **`retrieve_dialect_knowledge` 用 jieba 分词检索方言知识库，生成 RAG 上下文片段。**
6. **`rewrite_to_dialect` 接收 RAG 上下文，在 prompt 中注入方言词汇参考后生成自然方言文本。**
7. `build_tts_instruction` 合并官方方言指令和短情绪语调。
8. `synthesize`（Gold Teacher）使用 `cosyvoice-v3-plus` + 系统音色 `longanyang` 生成系统音色方言音频。
9. `enroll_voice` 使用参考音频调用 CosyVoice voice-enrollment 注册音色；相同参考音频 + 相同 target_model 命中缓存则复用。
10. `synthesize`（Voice Matched）使用注册的 `voice_id` + `cosyvoice-v3.5-plus` 生成用户音色方言音频。
11. `recommended_audio_url` 优先使用 Voice Matched；失败回退 Gold Teacher。
12. 前端展示结果；Voice Matched 成功后可复用 `voice_id` 继续合成。

## 当前模型与接口配置

### LLM（方言改写 + 情绪分析）

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `QWEN_LLM_MODEL` | `qwen3.7-max` | 当前新旗舰。旧 `qwen-plus`/`qwen-max` 将于 2026-07-13 下线 |
| `QWEN_LLM_BASE_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | OpenAI 兼容端点 |
| `QWEN_LLM_API_KEY` | 为空时回退 `DASHSCOPE_API_KEY` | 支持单独管理 |

备选模型：
- `qwen3.6-plus`：成本/效果均衡，日常改写可降级使用
- `qwen3-max`：上一代 Max，稳定但不再作为默认首选

### ASR

| 配置项 | 值 |
|--------|-----|
| `ASR_MODEL` | `paraformer-v2` |

### TTS — Gold Teacher（系统音色）

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `QWEN_TTS_MODEL` | `cosyvoice-v3-plus` | 保留系统音色 + instruction 控制 |
| `QWEN_TTS_VOICE` | `longanyang` | 系统内置音色 |

### TTS — Voice Matched（用户音色复刻）

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `QWEN_VOICE_TARGET_MODEL` | `cosyvoice-v3.5-plus` | **最强音色复刻模型，仅北京地域可用，无系统音色** |
| `QWEN_TTS_VC_MODEL` | `cosyvoice-v3.5-plus` | 兼容旧音色迁移配置；当前主链路使用 `QWEN_VOICE_TARGET_MODEL` |
| `QWEN_VOICE_ENROLLMENT_MODEL` | `voice-enrollment` | 音色注册 |
| `QWEN_VOICE_ENROLLMENT_URL` | DashScope customization URL | |

### 模型选择依据

- **Gold Teacher 用 v3-plus**：需要系统音色 `longanyang` 作为兜底输出。v3.5-plus 不支持系统音色。
- **Voice Matched 用 v3.5-plus**：音色复刻效果最强，支持 17+ 方言、指令控制（语速/情绪/风格）。
- **LLM 用 qwen3.7-max**：方言改写是质量瓶颈，用最新 Max 系列提升准确率与长上下文余量。

## RAG 方言语义增强

### 定位

在 ASR 之后、LLM 方言改写之前，检索方言知识库，将匹配到的方言词汇/习惯表达注入 LLM prompt，提升方言改写的准确性和地道感。

```
ASR → analyze_expression → retrieve_dialect_knowledge → rewrite_to_dialect(rag_context=...) → TTS
```

### 检索原理

1. `jieba` 对 ASR 原文分词
2. 每个 token 与知识库 JSON 的 `keyword` 字段做双向子串匹配
3. 按匹配数排序，返回 Top-5
4. 格式化为 prompt snippet：`「年轻人」→ 后生仔（口语常用，含亲切感）`
5. 注入到 `rewrite_to_dialect` 的 system prompt 中

### 图谱扩展接口

`app/rag/graph.py` 预留了 `DialectGraphProvider` 协议和 `GraphDialectFact` 数据结构。默认不注册 provider，因此现有 JSON 词库检索行为不变；后续接入 Neo4j、NetworkX、RDF 或远端图谱服务时，只需实现 `query(source_text, dialect, top_k)` 并调用 `set_dialect_graph_provider(provider)`，`retriever.py` 会把图谱语义关系追加到同一个 RAG prompt 片段。

### 知识库文件

每种方言一个 JSON 文件，格式：
```json
{"keyword": "年轻人", "dialect_expression": "后生仔", "category": "人称",
 "usage_note": "口语常用，含亲切感", "context": "泛指年轻一代"}
```

当前每种方言 ~40 条种子数据，持续扩充中。详细方案见 `docs/RAG方言语义增强实现方案.md`。

## 方言知识图谱（后续计划）

在 RAG 词 ↔ 词对照基础上，构建结构化的方言语义图谱：

- **概念层**：方言特有概念（如粤语「畀」= 让/给）
- **关系层**：同义、上下位、语用语境、情感色彩
- **候选工具**：Neo4j / NetworkX / Apache Jena
- **数据来源**：方言田野调查、影视字幕、社交媒体语料

详见 `docs/RAG方言语义增强实现方案.md` 的「方言知识图谱 — 后续计划」节。

## 运行时与缓存

- 真实转换必须配置 `DASHSCOPE_API_KEY` 和公网可回拉的 `PUBLIC_BASE_URL`。
- `runtime_data/uploads` / `outputs` / `jobs` / `voice_cache`。
- `cleanup_runtime`、`CLEANUP_AFTER_HOURS`、`VOICE_CACHE_TTL_HOURS` 控制磁盘增长。
- `ENABLE_MOCK_WHEN_NO_KEY=1` 只用于无密钥本地演示或测试。

## 部署约定

优先使用 WSL/Ubuntu 或 Linux 部署：

```bash
cd /mnt/d/dialect\ convert
bash scripts/deploy_tencent_cloud_tar.sh 43.139.53.84 root /opt/dialect-convert 7860 http://43.139.53.84
```

部署后检查：

```bash
curl -s http://43.139.53.84/health
ssh -i ~/.ssh/dialectconvert_key.pem root@43.139.53.84 "systemctl is-active dialect-convert"
```

`/health` 的静态资源字段应为 `true`。

## 安全约束

- 不提交 `.env`、私钥、API key、上传音频、输出音频和运行缓存。
- 不在日志、文档或提交信息中暴露密钥内容。
- `voice_id` 是可复用音色标识，不应作为公开示例写入仓库。
- CosyVoice `instruction` 保持短句（≤95 字符），避免超长指令影响方言输出或触发接口限制。

## 文档维护

- `README.md` 是 GitHub 首页展示入口。
- 修改 `app/config.py` 中的默认模型或环境变量后，必须同步更新 `README.md`、`.env.example`、`.env.prod.example` 和本文件。
- RAG 知识库新增条目后，标注来源（人工审校 / LLM 辅助），并在 `docs/RAG方言语义增强实现方案.md` 中更新条目统计。
- 如果后续移除 Gold Teacher 兜底或引入音频格式迁移链路，必须同步修改 `app/pipeline.py`、`app/models.py`、`static/app.js`、测试和文档。
