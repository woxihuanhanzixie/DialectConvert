const els = {
  form: document.getElementById("pipeline-form"),
  serviceStatus: document.getElementById("service-status"),
  inputAudio: document.getElementById("input-audio"),
  speakerRefAudio: document.getElementById("speaker-ref-audio"),
  inputText: document.getElementById("input-text"),
  targetDialect: document.getElementById("target-dialect"),
  voice: document.getElementById("voice"),
  submitBtn: document.getElementById("submit-btn"),
  statusText: document.getElementById("status-text"),
  recommendedOutput: document.getElementById("recommended-output"),
  totalLatency: document.getElementById("total-latency"),
  traceId: document.getElementById("trace-id"),
  errorText: document.getElementById("error-text"),
  clonedAudio: document.getElementById("cloned-audio"),
  clonedDownload: document.getElementById("cloned-download"),
  clonedNote: document.getElementById("cloned-note"),
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
  if (window.__APP_API_BASE__) return String(window.__APP_API_BASE__).replace(/\/$/, "");
  if (window.location.protocol === "file:") return "http://127.0.0.1:8002";
  if (["127.0.0.1", "localhost"].includes(window.location.hostname) && window.location.port && window.location.port !== "8002") {
    return "http://127.0.0.1:8002";
  }
  if (window.location.port && window.location.port !== "8002") {
    return `${window.location.protocol}//${window.location.hostname}:8002`;
  }
  return "";
})();

function setStatus(message, state) {
  els.statusText.textContent = message;
  els.statusText.className = `status ${state}`;
}

function resetOutputs() {
  els.recommendedOutput.textContent = "生成中";
  els.totalLatency.textContent = "-";
  els.traceId.textContent = "-";
  els.errorText.textContent = "无错误";
  els.clonedAudio.removeAttribute("src");
  els.clonedAudio.load();
  els.clonedDownload.classList.add("hidden");
  els.goldAudio.removeAttribute("src");
  els.goldAudio.load();
  els.goldDownload.classList.add("hidden");
  els.asrText.textContent = "-";
  els.reviewedText.textContent = "-";
  els.semanticText.textContent = "-";
  els.pronunciationText.textContent = "-";
  els.prosodyText.textContent = "-";
  els.culturalCards.textContent = "-";
  updateStats({});
}

async function checkHealth() {
  try {
    const resp = await fetch(`${API_BASE}/healthz`, { method: "GET" });
    if (!resp.ok) throw new Error("healthz failed");
    const payload = await resp.json();
    const runtime = payload.runtime || {};
    els.serviceStatus.textContent = `服务在线 · ${runtime.cosyvoice_target_model || payload.default_voice || "CosyVoice"}`;
    els.serviceStatus.className = "status-pill ok";
  } catch {
    els.serviceStatus.textContent = "服务未连接";
    els.serviceStatus.className = "status-pill bad";
  }
}

function readJsonError(payload) {
  if (!payload) return "请求失败";
  if (typeof payload.detail === "string") return payload.detail;
  if (payload.detail && typeof payload.detail === "object" && !Array.isArray(payload.detail)) {
    return payload.detail.message || payload.detail.error || JSON.stringify(payload.detail);
  }
  if (Array.isArray(payload.detail)) return payload.detail.map((item) => item.msg || JSON.stringify(item)).join("；");
  if (typeof payload.message === "string") return payload.message;
  return "请求失败";
}

