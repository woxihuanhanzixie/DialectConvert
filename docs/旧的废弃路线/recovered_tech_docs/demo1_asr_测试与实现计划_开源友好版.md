# Demo1-Step1（ASR）测试与实现计划（开源友好版）

## 1. Summary

目标：在你已完成本地部署的基础上，先完成 Demo1 的 ASR 子功能（普通话语音转文本）的可验收版本，采用 CLI 优先交付，并保留后续开源与扩展到 HTTP 接口的可维护结构。

本轮成功标准：
- 可通过 CLI 对示例音频完成识别并输出结构化结果文件。
- 输出中可评估“准确率（文本可读性）+ 时延（RTF/耗时）”两类指标。
- 形成可复用的目录规范、参数模板和验收流程，方便后续开源改造。

本轮范围：
- In scope：ASR（FireRedASR2-AED）推理测试、结果落盘、指标验收、文档化执行步骤。
- Out of scope：LLM 方言改写、TTS 音色克隆、数字人输出（属于 Demo1 后续 Step2/Step3）。

## 2. Current State Analysis

基于当前环境与仓库的只读确认：
- 项目路径存在：`c:/Users/34005/Desktop/大赛/FireRedASR2S`。
- 技术目标文档存在：`c:/Users/34005/Desktop/大赛/技术文档.md`，且已将 Demo1-Step1 定义为“普通话语音 -> ASR 文本”。
- 仓库已提供 ASR 推理入口：
  - `examples_infer/asr/inference_asr_aed.sh`
  - `fireredasr2s/fireredasr2/speech2text.py`
  - `fireredasr2s/fireredasr2/asr.py`
- 仓库 README 已给出 ASR Python API 与 CLI 使用方式：
  - `README.md`（Quick Start、Python API、ASR module usage）
- 你偏好的交付策略已明确：
  - CLI 脚本验收优先
  - 先用仓库示例音频
  - 指标采用准确率+时延平衡评估
  - 需兼顾后续开源易改造

## 3. Proposed Changes

### 3.1 交付策略（先快验收，后易扩展）

采用“两层交付”：
1. 第一层（本轮必做）：CLI 稳定验收链路
- 直接复用 `speech2text.py` / `inference_asr_aed.sh` 思路，完成 ASR 批量识别。
- 统一生成可比对结果文件（`txt` + `jsonl` + 可选 `wer`）。

2. 第二层（为开源预留）：接口化准备
- 不强制本轮实现 HTTP，但本轮结果格式、参数命名和目录布局按后续 API 兼容设计。
- 后续只需加薄封装即可迁移到 FastAPI。

### 3.2 文件级实施清单（执行阶段将修改/新增）

1. 更新项目内执行文档（开源友好）
- 文件：`FireRedASR2S/README.md`（新增“Windows/CLI 验收补充段”或单独文档链接）
- 目的：明确 Demo1-Step1 的最小可运行流程与验收口径。

2. 新增 Demo1 运行脚本（跨平台友好，避免仅依赖 .sh）
- 文件：`FireRedASR2S/examples_infer/asr/demo1_asr_eval.py`（建议）
- 内容：
  - 读取示例音频列表
  - 调用 `FireRedAsr2.from_pretrained("aed", ...)`
  - 输出 `out/demo1_asr_result.jsonl` 与 `out/demo1_asr_result.txt`
  - 统计简单时延指标（平均处理时长、平均 RTF）
- 原因：Windows 下直接执行 `.sh` 不稳定，Python 脚本更利于开源复用。

3. 新增结果样例与说明
- 文件：`FireRedASR2S/examples_infer/asr/out/README_demo1.md`（建议）
- 内容：
  - 字段说明（text/confidence/dur_s/rtf/timestamp）
  - 验收标准与失败排查（音频格式、模型路径、GPU开关）

4. 同步你的项目技术文档中的“测试与验收”段落
- 文件：`技术文档.md`
- 内容：
  - 增加 Demo1-Step1 的测试流程（输入、命令、输出、指标）
  - 增加“开源可维护性”说明（脚本化、参数化、目录规范）

### 3.3 数据流与接口约定（为后续 API 兼容）

输入：
- wav（16kHz, 16-bit, mono, PCM）
- 可接受 wav_path / wav_dir / wav_scp 三种模式（与现有脚本一致）

输出（统一字段）：
- `uttid`
- `text`
- `confidence`
- `dur_s`
- `rtf`
- `timestamp`（可选）

验收输出文件：
- `*.txt`：便于人工快速阅读
- `*.jsonl`：便于后续 API 与前端结构化消费

### 3.4 失败模式与兜底

主要风险：
- Windows 下 Bash 脚本兼容性问题。
- 音频格式不符导致识别为空。
- CPU 环境时延偏高。

兜底策略：
- 优先用 Python 脚本替代 `.sh` 执行逻辑。
- 在执行前加入音频格式检查与错误提示。
- 先以 CPU 完成功能验收，再切 GPU 做性能提速。

## 4. Assumptions & Decisions

关键假设：
- 你本地 ASR 依赖已可用，当前重点是“测试与可验收实现”。
- 本轮不接入 LLM/TTS，只做 Demo1-Step1 的可证明结果。

关键决策：
- 交付优先级：CLI 验收 > HTTP 接口。
- 测试数据优先级：仓库示例音频优先。
- 指标优先级：准确率与时延平衡评估。
- 设计原则：开源友好（脚本化、参数化、文档化、可复用目录）。

## 5. Verification Steps

执行验收步骤（实现阶段）：
1. 运行 Demo1 ASR 评估脚本，完成示例音频批量推理。
2. 检查 `jsonl/txt` 是否完整生成且字段齐全。
3. 抽查文本可读性（至少 5 条样例）。
4. 统计平均耗时/RTF，并输出评估结论。
5. 将流程与指标写回 `技术文档.md` 的 Demo1-Step1 测试章节。

通过标准：
- CLI 一键可运行，且输出稳定。
- 文本识别结果可读、无大面积空结果。
- 形成可复用文档与脚本，后续可直接扩展为 HTTP 接口。
