# Fix Dialect Output and Cloud Deployment Spec

## Why
当前网页输出存在两个严重问题：
1. **方言输出失效（变回中文）**：当用户上传音频时，后端的 `process_audio` 逻辑在 CosyVoice 分支中，受限于 `cosyvoice_text_only_rewrite` 配置，错误地跳过了 LLM 方言改写阶段，导致 ASR 识别出的普通话直接进入 TTS。
2. **输出极不稳定**：连续请求时常发生失败。这通常是由于公网 API（CosyVoice/Qwen TTS 或 DeepSeek LLM）的并发限制（QPS 限流）、网络超时或未捕获的瞬时异常导致，缺乏有效的重试机制。
同时，需要将修复后的稳定代码通过提供的私钥 (`dialectconvert_key.pem`) 部署到云端服务器。

## What Changes
- **修复方言改写绕过问题**：修改 `dialect_service/pipeline_engine.py` 中的 `process_audio` 逻辑，移除或修正阻碍音频输入进行方言改写的条件（如强制 `enable_rewrite` 生效），确保 ASR 文本必须经过 LLM 翻译为方言后再送入 TTS。
- **增强后端 API 调用稳定性**：在 `fireredasr2s/dialect_pipeline/cosyvoice.py` 和 `rewrite.py` / `adapters.py` 中，针对 HTTP 请求（如 `_post_json`）增加指数退避的自动重试机制（Retry logic），以应对瞬时网络抖动或限流。
- **云端一键部署脚本**：新增自动化部署脚本（如 `deploy_to_cloud.ps1`），集成使用指定的私钥文件 `C:\Users\34005\Downloads\dialectconvert_key.pem` 通过 SSH/SCP 将本地代码同步并部署到云端服务器。

## Impact
- Affected code: 
  - `FireRedASR2S/dialect_service/pipeline_engine.py` (改写流转逻辑)
  - `FireRedASR2S/fireredasr2s/dialect_pipeline/cosyvoice.py` (网络请求与重试)
  - `FireRedASR2S/dialect_service/adapters.py` (LLM 调用重试)
  - `FireRedASR2S/scripts/deploy_to_cloud.ps1` (新增部署脚本)

## ADDED Requirements
### Requirement: Cloud Deployment Automation
The system SHALL provide a secure and automated script to deploy the codebase to a remote cloud server using SSH key-based authentication.

#### Scenario: Success case
- **WHEN** user executes the deployment script with the server IP
- **THEN** the script uses the local `.pem` key to securely transfer files via SCP/Rsync, installs dependencies, and restarts the remote `dialect_service`.

## MODIFIED Requirements
### Requirement: Enforced Dialect Rewrite for Audio
The system SHALL ensure that all audio inputs passing through the pipeline are rewritten into the target dialect before speech synthesis, unless explicitly disabled by the user.

### Requirement: Resilient External API Calls
The system SHALL automatically retry external API calls (LLM and TTS) up to 3 times with exponential backoff upon encountering HTTP 429 (Too Many Requests), 500+ server errors, or network timeouts.