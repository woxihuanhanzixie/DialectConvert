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
const sceneCards = [...document.querySelectorAll(".scene-card")];
const communityPanel = document.querySelector("#communityPanel");
const communityEyebrow = document.querySelector("#communityEyebrow");
const communityTitle = document.querySelector("#communityTitle");
const communityPrompt = document.querySelector("#communityPrompt");
const communityFeed = document.querySelector("#communityFeed");
const openPublishBtn = document.querySelector("#openPublishBtn");
const communityModal = document.querySelector("#communityModal");
const communityModalClose = document.querySelector("#communityModalClose");
const communityModalTitle = document.querySelector("#communityModalTitle");
const communityModalOutput = document.querySelector("#communityModalOutput");
const postTitleInput = document.querySelector("#postTitleInput");
const postBodyInput = document.querySelector("#postBodyInput");
const postDialectTextInput = document.querySelector("#postDialectTextInput");
const postSceneInput = document.querySelector("#postSceneInput");
const postDialectInput = document.querySelector("#postDialectInput");
const publishPostBtn = document.querySelector("#publishPostBtn");
const correctionModal = document.querySelector("#correctionModal");
const correctionModalClose = document.querySelector("#correctionModalClose");
const correctionSuggestionInput = document.querySelector("#correctionSuggestionInput");
const correctionNoteInput = document.querySelector("#correctionNoteInput");
const correctionModalOutput = document.querySelector("#correctionModalOutput");
const submitCorrectionBtn = document.querySelector("#submitCorrectionBtn");
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
  lastResult: null,
  previewRequestId: 0,
  mascotDrag: null,
  mascotMoved: false,
  communityScene: "youth",
  correctionPostId: "",
  publishFromResult: false,
};

const dialectNames = {
  cantonese: "粤语",
  sichuanese: "四川话",
  hokkien: "闽南话",
};

const sceneMeta = {
  youth: {
    label: "Z世代社交",
    title: "校园里的第一条方言数字人作品",
    prompt: "方言表情包、宿舍配音、校园挑战榜",
    avatar: "🌱",
    persona: "校园方言玩家",
  },
  elder: {
    label: "乡音陪伴",
    title: "用亲人的声音，把问候留在身边",
    prompt: "亲人声音数字人、方言童谣、怀旧问候模板",
    avatar: "🧓",
    persona: "亲情陪伴数字人",
  },
  village: {
    label: "乡村振兴",
    title: "让古村导览开口说本地话",
    prompt: "AI 方言导览员、文旅讲解、农产品 IP 配音",
    avatar: "🏡",
    persona: "古村方言导览员",
  },
  overseas: {
    label: "侨乡寻根",
    title: "跨越时差的第一句祖辈乡音",
    prompt: "海外华侨乡音地图、祖辈故事、侨校方言学习卡",
    avatar: "🌏",
    persona: "侨乡寻根数字分身",
  },
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

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "请求失败");
  return data;
}

