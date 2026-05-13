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
  asrText: document.getElementById("asr-text"),
  reviewedText: document.getElementById("reviewed-text"),
  semanticText: document.getElementById("semantic-text"),
  pronunciationText: document.getElementById("pronunciation-text"),
  prosodyText: document.getElementById("prosody-text"),
  culturalCards: document.getElementById("cultural-cards"),
  finalHitCount: document.getElementById("final-hit-count"),
  pronHitCount: document.getElementById("pron-hit-count"),
  prosodyHitCount: document.getElementById("prosody-hit-count"),
  ragHitRate: document.getElementById("rag-hit-rate"),
  ragLatency: document.getElementById("rag-latency"),
  ragSimilarity: document.getElementById("rag-similarity"),
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
    voice_matched: "Gold Teacher",
    baseline: "Gold Teacher",
    clone: "Gold Teacher",
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
      const meaning = card.meaning || "暂无词义";
      const example = card.usage_example || "暂无例句";
      const register = card.register || "口语";
      const source = card.source_label || "资料整理";
      return `
        <button class="culture-chip" type="button" aria-label="${escapeHtml(title)}">
          ${escapeHtml(title)}
          <span class="culture-popover" role="tooltip">
            <strong>${escapeHtml(title)}</strong>
            <em>${escapeHtml(register)}</em>
            <span>词义：${escapeHtml(meaning)}</span>
            <span>文化说明：${escapeHtml(note || "暂无说明")}</span>
            <span>例句：${escapeHtml(example)}</span>
            <small>${escapeHtml(source)}</small>
          </span>
        </button>
      `;
    })
    .join("");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function hitCount(items) {
  if (!Array.isArray(items)) return 0;
  return items.reduce((total, item) => total + Math.max(1, Number(item?.count || 0) || 0), 0);
}

function pickFirstNumber(...values) {
  for (const value of values) {
    if (value === null || value === undefined || value === "") continue;
    const numeric = Number(value);
    if (Number.isFinite(numeric)) return numeric;
  }
  return null;
}

function ragHits(rewrite) {
  const hits = [];
  for (const key of ["rag_hits", "pronunciation_rag_hits"]) {
    if (Array.isArray(rewrite?.[key])) hits.push(...rewrite[key]);
  }
  return hits;
}

function formatPercent(value) {
  if (!Number.isFinite(value)) return "-";
  const normalized = value <= 1 ? value * 100 : value;
  return `${normalized.toFixed(normalized >= 10 ? 1 : 2)}%`;
}

function formatMs(value) {
  if (!Number.isFinite(value)) return "-";
  return `${Math.round(value)} ms`;
}

function updateStats(rewrite) {
  const pronCount = hitCount(rewrite?.pronunciation_rule_hits);
  const prosodyCount = hitCount(rewrite?.prosody_rule_hits);
  const hits = ragHits(rewrite || {});
  const ragCount = hits.length;
  const queryCount = pickFirstNumber(
    rewrite?.rag_query_count,
    rewrite?.pronunciation_rag_query_count,
    rewrite?.rag_total
  );
  const explicitRate = pickFirstNumber(
    rewrite?.rag_hit_rate,
    rewrite?.pronunciation_rag_hit_rate,
    rewrite?.rag_recall_rate
  );
  const latency = pickFirstNumber(rewrite?.rag_latency_ms, rewrite?.pronunciation_rag_latency_ms, rewrite?.rag_elapsed_ms);
  let similarity = pickFirstNumber(rewrite?.rag_semantic_similarity, rewrite?.rag_avg_similarity, rewrite?.rag_top_score);
  if (similarity === null) {
    const scores = hits
      .map((hit) => pickFirstNumber(hit?.semantic_similarity, hit?.similarity, hit?.score))
      .filter((value) => value !== null);
    if (scores.length) similarity = Math.max(...scores);
  }

  els.pronHitCount.textContent = String(pronCount);
  els.prosodyHitCount.textContent = String(prosodyCount);
  els.finalHitCount.textContent = String(pronCount + prosodyCount + ragCount);
  if (explicitRate !== null) {
    els.ragHitRate.textContent = formatPercent(explicitRate);
  } else if (queryCount !== null && queryCount > 0) {
    els.ragHitRate.textContent = formatPercent(ragCount / queryCount);
  } else {
    els.ragHitRate.textContent = ragCount > 0 ? "已命中" : "未启用";
  }
  els.ragLatency.textContent = formatMs(latency);
  els.ragSimilarity.textContent = similarity === null ? "-" : formatPercent(similarity);
}

function resetOutputs() {
  els.recommendedOutput.textContent = "生成中";
  els.totalLatency.textContent = "-";
  els.traceId.textContent = "-";
  els.errorText.textContent = "无错误";
  updateStats({});
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
    const asr = payload.asr || {};
    const review = payload.review || {};
    const rewrite = payload.rewrite || {};

    els.recommendedOutput.textContent = routeLabel(tts.recommended_main_output);
    els.totalLatency.textContent = `${Math.round(payload.total_latency_ms || 0)} ms`;
    els.traceId.textContent = payload.trace_id || "-";
    els.errorText.textContent = goldTeacher.error || "无错误";
    els.asrText.textContent = asr.punc_text || asr.text || (mainAudio ? "-" : "文本输入，无 ASR");
    els.reviewedText.textContent = review.asr_reviewed_text || "-";
    els.semanticText.textContent = rewrite.semantic_text || rewrite.dialect_text || "-";
    els.pronunciationText.textContent = rewrite.pronunciation_text || "-";
    els.prosodyText.textContent = rewrite.prosody_text || "-";
    els.culturalCards.innerHTML = renderCulturalCards(rewrite.cultural_cards);
    updateStats(rewrite);

    setAudioCard(els.goldAudio, els.goldDownload, els.goldNote, goldTeacher, "Gold Teacher 暂未生成。");
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
