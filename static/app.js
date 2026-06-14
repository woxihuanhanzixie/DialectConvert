const form = document.querySelector("#convertForm");
const fileInput = document.querySelector("#audioInput");
const recordInput = document.querySelector("#recordInput");
const preview = document.querySelector("#preview");
const result = document.querySelector("#result");
const submitBtn = document.querySelector("#submitBtn");
const recordBtn = document.querySelector("#recordBtn");
const stopBtn = document.querySelector("#stopBtn");
const clearBtn = document.querySelector("#clearBtn");
const deleteAudioBtn = document.querySelector("#deleteAudioBtn");
const recordState = document.querySelector("#recordState");
const recordTimer = document.querySelector("#recordTimer");
const audioChip = document.querySelector("#audioChip");
const audioName = document.querySelector("#audioName");
const audioMeta = document.querySelector("#audioMeta");
const serviceState = document.querySelector("#serviceState");
const waveCanvas = document.querySelector("#waveCanvas");
const waveWrap = document.querySelector("#waveWrap");
const liveLabel = document.querySelector("#liveLabel");
const steps = [...document.querySelectorAll("#steps li")];
const voiceModal = document.querySelector("#voiceModal");
const voiceModalClose = document.querySelector("#voiceModalClose");
const voiceTextInput = document.querySelector("#voiceTextInput");
const voiceSpeakBtn = document.querySelector("#voiceSpeakBtn");
const voiceModalOutput = document.querySelector("#voiceModalOutput");
const voiceMascot = document.querySelector("#voiceMascot");
const DEFAULT_MIN_AUDIO_SECONDS = 10;
const DEFAULT_MAX_AUDIO_SECONDS = 20;

const ctx = waveCanvas.getContext("2d");
const state = {
  recorder: null,
  chunks: [],
  stream: null,
  audioContext: null,
  analyser: null,
  animationId: null,
  startedAt: 0,
  timerId: null,
  selectedFile: null,
  selectedDurationS: null,
  selectedObjectUrl: "",
  demoPulse: 0,
  pointerRecording: false,
  pointerStartY: 0,
  cancelOnStop: false,
  ignoreNextClick: false,
  nativeCaptureActive: false,
  lastDrawAt: 0,
  audioLimits: {
    minSeconds: DEFAULT_MIN_AUDIO_SECONDS,
    maxSeconds: DEFAULT_MAX_AUDIO_SECONDS,
  },
  registeredVoice: null,
  previewRequestId: 0,
  mascotDrag: null,
  mascotMoved: false,
};

const dialectNames = {
  cantonese: "粤语",
  sichuanese: "四川话",
  hokkien: "闽南话",
};

const recorderTypes = [
  { mimeType: "audio/mp4;codecs=mp4a.40.2", ext: "m4a" },
  { mimeType: "audio/mp4", ext: "m4a" },
  { mimeType: "audio/webm;codecs=opus", ext: "webm" },
  { mimeType: "audio/webm", ext: "webm" },
  { mimeType: "audio/ogg;codecs=opus", ext: "ogg" },
  { mimeType: "audio/wav", ext: "wav" },
];

function getRecorderFormat() {
  if (!window.MediaRecorder) return null;
  const match = recorderTypes.find((item) => MediaRecorder.isTypeSupported(item.mimeType));
  return match || { mimeType: "", ext: "webm" };
}

function supportsLiveMicrophone() {
  return Boolean(
    window.isSecureContext &&
      navigator.mediaDevices &&
      typeof navigator.mediaDevices.getUserMedia === "function" &&
      window.MediaRecorder &&
      getRecorderFormat()
  );
}

function isLikelyMobile() {
  return /Android|iPhone|iPad|iPod|Mobile|HarmonyOS|HongMeng/i.test(navigator.userAgent);
}

