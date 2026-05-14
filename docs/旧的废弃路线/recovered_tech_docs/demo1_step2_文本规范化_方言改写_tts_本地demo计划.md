# Demo1-Step2 计划：文本规范化 + 粤语改写 + TTS（本地离线 Demo）

## 1. Summary

目标：

- 在现有 Step1（ASR 已完成）基础上，落地 Step2 的本地离线 Demo：
  - 普通话文本 -> 文本规范化（TN） -> 粤语文本改写 -> 粤语语音合成（TTS）。
- 先完成可演示样本链路，再为后续“接口化、网页化、音色克隆、多方言扩展”预留可升级空间。

成功标准：

- 用“昨天 ASR 样本 + 人工 10 条短句”两组输入均能稳定生成粤语文本与音频文件。
- 产出结构化结果（文本中间态、模型参数、耗时、错误原因）。
- 架构设计支持后续扩展到其他方言（不重写主流程，只加配置/词库/Prompt）。

范围：

- In scope：离线批处理 Demo、TN 基础规则（数字/时间/金额）、粤语改写、TTS 合成、结果落盘、验收标准。
- Out of scope：本轮不做“音色克隆强一致”、不做前端网页、不做线上云部署。

## 2. Current State Analysis

基于仓库与文档只读核查：

- `c:\Users\34005\Desktop\大赛\技术文档.md` 已定义主链路与 Step2 方向。
- ASR 结果已多轮落盘：`c:\Users\34005\Desktop\大赛\fireredasr2s\runtime_data\asr_output\`。
- 已有 Step1 服务化起步文件：
  - `c:\Users\34005\Desktop\大赛\fireredasr2s\asr_service\config.py`
  - `c:\Users\34005\Desktop\大赛\fireredasr2s\asr_service\schemas.py`
- 当前仓库无现成 TTS 模块与 TN 管线（需新增 Step2 目录与脚本）。

已确认的产品决策：

- 首版方言：先粤语。
- 首版交付：离线批处理 Demo。
- TTS 路线：Qwen3-TTS。
- 改写 LLM：可切换双通道（默认 DeepSeek，预留 Qwen 改写）。
- 音色策略：首版不做克隆（但保留扩展接口）。
- TN 首批覆盖：数字/时间/金额。
- 样本验收：ASR 真实样本 + 人工 10 条短句。

## 3. Proposed Changes

### 3.1 目录与文件规划（执行阶段创建）

在 `c:\Users\34005\Desktop\大赛\fireredasr2s` 下新增：

- `dialect_pipeline/`
  - `config.py`：方言、模型、路径、开关配置（含扩展位）。
  - `tn.py`：文本规范化（数字/时间/金额）。
  - `rewrite.py`：粤语改写（LLM 调用与 Prompt 组装）。
  - `tts.py`：Qwen3-TTS 调用封装（文本到 wav）。
  - `pipeline.py`：串联 TN -> Rewrite -> TTS 的主流程。
  - `run_batch_demo.py`：批处理入口（读取输入，输出结果文件）。
  - `dialect_registry.py`：方言注册表（先内置 `yue`，后续增量扩展）。
- `runtime_data/step2_input/`
  - `from_asr.txt`：来自 Step1 的文本样本（由现有 asr 结果抽取）。
  - `manual_10.txt`：人工 10 条对照短句。
- `runtime_data/step2_output/`
  - `results.jsonl`：每条样本中间态与最终态。
  - `audio/`：生成的语音文件（wav）。
  - `report.md`：一次运行的摘要报告。
- `docs/step2_local_demo.md`
  - 运行命令、参数说明、常见问题、升级路径说明。

### 3.2 Step2 处理链路（可扩展）

标准数据流：

1. 输入普通话文本（来源：ASR 结果或人工文本）。
2. TN 模块标准化：
   - 数字（如 123 -> 一百二十三）
   - 时间（如 10:30 -> 十点三十分）
   - 金额（如 58.6 元 -> 五十八点六元）
3. 粤语改写模块：
   - 通过 LLM Prompt 约束“保语义、口语化、粤语书写风格”。
   - 输出：`yue_text` + `rewrite_notes`（可解释字段）。
4. TTS 模块（Qwen3-TTS）：
   - 输入 `yue_text`，输出 `wav_path`。
5. 落盘：
   - 保存 `source_text/tn_text/yue_text/wav_path/latency/error`。

扩展空间设计：

- 方言扩展由 `dialect_registry.py` 管理：
  - `dialect_code`、Prompt 模板、词库路径、TTS 语音参数。
- 新增方言仅需新增配置与词库，不改主流程代码。
- 预留 `speaker_ref_audio` 字段，后续可无缝接入音色克隆。

### 3.3 文本规范化（TN）策略

首版规则（优先可用）：

- 数字：整数、小数、百分比。
- 时间：`HH:MM`、日期样式（基础版）。
- 金额：元/角/分常见表达。

实现建议：

- 规则优先（可控、可调试），复杂场景留到后续版本。
- 每条样本保留 `tn_diff`，便于人工审阅。

### 3.4 粤语改写策略（LLM）

Prompt 要点：

- 保留原意，不虚构事实。
- 优先口语常用粤语表达，避免生硬直译。
- 对专有名词、数字、单位保持一致。
- 输出纯文本（无解释）给 TTS，解释写入侧通道字段。

容错机制：

- 改写失败时回退到 TN 文本直送 TTS（不中断整批任务）。
- 记录 `degrade_mode=true` 与错误信息，便于复盘。

脚本实现顺序（明确回答）：

1. 先实现 `tn.py`（规则可控，降低后续改写漂移）。
2. 再实现 `rewrite.py`（调用 LLM 完成普通话 -> 粤语文本）。
3. 最后接 `tts.py`（将粤语文本生成音频）。

`rewrite.py` 原型（执行阶段按此落地）：

```python
from __future__ import annotations
import os
import time
from dataclasses import dataclass
from typing import Any
import requests


