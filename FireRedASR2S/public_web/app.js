const els = {
  inputAudio: document.getElementById("input-audio"),
  refAudio: document.getElementById("ref-audio"),
  targetDialect: document.getElementById("target-dialect"),
  voice: document.getElementById("voice"),
  voiceMatchedEnabled: document.getElementById("voice-matched-enabled"),
  voiceCloneProvider: document.getElementById("voice-clone-provider"),
  submitBtn: document.getElementById("submit-btn"),
  statusText: document.getElementById("status-text"),
  recommendedOutput: document.getElementById("recommended-output"),
  totalLatency: document.getElementById("total-latency"),
  errorText: document.getElementById("error-text"),
  goldAudio: document.getElementById("gold-audio"),
  goldDownload: document.getElementById("gold-download"),
  goldNote: document.getElementById("gold-note"),
  matchedAudio: document.getElementById("matched-audio"),
  matchedDownload: document.getElementById("matched-download"),
  matchedNote: document.getElementById("matched-note"),
  asrText: document.getElementById("asr-text"),
  reviewedText: document.getElementById("reviewed-text"),
  semanticText: document.getElementById("semantic-text"),
};

const API_BASE = (() => {
  if (window.__APP_API_BASE__) {
    return String(window.__APP_API_BASE__).replace(/\/$/, "");
  }
  const sameHost = `${window.location.protocol}//${window.location.host}`;
  if (window.location.port === "8002") {
    return sameHost;
  }
  if (window.location.protocol === "file:") {
    return "http://127.0.0.1:8002";
  }
  return "";
})();

function setStatus(message, state) {
  els.statusText.textContent = message;
  els.statusText.className = `status ${state}`;
}

function setAudioCard(audioEl, linkEl, noteEl, route, emptyMessage) {
  const audioUrl = route?.audio_url || "";
  if (audioUrl) {
    audioEl.src = audioUrl;
    linkEl.href = audioUrl;
    linkEl.classList.remove("hidden");
    noteEl.textContent = route?.route_reason || "已生成，可直接播放或下载。";
    return;
  }
  audioEl.removeAttribute("src");
  audioEl.load();
  linkEl.removeAttribute("href");
  linkEl.classList.add("hidden");
  noteEl.textContent = route?.error || route?.fallback_reason || emptyMessage;
}

function readJsonError(payload) {
  if (!payload) return "请求失败";
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload.detail)) return payload.detail.map((item) => item.msg || JSON.stringify(item)).join("；");
  return "请求失败";
}

async function submitPipeline() {
  const mainAudio = els.inputAudio.files?.[0];
  if (!mainAudio) {
    setStatus("请先上传主音频。", "error");
    return;
  }

  const [targetDialect, dialectStyle] = els.targetDialect.value.split(":");
  const form = new FormData();
  form.append("file", mainAudio);
  if (els.refAudio.files?.[0]) {
    form.append("speaker_ref_audio", els.refAudio.files[0]);
  }
  form.append("enable_punc", "true");
  form.append("enable_rewrite", "true");
  form.append("enable_tts", "true");
  form.append("segment_max_len", "28");
  form.append("voice", els.voice.value);
  form.append("target_dialect", targetDialect);
  form.append("dialect_style", dialectStyle);
  form.append("voice_clone_enabled", els.voiceMatchedEnabled.checked ? "true" : "false");
  form.append("voice_clone_provider", els.voiceCloneProvider.value);

  els.submitBtn.disabled = true;
  setStatus("正在处理，请稍候…", "loading");

  try {
    const resp = await fetch(`${API_BASE}/api/v1/dialect/pipeline`, {
      method: "POST",
      body: form,
    });
    const payload = await resp.json();
    if (!resp.ok) {
      throw new Error(readJsonError(payload));
    }

    const tts = payload.tts || {};
    const goldTeacher = tts.gold_teacher || {};
    const voiceMatched = tts.voice_matched || {};
    const asr = payload.asr || {};
    const review = payload.review || {};
    const rewrite = payload.rewrite || {};

    els.recommendedOutput.textContent = tts.recommended_main_output || "gold_teacher";
    els.totalLatency.textContent = `${payload.total_latency_ms || 0} ms`;
    els.errorText.textContent = voiceMatched.error || goldTeacher.error || "无";
    els.asrText.textContent = asr.punc_text || asr.text || "-";
    els.reviewedText.textContent = review.asr_reviewed_text || "-";
    els.semanticText.textContent = rewrite.semantic_text || rewrite.dialect_text || "-";

    setAudioCard(
      els.goldAudio,
      els.goldDownload,
      els.goldNote,
      goldTeacher,
      "Gold Teacher 暂未生成。"
    );
    setAudioCard(
      els.matchedAudio,
      els.matchedDownload,
      els.matchedNote,
      voiceMatched,
      "Voice Matched 暂未生成。"
    );

    setStatus("处理完成。", "success");
  } catch (error) {
    const message = error instanceof Error ? error.message : "请求失败";
    els.errorText.textContent = message;
    setStatus(message, "error");
  } finally {
    els.submitBtn.disabled = false;
  }
}

els.submitBtn.addEventListener("click", submitPipeline);
