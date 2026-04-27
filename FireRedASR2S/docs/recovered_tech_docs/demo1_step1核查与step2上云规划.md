# Demo1-Step1 核查与 Step2（DeepSeek + Qdrant）上云规划

## 1. Summary

目标：
- 核查 Demo1-Step1（ASR）是否达到“可验收、可上云前置”状态。
- 给出 Step2（LLM 方言改写 + 语义向量检索）的可执行方案，满足阿里云 ECS + Docker 部署。
- 保留向量库与语料策略的容错空间，先可用后优化。

成功标准：
- Step1 结论明确：已完成项、未完成项、补齐项一目了然。
- Step2 产出明确实施路线：接口、数据流、目录、部署、验收指标、风险兜底。
- 方案与当前技术文档一致，并可直接进入执行。

范围：
- In scope：Step1 完成度审计；Step2 架构与实施计划（DeepSeek-v4 API + Qdrant，粤语+四川话）。
- Out of scope：本轮不执行代码改造、不部署云资源、不接入 TTS。

## 2. Current State Analysis

基于仓库与文档只读核查结果：

1) Step1 资产已具备
- 文档：`c:\Users\34005\Desktop\大赛\技术文档.md` 已明确 Step1/Step2 目标与执行口径。
- ASR 脚本：`c:\Users\34005\Desktop\大赛\FireRedASR2S\examples_infer\asr\demo1_asr_eval.py` 支持单条/目录/wav.scp、批量、输出 txt/jsonl。
- 模型目录存在：
  - `c:\Users\34005\Desktop\大赛\FireRedASR2S\runtime_data\models\FireRedASR2-AED`
  - `c:\Users\34005\Desktop\大赛\FireRedASR2S\runtime_data\models\FireRedPunc`