@dataclass
class RewriteConfig:
    api_base: str = "https://api.deepseek.com/v1/chat/completions"
    api_key: str = ""
    model: str = "deepseek-chat"
    timeout_s: int = 45


def build_prompt(tn_text: str) -> list[dict[str, str]]:
    system = (
        "你是粤语文本改写助手。要求："
        "1) 保持原意；2) 使用自然口语化粤语书写；"
        "3) 不扩写事实；4) 输出仅一行改写文本。"
    )
    user = f"请将下面普通话文本改写为粤语：\n{tn_text}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def rewrite_to_cantonese(tn_text: str, cfg: RewriteConfig) -> dict[str, Any]:
    t0 = time.perf_counter()
    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": cfg.model,
        "messages": build_prompt(tn_text),
        "temperature": 0.2,
    }
    try:
        resp = requests.post(cfg.api_base, headers=headers, json=payload, timeout=cfg.timeout_s)
        resp.raise_for_status()
        data = resp.json()
        yue_text = data["choices"][0]["message"]["content"].strip()
        return {
            "ok": True,
            "yue_text": yue_text,
            "degrade_mode": False,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            "raw": data,
        }
    except Exception as e:
        return {
            "ok": False,
            "yue_text": tn_text,  # 降级回退
            "degrade_mode": True,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            "error": str(e),
        }
```

LLM 调用规范（补全“怎么调用、需要什么”）：

双通道调用（回答“要不要 DeepSeek”）：

- 需要，且作为默认改写通道：`provider=deepseek`。
- 同时预留 `provider=qwen`，用于后续切换或 A/B 测试。
- 统一由 `rewrite.py` 入口路由，不改主流程：
  - `rewrite_to_cantonese(text, provider="deepseek")`
  - 返回字段保持一致（`yue_text/degrade_mode/llm_model/llm_latency_ms/llm_error`）。

1. 调用方式（HTTP）

- 方法：`POST`
- Endpoint：`https://api.deepseek.com/v1/chat/completions`
- Header：
  - `Authorization: Bearer <DEEPSEEK_API_KEY>`
  - `Content-Type: application/json`
- Body（建议首版）：
  - `model`: `deepseek-chat`（若你后续拿到 v4 的正式模型名，可替换）
  - `messages`: system + user
  - `temperature`: `0.2`
  - `max_tokens`: `512`

1. 你必须提供的配置（最小集合）

- `DEEPSEEK_API_KEY`：已脱敏，请从本地 `.env` 或系统环境变量读取，不要写入文档。
- `DEEPSEEK_BASE_URL`：默认 `https://api.deepseek.com/v1/chat/completions`，可覆盖。
- `DEEPSEEK_MODEL`：默认 `deepseek-chat`，后续可切换。
- Qwen 改写通道（预留）：
  - `QWEN_LLM_API_KEY`
  - `QWEN_LLM_BASE_URL`
  - `QWEN_LLM_MODEL`

1. 调用输出解析规则

- 主取：`choices[0].message.content`
- 兜底：若无该字段，判定失败并触发降级。
- 输出统一字段：
  - `yue_text`
  - `degrade_mode`
  - `llm_model`
  - `llm_latency_ms`
  - `llm_error`（失败时）