function isLikelyIOS() {
  return /iPhone|iPad|iPod/i.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function configureNativeRecorderInput() {
  if (isLikelyIOS()) {
    recordInput.removeAttribute("capture");
    recordInput.setAttribute("accept", "audio/*,.m4a,.mp4,.caf,.wav,.mp3");
  } else {
    recordInput.setAttribute("capture", "microphone");
    recordInput.setAttribute("accept", "audio/*,.m4a,.mp4,.3gp,.3gpp,.caf,.amr,.wav,.mp3");
  }
}

function formatTime(ms) {
  const total = Math.max(0, Math.floor(ms / 1000));
  const minutes = String(Math.floor(total / 60)).padStart(2, "0");
  const seconds = String(total % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return "时长读取中";
  return `${formatTime(seconds * 1000)} 时长`;
}

function formatSize(bytes) {
  if (!bytes) return "0 KB";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDisplayStamp(date = new Date()) {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");
  return `${month}-${day} ${hour}:${minute}`;
}

function displayAudioName(source) {
  const label = source === "capture" ? "手机录音" : source === "live" ? "网页录音" : "上传音频";
  return `${formatDisplayStamp()} ${label}数据`;
}

function minAudioSeconds() {
  return state.audioLimits.minSeconds || DEFAULT_MIN_AUDIO_SECONDS;
}

function maxAudioSeconds() {
  return state.audioLimits.maxSeconds || DEFAULT_MAX_AUDIO_SECONDS;
}

async function fetchAudioLimits() {
  try {
    const response = await fetch("/api/audio-limits", { cache: "no-store" });
    if (!response.ok) return;
    const data = await response.json();
    const minSeconds = Number(data.min_seconds);
    const maxSeconds = Number(data.max_seconds);
    if (Number.isFinite(minSeconds) && minSeconds > 0) state.audioLimits.minSeconds = minSeconds;
    if (Number.isFinite(maxSeconds) && maxSeconds > minAudioSeconds()) state.audioLimits.maxSeconds = maxSeconds;
  } catch (error) {
    return;
  }
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setStep(activeIndex) {
  steps.forEach((step, index) => {
    step.classList.toggle("is-active", index === activeIndex);
    step.classList.toggle("is-done", index < activeIndex);
  });
}

function resetSteps() {
  steps.forEach((step) => step.classList.remove("is-active", "is-done"));
}

function drawIdleWave() {
  const now = performance.now();
  if (now - state.lastDrawAt < 80) {
    state.animationId = requestAnimationFrame(drawIdleWave);
    return;
  }
  state.lastDrawAt = now;
  const width = waveCanvas.width;
  const height = waveCanvas.height;
  state.demoPulse += 0.018;
  ctx.clearRect(0, 0, width, height);
  const gradient = ctx.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, "#0b1320");
  gradient.addColorStop(0.62, "#12324f");
  gradient.addColorStop(1, "#8fd3ff");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);

  const glow = ctx.createRadialGradient(width * 0.7, height * 0.92, 16, width * 0.7, height * 0.92, height * 0.78);
  glow.addColorStop(0, "rgba(236, 253, 245, 0.78)");
  glow.addColorStop(0.34, "rgba(125, 211, 252, 0.28)");
  glow.addColorStop(1, "rgba(101, 153, 220, 0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = "rgba(190, 242, 255, 0.28)";
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  for (let x = 0; x <= width; x += 10) {
    const y = height * 0.62 + Math.sin(x * 0.018 + state.demoPulse) * 8 + Math.sin(x * 0.043) * 3;
    if (x === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
  state.animationId = requestAnimationFrame(drawIdleWave);
}

function drawLiveWave() {
  const now = performance.now();
  if (now - state.lastDrawAt < 33) {
    state.animationId = requestAnimationFrame(drawLiveWave);
    return;
  }
  state.lastDrawAt = now;
  const width = waveCanvas.width;
  const height = waveCanvas.height;
  ctx.clearRect(0, 0, width, height);
  const gradient = ctx.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, "#071019");
  gradient.addColorStop(0.58, "#0c6ff6");
  gradient.addColorStop(1, "#62d6ff");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);

  const bars = window.innerWidth <= 520 ? 34 : 46;
  const centerY = height * 0.66;
  ctx.lineCap = "round";
  ctx.strokeStyle = "rgba(255, 255, 255, 0.92)";
  ctx.lineWidth = Math.max(4, width / 180);

  let levels = null;
  if (state.analyser) {
    levels = new Uint8Array(state.analyser.frequencyBinCount);
    state.analyser.getByteTimeDomainData(levels);
  }
  for (let i = 0; i < bars; i++) {
    const x = width * 0.16 + (width * 0.68 * i) / (bars - 1);
    const sample = levels ? Math.abs((levels[Math.floor((i / bars) * levels.length)] || 128) - 128) / 128 : 0.4;
    const idle = 0.55 + Math.sin(state.demoPulse * 8 + i * 0.72) * 0.32;
    const amp = Math.max(sample, idle * 0.24);
    const h = 12 + amp * 68;
    ctx.globalAlpha = 0.38 + amp * 0.62;
    ctx.beginPath();
    ctx.moveTo(x, centerY - h / 2);
    ctx.lineTo(x, centerY + h / 2);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
  state.demoPulse += 0.02;
  state.animationId = requestAnimationFrame(drawLiveWave);
}

function stopDrawing() {
  if (state.animationId) cancelAnimationFrame(state.animationId);
  state.animationId = null;
  state.lastDrawAt = 0;
}

function startTimer() {
  state.startedAt = Date.now();
  recordTimer.textContent = "00:00";
  state.timerId = window.setInterval(() => {
    recordTimer.textContent = formatTime(Date.now() - state.startedAt);
  }, 250);
}

function stopTimer() {
  if (state.timerId) clearInterval(state.timerId);
  state.timerId = null;
}

function renderMessage(message, level = "empty") {
  if (level === "loading") {
    result.innerHTML = `
      <div class="empty-state is-loading">
        <div class="skeleton-spinner"></div>
        <p>${escapeHtml(message)}</p>
        <span>请在生成过程中保持页面打开</span>
      </div>`;
    return;
  }
  result.innerHTML = `<div class="${level === "warn" ? "warn-card" : "empty-state"}"><p>${escapeHtml(message)}</p></div>`;
}

function setRecordingUi(message = "正在录音，松开发送，上滑取消") {
  stopDrawing();
  drawLiveWave();
  startTimer();
  recordBtn.disabled = false;
  stopBtn.disabled = false;
  waveWrap.classList.add("is-recording");
  recordState.textContent = message;
  serviceState.textContent = "Recording";
  liveLabel.textContent = "Recording";
}

function resetRecordingUi() {
  stopTimer();
  stopDrawing();
  recordBtn.disabled = false;
  stopBtn.disabled = true;
  waveWrap.classList.remove("is-recording", "is-canceling");
  liveLabel.textContent = "Live";
  drawIdleWave();
}

function serverBusyMessage() {
  return "服务器繁忙，请稍后再试";
}

function makePreviewUrl(file) {
  if (state.selectedObjectUrl) URL.revokeObjectURL(state.selectedObjectUrl);
  state.selectedObjectUrl = URL.createObjectURL(file);
  return state.selectedObjectUrl;
}

function updateAudioMeta(file, durationS = state.selectedDurationS) {
  const parts = [formatSize(file.size)];
  if (Number.isFinite(durationS)) parts.push(formatDuration(durationS));
  else parts.push("正在读取时长");
  parts.push("已准备生成");
  audioMeta.textContent = parts.join(" · ");
}

function setAudioMetaStatus(file, status) {
  audioMeta.textContent = `${formatSize(file.size)} · ${status}`;
}

function readDurationFromAudioElement(audioEl, timeoutMs = 2600) {
  return new Promise((resolve) => {
    let settled = false;
    const done = (value) => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve(Number.isFinite(value) && value > 0 ? value : null);
    };
    const cleanup = () => {
      window.clearTimeout(timer);
      audioEl.removeEventListener("loadedmetadata", onMetadata);
      audioEl.removeEventListener("durationchange", onMetadata);
      audioEl.removeEventListener("error", onError);
    };
    const onMetadata = () => done(audioEl.duration);
    const onError = () => done(null);
    const timer = window.setTimeout(() => done(null), timeoutMs);
    if (Number.isFinite(audioEl.duration) && audioEl.duration > 0) {
      done(audioEl.duration);
      return;
    }
    audioEl.addEventListener("loadedmetadata", onMetadata);
    audioEl.addEventListener("durationchange", onMetadata);
    audioEl.addEventListener("error", onError);
  });
}

async function readFileDuration(file, timeoutMs = 2600) {
  if (!file) return null;
  const audioEl = document.createElement("audio");
  const url = URL.createObjectURL(file);
  audioEl.preload = "metadata";
  audioEl.src = url;
  try {
    audioEl.load();
    return await readDurationFromAudioElement(audioEl, timeoutMs);
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function refreshPreviewDuration(file) {
  const duration = await readDurationFromAudioElement(preview);
  if (state.selectedFile !== file) return;
  if (!Number.isFinite(duration)) {
    await hydrateServerPreview(file);
    return;
  }
  state.selectedDurationS = duration;
  updateAudioMeta(file, duration);
  if (Number.isFinite(duration)) {
    recordTimer.textContent = formatTime(duration * 1000);
  }
}

async function hydrateServerPreview(file) {
  const requestId = ++state.previewRequestId;
  setAudioMetaStatus(file, "正在生成可播放预览");
  try {
    const body = new FormData();
    body.append("audio", file, file.name || `audio-${Date.now()}.m4a`);
    const response = await fetch("/api/preview-audio", { method: "POST", body });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "预览生成失败");
    if (requestId !== state.previewRequestId || state.selectedFile !== file) return;
    if (data.audio_url) {
      preview.src = data.audio_url;
      preview.load();
    }
    const duration = Number(data.duration_s);
    state.selectedDurationS = Number.isFinite(duration) && duration > 0 ? duration : null;
    updateAudioMeta(file, state.selectedDurationS);
    if (state.selectedDurationS) recordTimer.textContent = formatTime(state.selectedDurationS * 1000);
  } catch (error) {
    if (requestId !== state.previewRequestId || state.selectedFile !== file) return;
    state.selectedDurationS = null;
    setAudioMetaStatus(file, "预览不可播放，可继续生成");
  }
}

function setPreview(file, source = "upload") {
  if (!file) return;
  state.selectedFile = file;
  state.selectedDurationS = null;
  preview.src = makePreviewUrl(file);
  preview.load();
  const label = source === "capture" ? "手机录音" : source === "live" ? "网页录音" : "已选择音频";
  audioName.textContent = displayAudioName(source);
  updateAudioMeta(file, null);
  audioChip.hidden = false;
  recordState.textContent = `${label}已就绪，可以生成方言复刻语音`;
  serviceState.textContent = "Audio ready";
  liveLabel.textContent = "Ready";
  waveWrap.classList.add("has-audio");
  refreshPreviewDuration(file);
}

function setInputFiles(file) {
  if (!file || !window.DataTransfer) return;
  const transfer = new DataTransfer();
  transfer.items.add(file);
  fileInput.files = transfer.files;
}

function clearAudio() {
  fileInput.value = "";
  recordInput.value = "";
  state.selectedFile = null;
  state.selectedDurationS = null;
  state.previewRequestId += 1;
  if (state.selectedObjectUrl) URL.revokeObjectURL(state.selectedObjectUrl);
  state.selectedObjectUrl = "";
  preview.removeAttribute("src");
  preview.load();
  audioChip.hidden = true;
  recordTimer.textContent = "00:00";
  recordState.textContent = isLikelyMobile() ? "按住录音，或点加号调用手机录音器" : "点击录音，或上传一段参考音频";
  serviceState.textContent = "Ready";
  liveLabel.textContent = "Live";
  waveWrap.classList.remove("is-recording", "is-canceling", "has-audio");
  resetSteps();
}

function openNativeRecorder(reason = "") {
  stopTimer();
  stopDrawing();
  drawIdleWave();
  recordTimer.textContent = "00:00";
  recordState.textContent = isLikelyIOS()
    ? "请选择语音备忘录或音频文件"
    : "正在打开系统录音器，录完返回后会自动载入音频";
  serviceState.textContent = "Choose audio";
  liveLabel.textContent = "Audio input";
  waveWrap.classList.remove("is-recording", "is-canceling");
  state.nativeCaptureActive = true;
  const handleReturn = () => {
    window.setTimeout(() => {
      if (!state.nativeCaptureActive) return;
      if (!recordInput.files || !recordInput.files[0]) {
        state.nativeCaptureActive = false;
        finishNativeRecorderUi();
        recordState.textContent = "没有选择录音文件，可以重新录制";
      }
    }, 700);
  };
  window.addEventListener("focus", handleReturn, { once: true });
  window.addEventListener("pageshow", handleReturn, { once: true });
  if (reason) renderMessage(reason, "warn");
  recordInput.click();
}

function finishNativeRecorderUi() {
  resetRecordingUi();
}

async function startRecording() {
  if (state.recorder && state.recorder.state === "recording") return;
  if (!supportsLiveMicrophone()) {
    const reason = isLikelyIOS()
      ? "当前 HTTP 页面无法在 iOS 上直接调用网页麦克风。请选择语音备忘录里的音频；绑定 HTTPS 后可使用网页内录音。"
      : window.isSecureContext
      ? "当前浏览器不支持网页内录音，已切换到手机系统录音器。"
      : "当前页面不是 HTTPS，手机浏览器会禁止网页直接访问麦克风，已切换到手机系统录音器。";
    openNativeRecorder(reason);
    return;
  }

  try {
    const format = getRecorderFormat();
    state.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,
      },
    });
    state.chunks = [];
    state.recorder = new MediaRecorder(state.stream, format.mimeType ? { mimeType: format.mimeType } : undefined);
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (AudioContextClass) {
      state.audioContext = new AudioContextClass();
      const source = state.audioContext.createMediaStreamSource(state.stream);
      state.analyser = state.audioContext.createAnalyser();
      state.analyser.fftSize = 2048;
      source.connect(state.analyser);
    }

    state.recorder.ondataavailable = (event) => {
      if (event.data && event.data.size) state.chunks.push(event.data);
    };
    state.recorder.onstop = () => {
      const durationMs = Date.now() - state.startedAt;
      const chunks = [...state.chunks];
      const mimeType = state.recorder?.mimeType || format.mimeType || "audio/webm";
      const ext = format.ext || (mimeType.includes("mp4") ? "m4a" : "webm");
      stopRecordingDevices();
      if (state.cancelOnStop) {
        state.cancelOnStop = false;
        recordState.textContent = "录音已取消";
        return;
      }
      if (!chunks.length || durationMs < 800) {
        renderMessage(serverBusyMessage(), "warn");
        recordState.textContent = serverBusyMessage();
        return;
      }
      const blob = new Blob(chunks, { type: mimeType });
      const file = new File([blob], `live-recording-${Date.now()}.${ext}`, { type: mimeType || "audio/webm" });
      setInputFiles(file);
      setPreview(file, "live");
    };

    setRecordingUi("正在录音，松开发送，上滑取消");
    state.recorder.start(500);
  } catch (error) {
    stopRecordingDevices();
    const message =
      error && error.name === "NotAllowedError"
        ? "麦克风权限被拒绝。请在浏览器权限里允许录音，或使用手机系统录音器上传。"
        : `无法启动麦克风：${error.message || "浏览器未开放录音能力"}。已切换到手机系统录音器。`;
    openNativeRecorder(message);
  }
}

function stopRecordingDevices() {
  stopTimer();
  stopDrawing();
  if (state.stream) {
    state.stream.getTracks().forEach((track) => track.stop());
  }
  if (state.audioContext) {
    state.audioContext.close().catch(() => {});
  }
  state.stream = null;
  state.audioContext = null;
  state.analyser = null;
  state.recorder = null;
  recordBtn.disabled = false;
  stopBtn.disabled = true;
  waveWrap.classList.remove("is-recording", "is-canceling");
  drawIdleWave();
}

function stopRecording({ cancel = false } = {}) {
  state.cancelOnStop = cancel;
  if (state.recorder && state.recorder.state !== "inactive") {
    state.recorder.stop();
  } else {
    stopRecordingDevices();
  }
}

function renderAudioBlock(title, url, tone, autoPlay = false) {
  if (!url) return "";
  return `
    <article class="audio-result ${tone}">
      <div>
        <span>${title}</span>
        <strong>${tone === "matched" ? "推荐播放" : "标准参考"}</strong>
      </div>
      <audio src="${escapeHtml(url)}" controls ${autoPlay ? "autoplay" : ""}></audio>
    </article>
  `;
}

function openVoiceModal() {
  if (!state.registeredVoice) return;
  voiceModal.hidden = false;
  voiceModalOutput.innerHTML = "";
  window.setTimeout(() => voiceTextInput.focus(), 0);
}

function closeVoiceModal() {
  voiceModal.hidden = true;
}

function clampMascotPosition(left, top) {
  const rect = voiceMascot.getBoundingClientRect();
  const padding = 8;
  const maxLeft = Math.max(padding, window.innerWidth - rect.width - padding);
  const maxTop = Math.max(padding, window.innerHeight - rect.height - padding);
  return {
    left: Math.min(Math.max(left, padding), maxLeft),
    top: Math.min(Math.max(top, padding), maxTop),
  };
}

function placeMascot(left, top) {
  const next = clampMascotPosition(left, top);
  voiceMascot.style.left = `${next.left}px`;
  voiceMascot.style.top = `${next.top}px`;
  voiceMascot.style.right = "auto";
  voiceMascot.style.bottom = "auto";
  try {
    localStorage.setItem("voiceMascotPosition", JSON.stringify(next));
  } catch {
    // localStorage can be blocked in embedded browsers; dragging should still work.
  }
}

function restoreMascotPosition() {
  try {
    const saved = JSON.parse(localStorage.getItem("voiceMascotPosition") || "null");
    if (saved && Number.isFinite(saved.left) && Number.isFinite(saved.top)) {
      placeMascot(saved.left, saved.top);
    }
  } catch {
    localStorage.removeItem("voiceMascotPosition");
  }
}

function beginMascotDrag(event) {
  if (!state.registeredVoice || event.button > 0) return;
  const rect = voiceMascot.getBoundingClientRect();
  state.mascotDrag = {
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    left: rect.left,
    top: rect.top,
  };
  state.mascotMoved = false;
  voiceMascot.classList.add("is-dragging");
  voiceMascot.setPointerCapture(event.pointerId);
}

function moveMascot(event) {
  if (!state.mascotDrag || state.mascotDrag.pointerId !== event.pointerId) return;
  const deltaX = event.clientX - state.mascotDrag.startX;
  const deltaY = event.clientY - state.mascotDrag.startY;
  if (Math.hypot(deltaX, deltaY) > 6) state.mascotMoved = true;
  placeMascot(state.mascotDrag.left + deltaX, state.mascotDrag.top + deltaY);
}

function endMascotDrag(event) {
  if (!state.mascotDrag || state.mascotDrag.pointerId !== event.pointerId) return;
  voiceMascot.classList.remove("is-dragging");
  voiceMascot.releasePointerCapture(event.pointerId);
  state.mascotDrag = null;
}

function renderResult(data) {
  const visibleWarnings = (data.warnings || []).filter(
    (item) => !(data.voice_matched_audio_url && String(item).includes("Gold Teacher synthesis failed"))
  );
  const warnings = visibleWarnings.map((item) => `<div class="warn-card"><p>${escapeHtml(item)}</p></div>`).join("");
  const dialectLabel = dialectNames[data.dialect] || "方言";
  state.registeredVoice =
    data.voice_id && data.voice_matched_audio_url
      ? {
          voiceId: data.voice_id,
          dialect: data.dialect,
        }
      : null;
  voiceMascot.hidden = !state.registeredVoice;
  if (state.registeredVoice) restoreMascotPosition();
  // Only show Gold Teacher when Voice Matched failed — it's a fallback.
  const showGold = !data.voice_matched_audio_url && data.gold_audio_url;
  result.innerHTML = `
    <div class="result-head">
      <p>生成完成</p>
      <h2>${dialectLabel}音色已就绪</h2>
      <span>任务 ${escapeHtml(data.job_id || "")}</span>
    </div>
    <div class="result-audio-grid">
      ${renderAudioBlock("我的克隆音色", data.voice_matched_audio_url, "matched", Boolean(data.voice_matched_audio_url))}
      ${showGold ? renderAudioBlock("备选方言音频", data.gold_audio_url, "gold", true) : ""}
    </div>
    <div class="transcript-grid">
      <article>
        <span>原始识别</span>
        <p>${escapeHtml(data.source_text || "暂无文本")}</p>
      </article>
      ${
        data.emotion_label || data.prosody_instruction
          ? `<article><span>情绪语调</span><p>${escapeHtml([data.emotion_label, data.prosody_instruction].filter(Boolean).join("；"))}</p></article>`
          : ""
      }
      <article>
        <span>方言表达</span>
        <p>${escapeHtml(data.dialect_text || "暂无文本")}</p>
      </article>
      ${
        data.pronunciation_note
          ? `<article><span>发音提示</span><p>${escapeHtml(data.pronunciation_note)}</p></article>`
          : ""
      }
    </div>
    ${warnings}
    ${state.registeredVoice ? '<div class="voice-continue"><strong>音色已保存</strong><span>点击右下角吉祥物，或用下方弹窗继续使用这个声音。</span></div>' : ""}
  `;
}

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (file) setPreview(file, "upload");
});