function formatDateTime(seconds) {
  if (!seconds) return "刚刚";
  const date = new Date(seconds * 1000);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");
  return `${month}-${day} ${hour}:${minute}`;
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
  if (now - state.lastDrawAt < 50) {
    state.animationId = requestAnimationFrame(drawIdleWave);
    return;
  }
  state.lastDrawAt = now;
  const width = waveCanvas.width;
  const height = waveCanvas.height;
  state.demoPulse += 0.012;
  ctx.clearRect(0, 0, width, height);

  // Forest floor gradient
  const bgGrad = ctx.createLinearGradient(0, 0, 0, height);
  bgGrad.addColorStop(0, "#0a1610");
  bgGrad.addColorStop(0.55, "#0f2116");
  bgGrad.addColorStop(1, "#183422");
  ctx.fillStyle = bgGrad;
  ctx.fillRect(0, 0, width, height);

  // Ground line
  const groundY = height * 0.78;
  ctx.strokeStyle = "rgba(107, 138, 90, 0.18)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, groundY);
  for (let x = 0; x <= width; x += 3) {
    ctx.lineTo(x, groundY + Math.sin(x * 0.04 + state.demoPulse * 0.5) * 4);
  }
  ctx.stroke();

  // Distant foliage haze
  const hazeGrad = ctx.createRadialGradient(width * 0.68, groundY - 80, 20, width * 0.68, groundY - 40, height * 0.7);
  hazeGrad.addColorStop(0, "rgba(107, 138, 90, 0.13)");
  hazeGrad.addColorStop(0.5, "rgba(124, 200, 100, 0.06)");
  hazeGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
  ctx.fillStyle = hazeGrad;
  ctx.fillRect(0, 0, width, height);

  // --- Dialect tree sapling ---
  const cx = width * 0.48;
  const baseY = groundY + 6;
  const sway = Math.sin(state.demoPulse * 1.4) * 1.2;

  // Roots
  ctx.strokeStyle = "rgba(107, 138, 90, 0.3)";
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.moveTo(cx, baseY);
  ctx.quadraticCurveTo(cx - 18, baseY + 18, cx - 32, baseY + 24);
  ctx.moveTo(cx, baseY);
  ctx.quadraticCurveTo(cx + 16, baseY + 18, cx + 32, baseY + 22);
  ctx.stroke();

  // Trunk
  const trunkGrad = ctx.createLinearGradient(cx, baseY, cx, baseY - 80);
  trunkGrad.addColorStop(0, "#4a6a3a");
  trunkGrad.addColorStop(0.5, "#6b8a50");
  trunkGrad.addColorStop(1, "#8aaa6a");
  ctx.strokeStyle = trunkGrad;
  ctx.lineWidth = 5;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(cx, baseY);
  ctx.lineTo(cx + sway, baseY - 60);
  ctx.stroke();

  // Main branches
  ctx.lineWidth = 3;
  const branchY = baseY - 38;
  ctx.beginPath();
  ctx.moveTo(cx + sway, branchY);
  ctx.quadraticCurveTo(cx - 18 + sway, branchY - 14, cx - 34, branchY - 20);
  ctx.moveTo(cx + sway, branchY);
  ctx.quadraticCurveTo(cx + 22 + sway, branchY - 16, cx + 38, branchY - 24);
  ctx.stroke();

  // Upper branch
  ctx.lineWidth = 2.2;
  const topY = baseY - 50;
  ctx.beginPath();
  ctx.moveTo(cx + sway, topY);
  ctx.quadraticCurveTo(cx - 10 + sway, topY - 10, cx - 22, topY - 16);
  ctx.moveTo(cx + sway, topY);
  ctx.quadraticCurveTo(cx + 14 + sway, topY - 8, cx + 26, topY - 18);
  ctx.stroke();

  // Leaf clusters (circles with glow)
  const leaves = [
    [cx - 34, branchY - 20, 12],
    [cx + 38, branchY - 24, 11],
    [cx - 22, topY - 16, 10],
    [cx + 26, topY - 18, 9],
    [cx + sway, topY - 22, 8],
  ];
  leaves.forEach(([lx, ly, r]) => {
    const leafGrad = ctx.createRadialGradient(lx, ly, r * 0.2, lx, ly, r);
    leafGrad.addColorStop(0, "rgba(168, 232, 140, 0.7)");
    leafGrad.addColorStop(0.6, "rgba(124, 200, 100, 0.35)");
    leafGrad.addColorStop(1, "rgba(80, 150, 60, 0)");
    ctx.fillStyle = leafGrad;
    ctx.beginPath();
    ctx.arc(lx, ly, r, 0, Math.PI * 2);
    ctx.fill();
  });

  // Floating leaf particles
  for (let i = 0; i < 4; i++) {
    const lx = cx - 40 + i * 22 + Math.sin(state.demoPulse * 2 + i) * 14;
    const ly = baseY - 70 - i * 10 + Math.cos(state.demoPulse * 1.8 + i) * 8;
    ctx.fillStyle = "rgba(124, 219, 106, 0.15)";
    ctx.beginPath();
    ctx.ellipse(lx, ly, 5, 2.5, Math.sin(state.demoPulse + i) * 0.8, 0, Math.PI * 2);
    ctx.fill();
  }

  // Ground glow
  const groundGlow = ctx.createRadialGradient(cx, baseY, 6, cx, baseY, 50);
  groundGlow.addColorStop(0, "rgba(124, 219, 106, 0.1)");
  groundGlow.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = groundGlow;
  ctx.fillRect(cx - 50, baseY - 30, 100, 50);

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
      <div class="demo-processing" aria-busy="true">
        <div class="demo-processing-mark" aria-hidden="true">成</div>
        <p>${escapeHtml(message)}</p>
        <span>后台正在完成 ASR、方言改写和音色生成，可继续展示产品场景。</span>
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

function updateCommunityHeader(scene) {
  const meta = sceneMeta[scene] || sceneMeta.youth;
  communityEyebrow.textContent = meta.label;
  communityTitle.textContent = meta.title;
  communityPrompt.textContent = meta.prompt;
  sceneCards.forEach((card) => card.classList.toggle("is-selected", card.dataset.scene === scene));
}

function communityAvatar(post) {
  const scene = sceneMeta[post.scene] || sceneMeta.youth;
  const avatarMap = {
    sprout: "木",
    leaf: "🌱",
    home: "🧓",
    guide: "🏡",
    map: "🌏",
  };
  return avatarMap[post.avatar] || scene.avatar || "木";
}

function renderCommunityPost(post) {
  const dialectLabel = dialectNames[post.dialect] || "方言";
  const comments = (post.comments || []).slice(-2);
  return `
    <article class="community-post" data-post-id="${escapeHtml(post.id)}">
      <div class="post-avatar" aria-hidden="true">${escapeHtml(communityAvatar(post))}</div>
      <div class="post-body">
        <div class="post-meta">
          <span>${escapeHtml(post.persona || "乡音数字分身")}</span>
          <span>${escapeHtml(dialectLabel)}</span>
          <span>${escapeHtml(formatDateTime(post.created_at))}</span>
        </div>
        <h3>${escapeHtml(post.title || "未命名乡音作品")}</h3>
        ${post.body ? `<p class="post-desc">${escapeHtml(post.body)}</p>` : ""}
        ${
          post.source_text
            ? `<div class="post-line"><span>原文</span><p>${escapeHtml(post.source_text)}</p></div>`
            : ""
        }
        ${
          post.dialect_text
            ? `<div class="post-line is-dialect"><span>方言台词</span><p>${escapeHtml(post.dialect_text)}</p></div>`
            : ""
        }
        ${post.audio_url ? `<audio class="post-audio" src="${escapeHtml(post.audio_url)}" controls preload="metadata"></audio>` : ""}
        <div class="post-actions">
          <button type="button" data-action="like">赞 ${Number(post.likes || 0)}</button>
          <button type="button" data-action="bookmark">收藏 ${Number(post.bookmarks || 0)}</button>
          <button type="button" data-action="correct">贡献说法 ${Number(post.corrections || 0)}</button>
        </div>
        <form class="comment-form">
          <input maxlength="160" placeholder="留一句评论或使用场景建议" />
          <button type="submit">评论</button>
        </form>
        ${
          comments.length
            ? `<div class="post-comments">${comments
                .map((comment) => `<p><strong>${escapeHtml(comment.author || "社区成员")}</strong>${escapeHtml(comment.text)}</p>`)
                .join("")}</div>`
            : ""
        }
      </div>
    </article>`;
}

async function loadCommunity(scene = state.communityScene) {
  state.communityScene = scene;
  updateCommunityHeader(scene);
  communityFeed.innerHTML = `<div class="community-empty">正在加载乡音作品...</div>`;
  try {
    const data = await fetchJson(`/api/community/posts?scene=${encodeURIComponent(scene)}`);
    const posts = data.posts || [];
    communityFeed.innerHTML = posts.length
      ? posts.map(renderCommunityPost).join("")
      : `<div class="community-empty">这个社区还没有作品，发布第一条乡音数字分身。</div>`;
  } catch (error) {
    communityFeed.innerHTML = `<div class="warn-card"><p>${escapeHtml(error.message || serverBusyMessage())}</p></div>`;
  }
}

function openCommunityModal(fromResult = false) {
  state.publishFromResult = fromResult;
  const meta = sceneMeta[state.communityScene] || sceneMeta.youth;
  const data = fromResult ? state.lastResult : null;
  communityModalTitle.textContent = fromResult ? "发布刚生成的音色作品" : "发布到社区";
  postSceneInput.value = state.communityScene;
  postDialectInput.value =
    data?.dialect || form.querySelector('input[name="dialect"]:checked')?.value || "cantonese";
  postTitleInput.value = data ? `${dialectNames[data.dialect] || "方言"}音色作品` : "";
  postBodyInput.value = data ? `一个适合${meta.label}场景的乡音数字分身作品。` : "";
  postDialectTextInput.value = data?.dialect_text || "";
  communityModalOutput.innerHTML = data?.recommended_audio_url
    ? `<span>已带入刚生成的音频，发布后会作为作品播放器展示。</span>`
    : "";
  communityModal.hidden = false;
  postTitleInput.focus();
}

function closeCommunityModal() {
  communityModal.hidden = true;
  communityModalOutput.innerHTML = "";
  state.publishFromResult = false;
}

async function publishCommunityPost() {
  const scene = postSceneInput.value;
  const meta = sceneMeta[scene] || sceneMeta.youth;
  const data = state.publishFromResult ? state.lastResult : null;
  const payload = {
    scene,
    dialect: postDialectInput.value,
    title: postTitleInput.value,
    body: postBodyInput.value,
    source_text: data?.source_text || "",
    dialect_text: postDialectTextInput.value,
    audio_url: data?.recommended_audio_url || "",
    avatar: scene === "youth" ? "leaf" : scene === "elder" ? "home" : scene === "village" ? "guide" : "map",
    persona: meta.persona,
    author: "方言守护者",
  };
  publishPostBtn.disabled = true;
  publishPostBtn.textContent = "正在发布";
  try {
    await fetchJson("/api/community/posts", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.communityScene = scene;
    closeCommunityModal();
    await loadCommunity(scene);
    communityPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    communityModalOutput.innerHTML = `<div class="warn-card"><p>${escapeHtml(error.message || serverBusyMessage())}</p></div>`;
  } finally {
    publishPostBtn.disabled = false;
    publishPostBtn.textContent = "发布作品";
  }
}

function openCorrectionModal(postId) {
  state.correctionPostId = postId;
  correctionSuggestionInput.value = "";
  correctionNoteInput.value = "";
  correctionModalOutput.innerHTML = `<span>提交后会进入候选语料池，审核通过后才会反哺 RAG/知识图谱。</span>`;
  correctionModal.hidden = false;
  correctionSuggestionInput.focus();
}

function closeCorrectionModal() {
  correctionModal.hidden = true;
  state.correctionPostId = "";
  correctionModalOutput.innerHTML = "";
}

async function submitCorrection() {
  if (!state.correctionPostId) return;
  submitCorrectionBtn.disabled = true;
  submitCorrectionBtn.textContent = "正在提交";
  try {
    await fetchJson(`/api/community/posts/${encodeURIComponent(state.correctionPostId)}/corrections`, {
      method: "POST",
      body: JSON.stringify({
        suggestion: correctionSuggestionInput.value,
        note: correctionNoteInput.value,
      }),
    });
    closeCorrectionModal();
    await loadCommunity(state.communityScene);
  } catch (error) {
    correctionModalOutput.innerHTML = `<div class="warn-card"><p>${escapeHtml(error.message || serverBusyMessage())}</p></div>`;
  } finally {
    submitCorrectionBtn.disabled = false;
    submitCorrectionBtn.textContent = "提交到候选池";
  }
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
  state.lastResult = data;
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
    <div class="voice-continue community-share">
      <strong>生成乡音数字分身</strong>
      <span>把这段方言音频发布到场景社区，让作品、纠错和语料一起沉淀。</span>
      <button type="button" id="shareResultBtn">发布到乡音社区</button>
    </div>
    ${state.registeredVoice ? '<div class="voice-continue"><strong>音色已保存</strong><span>点击右下角吉祥物，或用下方弹窗继续使用这个声音。</span></div>' : ""}
  `;
  document.querySelector("#shareResultBtn")?.addEventListener("click", () => openCommunityModal(true));
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
sceneCards.forEach((card) => {
  card.addEventListener("click", () => {
    const scene = card.dataset.scene || "youth";
    loadCommunity(scene);
    communityPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  });
});
openPublishBtn.addEventListener("click", () => openCommunityModal(false));
communityModalClose.addEventListener("click", closeCommunityModal);
communityModal.addEventListener("click", (event) => {
  if (event.target === communityModal) closeCommunityModal();
});
publishPostBtn.addEventListener("click", publishCommunityPost);
correctionModalClose.addEventListener("click", closeCorrectionModal);
correctionModal.addEventListener("click", (event) => {
  if (event.target === correctionModal) closeCorrectionModal();
});
submitCorrectionBtn.addEventListener("click", submitCorrection);
communityFeed.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const post = button.closest(".community-post");
  const postId = post?.dataset.postId;
  if (!postId) return;
  const action = button.dataset.action;
  if (action === "correct") {
    openCorrectionModal(postId);
    return;
  }
  button.disabled = true;
  try {
    await fetchJson(`/api/community/posts/${encodeURIComponent(postId)}/reactions`, {
      method: "POST",
      body: JSON.stringify({ action }),
    });
    await loadCommunity(state.communityScene);
  } catch (error) {
    communityFeed.insertAdjacentHTML("afterbegin", `<div class="warn-card"><p>${escapeHtml(error.message)}</p></div>`);
  } finally {
    button.disabled = false;
  }
});
communityFeed.addEventListener("submit", async (event) => {
  const formEl = event.target.closest(".comment-form");
  if (!formEl) return;
  event.preventDefault();
  const post = formEl.closest(".community-post");
  const postId = post?.dataset.postId;
  const input = formEl.querySelector("input");
  if (!postId || !input) return;
  const text = input.value.trim();
  if (!text) return;
  const submit = formEl.querySelector("button");
  submit.disabled = true;
  try {
    await fetchJson(`/api/community/posts/${encodeURIComponent(postId)}/comments`, {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    input.value = "";
    await loadCommunity(state.communityScene);
  } catch (error) {
    communityFeed.insertAdjacentHTML("afterbegin", `<div class="warn-card"><p>${escapeHtml(error.message)}</p></div>`);
  } finally {
    submit.disabled = false;
  }
});
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
  submitBtn.querySelector("span").textContent = "生成流程运行中";
  serviceState.textContent = "Processing";
  renderMessage("产品生成流程已启动，正在完成语音识别、方言改写与音色合成。", "loading");
  setStep(4);

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
    submitBtn.disabled = false;
    submitBtn.querySelector("span").textContent = "生成我的方言音色";
  }
});

configureNativeRecorderInput();
fetchAudioLimits();
clearAudio();
stopDrawing();
drawIdleWave();
loadCommunity("youth");

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    stopDrawing();
  } else if (state.recorder && state.recorder.state === "recording") {
    drawLiveWave();
  } else {
    drawIdleWave();
  }
});