1. 重试与容错（必须实现）

- 超时：`timeout=45s`。
- 重试：最多 2 次，指数退避（1s, 2s）。
- 降级：
  - LLM 连续失败 -> 回退 `yue_text = tn_text`；
  - 标记 `degrade_mode=true`；
  - 不中断整批任务。

1. Prompt 结构（稳定输出）

- `system`：
  - 指定角色：粤语改写助手。
  - 约束：保语义、不编造、口语化、输出单行文本。
- `user`：
  - 仅包含待改写文本与必要风格标签。
- 禁止项：
  - 不输出解释段落；
  - 不添加“以下是改写结果：”等前缀。

1. 成本与稳定性控制（离线 Demo 也建议）

- 对完全相同 `tn_text` 做本地缓存（减少重复调用）。
- 限制并发（例如 2\~4）防止 API 限流。
- `results.jsonl` 写入 token 用量与耗时，便于后续上云预算评估。

### 3.5 TTS 策略（Qwen3-TTS）

首版目标：

- 稳定生成可听音频，验证“文本到语音”链路。
- 不追求音色一致性（后续阶段再引入克隆）。

输出约束：

- 统一输出为 wav（采样率固定），便于后续前端播放和评测。

### 3.6 验收指标（本地离线）

功能验收：

- 两组输入（ASR 样本 + 人工 10 条）均完成全链路输出。
- 失败样本可追踪，且不影响其他样本处理。

质量验收：

- 文本：粤语改写可读、语义基本一致。
- 音频：可播放、无明显截断/损坏。

工程验收：

- 一条命令可复跑，输出目录结构稳定。
- 配置可切换方言代码（即使目前只启用粤语）。

### 3.7 你需要提供的前置信息（回答“要不要 Qwen API”）

说明：

- 本地离线 Demo 若按“Qwen3-TTS 路线”，需要可调用的 TTS API 或本地可运行推理端。
- 粤语改写使用 LLM（当前计划沿用 DeepSeek 文本改写），也需要 API Key。

你需要准备：

1. 改写 LLM（至少一条通道可用）：
   - 必选默认：`DEEPSEEK_API_KEY`
   - 预留可选：`QWEN_LLM_API_KEY`、`QWEN_LLM_BASE_URL`、`QWEN_LLM_MODEL`
2. Qwen3-TTS 的接入方式二选一：
   - API 方式：`QWEN_TTS_API_KEY`、`QWEN_TTS_BASE_URL`、`QWEN_TTS_MODEL`；
   - 本地推理方式：本地模型路径、推理启动命令、调用协议（HTTP/gRPC）。
3. 人工 10 条短句（`manual_10.txt`）用于对照验收。

若你暂时没有 Qwen-TTS API：

- 计划允许先跑“TN + 粤语改写文本输出”，把 TTS 阶段置为可选开关（`--skip-tts 1`），先验证文本侧质量。

### 3.8 优先级与难度（回答“先做什么、难度如何”）

P0（先做）：

- TN + 粤语改写（文本链路），可不依赖 TTS API。
- 难度：中等（规则 + Prompt 调优 + 容错）。

P1（随后）：

- 接入 Qwen3-TTS 输出音频。
- 难度：中等偏高（接口适配 + 音频参数调试）。

P2（留扩展位）：

- 网页展示、HTTP 接口、音色克隆、多方言扩展。
- 难度：高（涉及部署、并发、稳定性治理）。

## 4. Assumptions & Decisions

关键假设：

- 你当前重点是“先看到本地可运行效果”，不是一次性完成线上化。
- Step1 的 ASR 结果可作为 Step2 初始输入源。

关键决策（已锁定）：

- 先粤语，后续再扩其他方言。
- 先离线批处理 Demo，后续再做接口与网页。
- 先不做音色克隆，但保留扩展字段与配置位。
- 先做 TN 基础规则（数字/时间/金额），逐步扩展。

## 5. Verification Steps

执行阶段验证步骤：

1. 从 `runtime_data/asr_output/*.txt` 抽取一批文本，生成 `from_asr.txt`。
2. 准备 `manual_10.txt`（人工短句）。
3. 执行 `run_batch_demo.py`，输出 `results.jsonl` 与 `audio/*.wav`。
4. 抽样听音 + 文本核查，记录 3 类问题：
   - TN 错误
   - 改写偏义
   - TTS 播放异常
5. 生成 `report.md`，沉淀下一轮优化清单（为接口化/网页化/音色克隆做准备）。