recordInput.addEventListener("change", () => {
  state.nativeCaptureActive = false;
  finishNativeRecorderUi();
  const file = recordInput.files[0];
  if (file) {
    setPreview(file, "capture");
  } else {
    recordState.textContent = "没有选择录音文件，可以重新录制";
  }
});

recordBtn.addEventListener("click", () => {
  if (state.ignoreNextClick) {
    state.ignoreNextClick = false;
    return;
  }
  if (state.recorder && state.recorder.state === "recording") stopRecording();
  else startRecording();
});
stopBtn.addEventListener("click", () => stopRecording());
clearBtn.addEventListener("click", clearAudio);
deleteAudioBtn.addEventListener("click", clearAudio);
voiceModalClose.addEventListener("click", closeVoiceModal);
voiceMascot.addEventListener("pointerdown", beginMascotDrag);
voiceMascot.addEventListener("pointermove", moveMascot);
voiceMascot.addEventListener("pointerup", endMascotDrag);
voiceMascot.addEventListener("pointercancel", endMascotDrag);
voiceMascot.addEventListener("click", (event) => {
  if (state.mascotMoved) {
    event.preventDefault();
    state.mascotMoved = false;
    return;
  }
  openVoiceModal();
});
window.addEventListener("resize", () => {
  if (voiceMascot.hidden) return;
  const rect = voiceMascot.getBoundingClientRect();
  placeMascot(rect.left, rect.top);
});
voiceModal.addEventListener("click", (event) => {
  if (event.target === voiceModal) closeVoiceModal();
});
voiceSpeakBtn.addEventListener("click", async () => {
  if (!state.registeredVoice) return;
  const text = voiceTextInput.value.trim();
  if (!text) {
    voiceModalOutput.innerHTML = `<div class="warn-card"><p>请输入要朗读的文本</p></div>`;
    return;
  }
  voiceSpeakBtn.disabled = true;
  voiceSpeakBtn.textContent = "正在生成";
  voiceModalOutput.textContent = "正在分析情绪语调并生成音频。";
  try {
    const body = new FormData();
    body.append("dialect", state.registeredVoice.dialect);
    body.append("voice_id", state.registeredVoice.voiceId);
    body.append("text", text);
    const response = await fetch("/api/speak-with-voice", { method: "POST", body });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "请求失败");
    voiceModalOutput.innerHTML = `
      <strong>${escapeHtml([data.emotion_label, data.prosody_instruction].filter(Boolean).join("；") || "自然口语")}</strong>
      <span>${escapeHtml(data.dialect_text || data.source_text || "")}</span>
      <audio src="${escapeHtml(data.audio_url)}" controls autoplay></audio>
    `;
  } catch (error) {
    voiceModalOutput.innerHTML = `<div class="warn-card"><p>${escapeHtml(error.message || serverBusyMessage())}</p></div>`;
  } finally {
    voiceSpeakBtn.disabled = false;
    voiceSpeakBtn.textContent = "用我的音色生成";
  }
});

