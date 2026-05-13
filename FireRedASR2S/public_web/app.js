const els = {
  form: document.getElementById("pipeline-form"),
  serviceStatus: document.getElementById("service-status"),
  inputAudio: document.getElementById("input-audio"),
  inputText: document.getElementById("input-text"),
  targetDialect: document.getElementById("target-dialect"),
  voice: document.getElementById("voice"),
  submitBtn: document.getElementById("submit-btn"),
  statusText: document.getElementById("status-text"),
  recommendedOutput: document.getElementById("recommended-output"),
  totalLatency: document.getElementById("total-latency"),
  traceId: document.getElementById("trace-id"),
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
  pronunciationText: document.getElementById("pronunciation-text"),
  prosodyText: document.getElementById("prosody-text"),
  culturalCards: document.getElementById("cultural-cards"),
};

const API_BASE = (() => {
  if (window.__APP_API_BASE__) {
    return String(window.__APP_API_BASE__).replace(/\/$/, "");
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

function routeLabel(value) {
  const labels = {
    gold_teacher: "Gold Teacher",
    voice_matched: "Voice Matched",
    baseline: "Gold Teacher",
    clone: "Voice Matched",
  };
  return labels[value] || value || "Gold Teacher";
}

function setAudioCard(audioEl, linkEl, noteEl, route, emptyMessage) {
  const audioUrl = route?.audio_url || "";
  if (audioUrl) {
    audioEl.src = audioUrl;
    linkEl.href = audioUrl;
    linkEl.classList.remove("hidden");
    noteEl.textContent = route?.route_reason || "已生成。";
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
  if (Array.isArray(payload.detail)) {
    return payload.detail.map((item) => item.msg || JSON.stringify(item)).join("；");
  }
  return "请求失败";
}

function renderCulturalCards(cards) {
  if (!Array.isArray(cards) || cards.length === 0) return "-";
  return cards
    .map((card) => {
      const title = card.term || card.id || "方言词";
      const note = card.cultural_note || card.meaning || "";
      const example = card.usage_example ? `例：${card.usage_example}` : "";
      return [title, note, example].filter(Boolean).join("\n");
    })
    .join("\n\n");
}

function resetOutputs() {
  els.recommendedOutput.textContent = "生成中";
  els.totalLatency.textContent = "-";
  els.traceId.textContent = "-";
  els.errorText.textContent = "无错误";
}

async function checkHealth() {
  try {
    const resp = await fetch(`${API_BASE}/healthz`, { method: "GET" });
    if (!resp.ok) throw new Error("healthz failed");
    const payload = await resp.json();
    els.serviceStatus.textContent = `服务在线 · ${payload.default_voice || "Kiki"}`;
    els.serviceStatus.className = "status-pill ok";
  } catch {
    els.serviceStatus.textContent = "服务未连接";
    els.serviceStatus.className = "status-pill bad";
  }
}

async function submitPipeline(event) {
  event.preventDefault();
  const mainAudio = els.inputAudio.files?.[0];
  const inputText = els.inputText.value.trim();
  if (!mainAudio && !inputText) {
    setStatus("请上传主音频或输入文本。", "error");
    return;
  }

  const [targetDialect, dialectStyle] = els.targetDialect.value.split(":");
  const form = new FormData();
  if (mainAudio) form.append("file", mainAudio);
  if (inputText) form.append("text", inputText);
  form.append("enable_punc", "true");
  form.append("enable_rewrite", "true");
  form.append("enable_tts", "true");
  form.append("segment_max_len", "28");
  form.append("voice", els.voice.value);
  form.append("target_dialect", targetDialect);
  form.append("dialect_style", dialectStyle);
  form.append("voice_clone_enabled", "false");
  form.append("voice_clone_provider", "none");

  els.submitBtn.disabled = true;
  resetOutputs();
  setStatus("正在生成 Gold Teacher...", "loading");

  try {
    const resp = await fetch(`${API_BASE}/api/v1/dialect/pipeline`, {
      method: "POST",
      body: form,
    });
    const payload = await resp.json();
    if (!resp.ok) throw new Error(readJsonError(payload));

    const tts = payload.tts || {};
    const goldTeacher = tts.gold_teacher || {};
    const voiceMatched = tts.voice_matched || {};
    const asr = payload.asr || {};
    const review = payload.review || {};
    const rewrite = payload.rewrite || {};

    els.recommendedOutput.textContent = routeLabel(tts.recommended_main_output);
    els.totalLatency.textContent = `${Math.round(payload.total_latency_ms || 0)} ms`;
    els.traceId.textContent = payload.trace_id || "-";
    els.errorText.textContent = voiceMatched.error || goldTeacher.error || "无错误";
    els.asrText.textContent = asr.punc_text || asr.text || (mainAudio ? "-" : "文本输入，无 ASR");
    els.reviewedText.textContent = review.asr_reviewed_text || "-";
    els.semanticText.textContent = rewrite.semantic_text || rewrite.dialect_text || "-";
    els.pronunciationText.textContent = rewrite.pronunciation_text || "-";
    els.prosodyText.textContent = rewrite.prosody_text || "-";
    els.culturalCards.textContent = renderCulturalCards(rewrite.cultural_cards);

    setAudioCard(els.goldAudio, els.goldDownload, els.goldNote, goldTeacher, "Gold Teacher 暂未生成。");
    setAudioCard(els.matchedAudio, els.matchedDownload, els.matchedNote, voiceMatched, "公网稳定版默认关闭。");
    setStatus("处理完成。", "success");
  } catch (error) {
    const message = error instanceof Error ? error.message : "请求失败";
    els.errorText.textContent = message;
    setStatus(message, "error");
  } finally {
    els.submitBtn.disabled = false;
  }
}

els.form.addEventListener("submit", submitPipeline);
checkHealth();