function routeLabel(value) {
  const labels = {
    cosyvoice_realtime: "CosyVoice 实时方言语音",
    cosyvoice_fallback: "CosyVoice 非实时兜底音频",
    cloned_dialect: "CosyVoice 方言音频",
  };
  return labels[value] || value || "CosyVoice 实时方言语音";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
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

function hitCount(items) {
  if (!Array.isArray(items)) return 0;
  return items.reduce((total, item) => total + Math.max(1, Number(item?.count || 0) || 0), 0);
}

function updateStats(rewrite) {
  els.finalHitCount.textContent = Array.isArray(rewrite?.cultural_cards) ? rewrite.cultural_cards.length : 0;
  els.pronHitCount.textContent = hitCount(rewrite?.pronunciation_rule_hits);
  els.prosodyHitCount.textContent = hitCount(rewrite?.prosody_rule_hits);
  els.ragHitRate.textContent = "未启用";
  els.ragLatency.textContent = "-";
  els.ragSimilarity.textContent = "-";
}

function buildForm() {
  const mainAudio = els.inputAudio.files?.[0];
  const speakerRefAudio = els.speakerRefAudio.files?.[0];
  const inputText = els.inputText.value.trim();
  if (!mainAudio && !inputText) {
    throw new Error("请上传主音频或输入文本。");
  }
  const [targetDialect, dialectStyle] = els.targetDialect.value.split(":");
  const form = new FormData();
  if (mainAudio) form.append("file", mainAudio);
  if (speakerRefAudio) form.append("speaker_ref_audio", speakerRefAudio);
  if (inputText) form.append("text", inputText);
  form.append("enable_punc", "true");
  form.append("target_dialect", targetDialect);
  form.append("dialect_style", dialectStyle);
  form.append("voice_clone_enabled", speakerRefAudio ? "true" : "false");
  form.append("voice_clone_provider", "cosyvoice");
  return { form, mainAudio, speakerRefAudio };
}

function renderSession(session, mainAudio) {
  els.recommendedOutput.textContent = routeLabel("cosyvoice_realtime");
  els.traceId.textContent = session.trace_id || "-";
  els.asrText.textContent = session.asr?.punc_text || session.asr?.text || (mainAudio ? "-" : "文本输入，无 ASR");
  els.reviewedText.textContent = session.speech_text || "-";
  els.semanticText.textContent = session.speech_text || "-";
  els.pronunciationText.textContent = session.instruction || "-";
  els.prosodyText.textContent = "CosyVoice v3-flash 实时合成，不等待 LLM 韵律层。";
  els.culturalCards.textContent = "-";
  updateStats({});
  const warnings = Array.isArray(session.warnings) ? session.warnings : [];
  if (session.voice_source === "default_ref") {
    els.clonedNote.textContent = session.voice_cache_hit ? "已复用默认 CosyVoice 方言音色，正在实时播放。" : "已创建默认 CosyVoice 方言音色，正在实时播放。";
  } else if (session.voice_source === "system_fallback") {
    els.clonedNote.textContent = "默认方言音色不可用，已使用系统音色兜底，口音可能偏普通话。";
  } else if (warnings.some((item) => String(item).includes("voice_enrollment_fallback"))) {
    els.clonedNote.textContent = "参考音频暂未复刻成功，已自动使用系统音色继续生成。";
  } else {
    els.clonedNote.textContent = session.voice_cache_hit ? "已复用 CosyVoice 专属音色，正在实时播放。" : "CosyVoice v3-flash 正在实时播放。";
  }
  els.goldNote.textContent = "当前公网主链路不再使用 Gold Teacher。";
}

function websocketUrl(url) {
  if (url) return url;
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const base = API_BASE || `${window.location.protocol}//${window.location.host}`;
  return base.replace(/^https?:/, proto);
}

async function playRealtime(session) {
  const mediaSourceCtor = window.MediaSource || window.WebKitMediaSource;
  const supportsMseMp3 = Boolean(
    mediaSourceCtor &&
      typeof mediaSourceCtor.isTypeSupported === "function" &&
      mediaSourceCtor.isTypeSupported("audio/mpeg")
  );
  if (!supportsMseMp3) {
    return playRealtimeAsBlob(session);
  }
  const mediaSource = new mediaSourceCtor();
  const chunks = [];
  let sourceBuffer = null;
  let opened = false;
  let finished = false;
  const startedAt = performance.now();
  const objectUrl = URL.createObjectURL(mediaSource);
  els.clonedAudio.src = objectUrl;
  els.clonedAudio.play().catch(() => {});

  function pump() {
    if (!sourceBuffer || sourceBuffer.updating || chunks.length === 0) return;
    sourceBuffer.appendBuffer(chunks.shift());
  }

  mediaSource.addEventListener("sourceopen", () => {
    opened = true;
    sourceBuffer = mediaSource.addSourceBuffer("audio/mpeg");
    sourceBuffer.addEventListener("updateend", () => {
      pump();
      if (finished && chunks.length === 0 && !sourceBuffer.updating && mediaSource.readyState === "open") {
        mediaSource.endOfStream();
      }
    });
    pump();
  });

  const streamUrl = websocketUrl(session.stream_url);
  const ws = new WebSocket(streamUrl);
  ws.binaryType = "arraybuffer";

  await new Promise((resolve, reject) => {
    ws.onopen = () => setStatus("CosyVoice 已连接，等待首个音频片段...", "loading");
    ws.onerror = () => reject(new Error("实时 WebSocket 连接失败。"));
    ws.onmessage = (event) => {
      if (typeof event.data === "string") {
        let payload = {};
        try {
          payload = JSON.parse(event.data);
        } catch {
          payload = { type: "message", message: event.data };
        }
        if (payload.type === "error") {
          reject(new Error(payload.message || "实时合成失败。"));
        }
        if (payload.type === "done") {
          finished = true;
          els.totalLatency.textContent = `${Math.round(performance.now() - startedAt)} ms`;
          setStatus("实时播放完成。", "success");
          resolve();
        }
        return;
      }
      chunks.push(event.data);
      if (opened) pump();
      if (els.clonedAudio.paused) els.clonedAudio.play().catch(() => {});
      setStatus("正在实时播放 CosyVoice 方言语音...", "loading");
    };
    ws.onclose = () => {
      finished = true;
      if (!sourceBuffer && chunks.length === 0) reject(new Error("实时连接关闭，未收到音频。"));
    };
  });
}

async function playRealtimeAsBlob(session) {
  const chunks = [];
  const startedAt = performance.now();
  const streamUrl = websocketUrl(session.stream_url);
  const ws = new WebSocket(streamUrl);
  ws.binaryType = "arraybuffer";

  await new Promise((resolve, reject) => {
    ws.onopen = () => setStatus("手机浏览器不支持边下边播，正在接收音频...", "loading");
    ws.onerror = () => reject(new Error("实时 WebSocket 连接失败。"));
    ws.onmessage = (event) => {
      if (typeof event.data === "string") {
        let payload = {};
        try {
          payload = JSON.parse(event.data);
        } catch {
          payload = { type: "message", message: event.data };
        }
        if (payload.type === "error") {
          reject(new Error(payload.message || "实时合成失败。"));
          return;
        }
        if (payload.type === "done") {
          const blob = new Blob(chunks, { type: "audio/mpeg" });
          const objectUrl = URL.createObjectURL(blob);
          els.clonedAudio.src = objectUrl;
          els.clonedDownload.href = objectUrl;
          els.clonedDownload.classList.remove("hidden");
          els.clonedAudio.play().catch(() => {});
          els.totalLatency.textContent = `${Math.round(performance.now() - startedAt)} ms`;
          setStatus("音频已生成，手机端可直接播放。", "success");
          resolve();
        }
        return;
      }
      chunks.push(event.data);
      setStatus("正在接收 CosyVoice 方言语音...", "loading");
    };
    ws.onclose = () => {
      if (chunks.length === 0) reject(new Error("实时连接关闭，未收到音频。"));
    };
  });
}

async function runFallbackPipeline(form) {
  setStatus("实时播放不可用，正在生成非实时兜底音频...", "loading");
  form.set("enable_rewrite", "false");
  form.set("enable_tts", "true");
  form.set("segment_max_len", "28");
  const resp = await fetch(`${API_BASE}/api/v1/dialect/pipeline`, { method: "POST", body: form });
  const payload = await resp.json();
  if (!resp.ok) throw new Error(readJsonError(payload));
  const tts = payload.tts || {};
  const route = tts.cosyvoice_fallback || tts.cloned_dialect || tts.voice_matched || {};
  const audioUrl = route.audio_url || tts.audio_url || "";
  if (!audioUrl) throw new Error(route.error || tts.error || "非实时兜底音频未生成。");
  els.clonedAudio.src = audioUrl;
  els.clonedDownload.href = audioUrl;
  els.clonedDownload.classList.remove("hidden");
  els.clonedNote.textContent = route.route_reason || "已生成 CosyVoice 非实时兜底音频。";
  els.recommendedOutput.textContent = routeLabel(tts.recommended_main_output || "cosyvoice_fallback");
  els.totalLatency.textContent = `${Math.round(payload.total_latency_ms || 0)} ms`;
  els.traceId.textContent = payload.trace_id || els.traceId.textContent;
  setStatus("非实时兜底音频已生成。", "success");
}

async function submitPipeline(event) {
  event.preventDefault();
  const startedAt = performance.now();
  let built;
  try {
    built = buildForm();
  } catch (error) {
    setStatus(error.message, "error");
    return;
  }
  els.submitBtn.disabled = true;
  resetOutputs();
  setStatus("正在准备 CosyVoice 实时会话...", "loading");

  try {
    const resp = await fetch(`${API_BASE}/api/v1/dialect/realtime-session`, {
      method: "POST",
      body: built.form,
    });
    const session = await resp.json();
    if (!resp.ok) throw new Error(readJsonError(session));
    renderSession(session, built.mainAudio);
    await playRealtime(session);
    els.totalLatency.textContent = `${Math.round(performance.now() - startedAt)} ms`;
  } catch (error) {
    const message = error instanceof Error ? error.message : "实时链路失败。";
    els.errorText.textContent = message;
    try {
      await runFallbackPipeline(built.form);
    } catch (fallbackError) {
      const fallbackMessage = fallbackError instanceof Error ? fallbackError.message : "请求失败";
      els.errorText.textContent = `${message} ${fallbackMessage}`;
      setStatus(fallbackMessage, "error");
    }
  } finally {
    els.submitBtn.disabled = false;
  }
}

function initRecording() {
  const recordBtn = document.getElementById("record-btn");
  const recordBtnText = document.getElementById("record-btn-text");
  if (!recordBtn || !navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
    if (recordBtn) recordBtn.disabled = true;
    return;
  }

  let mediaRecorder = null;
  let chunks = [];
  let stream = null;

  function setRecordingState(isRecording) {
    recordBtn.classList.toggle("recording", isRecording);
    if (recordBtnText) recordBtnText.textContent = isRecording ? "停止" : "录制";
  }

  recordBtn.addEventListener("click", async () => {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
      return;
    }

    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunks = [];
      const preferredType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "audio/webm";
      mediaRecorder = new MediaRecorder(stream, { mimeType: preferredType });
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      mediaRecorder.onstop = () => {
        stream?.getTracks().forEach((track) => track.stop());
        setRecordingState(false);
        if (!chunks.length) return;
        const blob = new Blob(chunks, { type: preferredType });
        const file = new File([blob], "recording.webm", { type: preferredType });
        const transfer = new DataTransfer();
        transfer.items.add(file);
        els.inputAudio.files = transfer.files;
        setStatus("已录制音频，可提交转换。", "success");
      };
      mediaRecorder.start();
      setRecordingState(true);
      setStatus("录音中...", "loading");
    } catch {
      stream?.getTracks().forEach((track) => track.stop());
      setRecordingState(false);
      setStatus("无法访问麦克风，请检查权限。", "error");
    }
  });
}

initRecording();
els.form.addEventListener("submit", submitPipeline);
checkHealth();