recordBtn.addEventListener("pointerdown", (event) => {
  if (!isLikelyMobile() || event.pointerType === "mouse" || !supportsLiveMicrophone()) return;
  event.preventDefault();
  state.pointerRecording = true;
  state.ignoreNextClick = true;
  state.pointerStartY = event.clientY;
  state.cancelOnStop = false;
  recordBtn.setPointerCapture(event.pointerId);
  startRecording();
});

recordBtn.addEventListener("pointermove", (event) => {
  if (!state.pointerRecording) return;
  const canceling = state.pointerStartY - event.clientY > 72;
  waveWrap.classList.toggle("is-canceling", canceling);
  recordState.textContent = canceling ? "松手取消本次录音" : "正在录音，松开发送，上滑取消";
  state.cancelOnStop = canceling;
});

recordBtn.addEventListener("pointerup", (event) => {
  if (!state.pointerRecording) return;
  event.preventDefault();
  state.pointerRecording = false;
  stopRecording({ cancel: state.cancelOnStop });
});

recordBtn.addEventListener("pointercancel", () => {
  if (!state.pointerRecording) return;
  state.pointerRecording = false;
  stopRecording({ cancel: true });
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const selectedAudio = state.selectedFile || fileInput.files[0] || recordInput.files[0];
  if (!selectedAudio) {
    renderMessage("请先录音，或点击加号上传一段音频。", "warn");
    return;
  }

  let durationS = state.selectedFile === selectedAudio ? state.selectedDurationS : null;
  if (!Number.isFinite(durationS)) {
    durationS = await readFileDuration(selectedAudio, 1800);
    if (state.selectedFile === selectedAudio) {
      state.selectedDurationS = durationS;
      updateAudioMeta(selectedAudio, durationS);
    }
  }
  if (Number.isFinite(durationS) && durationS > maxAudioSeconds()) {
    renderMessage(`音频过长，请控制在 ${maxAudioSeconds()}s 以内。`, "warn");
    recordState.textContent = "音频过长，请重新录制或上传";
    return;
  }

  submitBtn.disabled = true;
  submitBtn.querySelector("span").textContent = "正在生成…";
  serviceState.textContent = "Processing";
  renderMessage("正在识别、方言化和复刻音色，请保持页面打开。", "loading");
  setStep(0);

  const progress = [1, 2, 3];
  let progressIndex = 0;
  const progressTimer = window.setInterval(() => {
    setStep(progress[progressIndex] ?? 3);
    progressIndex = Math.min(progressIndex + 1, progress.length - 1);
  }, 1800);

  try {
    const selectedDialect = form.querySelector('input[name="dialect"]:checked')?.value || "cantonese";
    const body = new FormData();
    body.append("dialect", selectedDialect);
    body.append("audio", selectedAudio, selectedAudio.name || `recording-${Date.now()}.m4a`);
    const response = await fetch("/api/convert", { method: "POST", body });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "请求失败");
    setStep(4);
    renderResult(data);
    serviceState.textContent = data.status === "ok" ? "Done" : "Needs check";
  } catch (error) {
    resetSteps();
    serviceState.textContent = "Error";
    renderMessage(error.message, "warn");
  } finally {
    window.clearInterval(progressTimer);
    submitBtn.disabled = false;
    submitBtn.querySelector("span").textContent = "生成我的方言音色";
  }
});

configureNativeRecorderInput();
fetchAudioLimits();
clearAudio();
stopDrawing();
drawIdleWave();

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    stopDrawing();
  } else if (state.recorder && state.recorder.state === "recording") {
    drawLiveWave();
  } else {
    drawIdleWave();
  }
});
