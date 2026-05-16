# Tasks

- [ ] Task 1: Fix Dialect Rewrite Bypass in Audio Pipeline
  - [ ] SubTask 1.1: Modify `process_audio` in `FireRedASR2S/dialect_service/pipeline_engine.py`. Remove the restriction that skips `rewrite_text` for CosyVoice audio inputs (ensure ASR text is sent to LLM for dialect translation).
  - [ ] SubTask 1.2: Verify that `clean_realtime_speech_text` consumes the output of the rewrite (e.g., `dialect_text` or `semantic_text`) instead of the raw ASR text.

- [ ] Task 2: Implement Robust Retry Logic for External APIs
  - [ ] SubTask 2.1: Update `_post_json` in `FireRedASR2S/fireredasr2s/dialect_pipeline/cosyvoice.py` to include a retry loop (e.g., 3 retries, exponential backoff) for handling timeouts, HTTP 429, and 50X errors.
  - [ ] SubTask 2.2: Add similar retry logic to the LLM rewrite API calls in `rewrite.py` or `adapters.py` to prevent intermittent failures from breaking the pipeline.

- [ ] Task 3: Create Cloud Deployment Script
  - [ ] SubTask 3.1: Create a PowerShell script `FireRedASR2S/scripts/deploy_to_cloud.ps1`.
  - [ ] SubTask 3.2: Implement SCP/SSH commands within the script that utilize the private key located at `"C:\Users\34005\Downloads\dialectconvert_key.pem"` to transfer code to a target cloud server and restart the services. (The script should accept the server IP/hostname as a parameter).

# Task Dependencies
- Task 1 and Task 2 can be executed in parallel.
- Task 3 is independent and can be executed in parallel.