- 结果目录存在且有多轮产物：
  - `c:\Users\34005\Desktop\大赛\FireRedASR2S\runtime_data\asr_output\`
  - 包含 `demo1_asr_result_16k_rerun.jsonl`、`demo1_asr_result_16k_rerun_punc.txt` 等。

2) Step1 当前结论
- 已完成：ASR 推理闭环（普通话音频 -> 文本）、批量评测、标点增强（Punc）。
- 已具备上云前置条件：输入规范、输出结构、批处理脚本、结果样本。
- 仍需补齐（上云前建议）：
  - HTTP 服务化（当前以 CLI 为主）；
  - 接口级鉴权、日志、错误码与限流；
  - 容器化与配置外置（ENV/配置文件）。

3) Step2 输入决策（已锁定）
- 云平台：阿里云。
- 部署形态：ECS + Docker。
- LLM：DeepSeek-v4（官方 API）。
- 向量库：Qdrant。
- 方言范围：粤语 + 四川话。
- 语料策略：混合方案（先人工词表 + 公开语料，后续可扩展第三方 API 辅助构建）。

## 3. Proposed Changes

### 3.1 Step1 收尾（上云前最小补齐）

目标：把“CLI 可用”升级为“服务可调用”。

建议新增文件（执行阶段创建）：
- `c:\Users\34005\Desktop\大赛\FireRedASR2S\asr_service\app.py`
  - FastAPI 入口，提供 `/api/v1/asr/transcribe` 与 `/healthz`。
- `c:\Users\34005\Desktop\大赛\FireRedASR2S\asr_service\asr_engine.py`
  - 封装 FireRedASR2-AED 推理加载与批处理。
- `c:\Users\34005\Desktop\大赛\FireRedASR2S\asr_service\punc_engine.py`
  - 封装 FireRedPunc，可配置开启/关闭。
- `c:\Users\34005\Desktop\大赛\FireRedASR2S\asr_service\schemas.py`
  - 请求/响应定义，统一字段：`text/confidence/timestamp/punc_text/latency_ms`。
- `c:\Users\34005\Desktop\大赛\FireRedASR2S\asr_service\config.py`
  - 模型路径、GPU 开关、批量参数、超时参数。

为什么：
- Step2 的 LLM 与向量检索需要稳定文本入口；HTTP 服务是最小公共边界。

如何做：
- 保持你已有 CLI 脚本不变，新增服务层调用同一推理逻辑，避免重复实现。

### 3.2 Step2 架构（DeepSeek-v4 + Qdrant）

目标：将 Step1 输出普通话文本，转换为“可读、可解释、可追溯”的方言文本（粤语/四川话）。

组件拆分（ECS 上 Docker Compose 推荐）：
- `gateway-api`：统一入口（鉴权、请求追踪、限流）。
- `asr-service`：复用 Step1 服务（文本输入可选跳过）。
- `dialect-service`：Step2 核心（RAG 检索 + Prompt 组装 + DeepSeek 调用 + 后处理）。
- `qdrant`：向量检索服务。
- `redis`（可选）：缓存热点短句和检索结果，降低 API 成本。

Step2 数据流：
1. 接收 `mandarin_text`（可来自 ASR 或直接文本输入）。
2. `dialect-service` 先做规范化（数字、时间、口语词清洗）。
3. 生成 embedding，检索 Qdrant Top-K 方言词条与示例句。
4. 组装 Prompt（系统指令 + 检索上下文 + 风格约束 + 禁止项）。
5. 调用 DeepSeek-v4 API 输出 `dialect_text` 与可解释字段。
6. 返回结构化结果：`dialect_text`、`glossary_hits`、`confidence_proxy`、`trace_id`。

Step2 API 草案：
- `POST /api/v1/dialect/rewrite`
  - 入参：`text`, `target_dialect`(cantonese/sichuan), `style`, `strict_level`
  - 出参：`dialect_text`, `hits[]`, `latency_ms`, `model`, `trace_id`
- `POST /api/v1/rag/upsert`
  - 入参：词条/例句/标签
  - 出参：写入条数、失败条数
- `POST /api/v1/rag/search`
  - 入参：query, target_dialect, top_k
  - 出参：候选词条及相似度

### 3.3 向量库构建（保留容错空间）

你要求可改动空间，采用“分层数据策略”：

数据层级：
- L1（强规则）：人工整理高频词表（先 200~500 条/方言）。
- L2（半结构）：公开语料抽取的“普通话-方言”短句对。
- L3（弱可信）：第三方 API 生成候选，仅入候选池，不直接高权重召回。

索引策略：
- Qdrant 建议两个 collection：
  - `dialect_lexicon`（词条级）
  - `dialect_examples`（句子级）
- metadata 字段：`dialect`, `source`, `quality_score`, `domain`, `updated_at`。
- 检索融合：词条检索 + 例句检索双路召回，再由 rerank 统一排序。

容错策略：
- 当 Qdrant 无命中或低置信命中时：
  - 自动降级为“仅 LLM 风格化改写”；
  - 返回 `degrade_mode=true`，便于后续人工补词库。

### 3.4 阿里云落地方案（ECS + Docker）

部署建议：
- 一台 ECS（8C16G 起步）先跑 Step2；ASR 可分离为 GPU 节点（后续扩展）。
- 镜像仓库：阿里云 ACR。
- 配置中心：`.env` + 机密变量（API Key 不入库）。
- 观测：结构化日志（JSON），至少记录 `trace_id`、耗时、命中率、降级率。

网络与安全：
- 仅开放 API 网关端口；
- Qdrant/Redis 内网访问；
- 开启限流与请求大小限制，防止音频/文本滥用。

## 4. Assumptions & Decisions

关键假设：
- Step1 阶段目标是“可用识别 + 基础标点 + 可复现结果”，不要求训练能力。
- DeepSeek-v4 通过官方 API 可稳定调用。
- 方言知识库先追求可用性，再逐步提升覆盖率和质量。

关键决策（已确认）：
- 阿里云 + ECS + Docker。
- Step2 使用 DeepSeek-v4 官方 API。
- 向量数据库采用 Qdrant。
- 首批方言覆盖粤语与四川话。
- 语料采用“人工词表 + 公开语料”的混合策略，并保留后续第三方 API 辅助空间。

## 5. Verification Steps

Step1 完成度复核（上线前）：
1. 复跑 `audio_16k`，输出 `jsonl/txt` 一致且无空结果异常。
2. 复跑 Punc，确认 `punc_text` 可读。
3. 抽样 20 条记录可读性并打分，形成基线报告。

Step2 功能验收（首版）：
1. `rewrite` 接口可针对粤语/四川话返回文本。
2. Qdrant 检索命中率达到设定阈值（如 Top-5 命中率>70%，可后续调参）。
3. 低命中场景触发降级策略，接口仍稳定返回。
4. 单请求延迟达到 Demo 可演示级（例如 P95 < 2s，具体按云资源校准）。

上云验收：
1. Docker Compose 一键启动（gateway/dialect/qdrant）。
2. 环境变量注入成功（DeepSeek Key、Qdrant 地址）。
3. 关键日志可追踪（trace_id 全链路贯通）。
