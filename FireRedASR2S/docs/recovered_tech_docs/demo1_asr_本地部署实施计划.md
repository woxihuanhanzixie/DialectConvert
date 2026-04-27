# Demo1-Step1（ASR）本地部署实施计划

## 1. Summary

目标：在当前 Windows 电脑上完成 Demo1 第一步“普通话语音 -> ASR 文本”的本地可运行版本，为后续 LLM 方言改写与 TTS 音色克隆提供稳定输入。

成功标准：
- 本地可调用 ASR 推理，输入 3-15 秒普通话音频可返回文本。
- 提供统一接口（后续可被小程序/前端调用）。
- 不污染现有开发环境（全程隔离在独立 Conda 环境）。

范围：
- In scope：FireRedASR2-AED 模型下载、推理打通、接口封装、基础日志和验收。
- Out of scope：本阶段不接入 LLM、RAG、TTS、数字人。

## 2. Current State Analysis

已确认的本机环境（只读检查结果）：
- 操作系统：Windows。
- Python：3.11.9（当前默认环境）。
- Conda：23.10.0（可用）。
- Git：2.53.0（可用）。
- GPU：NVIDIA GeForce RTX 5060 Laptop GPU，显存约 8GB，可用于推理。
- 驱动/CUDA：驱动 577.05，`nvidia-smi` 显示 CUDA 12.9。
- 磁盘可用：C 盘约 183GB，D 盘约 399GB，满足代码和模型下载。
- WSL：未安装（不是必需项）。
- 当前默认 Python 环境无 `torch`（说明需要在新环境中安装依赖，不影响现有环境）。

已有项目文档状态：
- `技术文档.md` 已明确 Demo1 最终链路与当前 Step1（ASR）优先级。
- 当前需要落地的是 Step1 的本地部署与接口化。

## 3. Proposed Changes

### 3.1 技术路线与模型选择（决策）

- 模型选择：`FireRedASR2-AED`（用于 Step1）。
- 选择理由：
  - 相比 LLM 版更适合先做稳定、低复杂度 ASR 基线。
  - 支持普通话和后续方言扩展；可输出时间戳和置信度（按需开启）。
  - 更贴合 Demo1 第一步“先识别再扩展”的目标。

### 3.2 部署方式（决策）

- 采用 Windows 原生部署，不先上虚拟机 Linux。
- 如遇到 Windows 依赖兼容问题，再切换 WSL2 作为兜底方案。

### 3.3 实施步骤（执行清单）

1. 创建隔离环境（防污染）
- 新建 `conda` 环境（Python 3.10），所有依赖仅安装在该环境内。
- 不在 `base` 环境安装任何项目依赖。

2. 获取代码与依赖
- 克隆 `FireRedASR2S` 仓库。
- 安装 `requirements.txt`。

3. 下载 ASR 模型
- 优先通过 ModelScope 下载 `FireRedASR2-AED` 到项目目录 `pretrained_models/FireRedASR2-AED`。

4. 跑通最小推理
- 使用仓库示例脚本或最小调用代码，对单个 wav 音频执行识别。
- 验证输出文本可用。

5. 封装统一接口（FastAPI）
- 提供 `POST /api/v1/asr/transcribe`。
- 输入：音频文件（建议 16kHz/mono/wav）。
- 输出：`text`，可选 `timestamps`、`confidence`、`latency_ms`。

6. 进行 Step1 验收
- 使用校园场景样本（宿舍/教室）进行测试。
- 记录识别成功率、平均时延、典型失败样例。

### 3.4 建议新增文件（执行阶段创建）

以下文件将在你确认后执行阶段创建（当前计划阶段不改业务文件）：
- `asr_service/app.py`：FastAPI 入口与路由。
- `asr_service/asr_engine.py`：FireRedASR2-AED 推理封装。
- `asr_service/schemas.py`：请求/响应结构定义。
- `asr_service/config.py`：模型路径与运行参数。
- `asr_service/README.md`：本地运行与调用说明。

## 4. Assumptions & Decisions

关键假设：
- 你当前目标是先交付 Demo1 的 Step1（ASR），不要求同一阶段完成 LLM 和 TTS。
- 接口优先非流式（上传短音频后返回文本），先保证可用性。
- 前端或小程序暂时可以用 Postman/脚本替代联调。

关键决策：
- 不需要先装 Linux 虚拟机。
- 采用独立 Conda 环境，避免破坏你现有电脑环境。
- 先做 FireRedASR2-AED，再逐步接入 LLM/TTS。

## 5. Verification Steps

环境隔离验收：
- `conda env list` 中出现独立环境（如 `fireredasr2s`）。
- 退出该环境后，系统 Python 包不变化。

功能验收：
- 提交普通话 wav 文件，接口返回有效文本且无报错。
- 至少 20 条短音频测试通过，记录失败日志。

稳定性验收：
- 连续请求无崩溃。
- 错误输入（空文件/格式不符）返回可读错误码。

扩展就绪验收：
- ASR 输出字段满足后续 LLM/TTS 调用需要（至少包含 `text`）。
