const form = document.querySelector("#convertForm");
const fileInput = document.querySelector("#audioInput");
const recordInput = document.querySelector("#recordInput");
const preview = document.querySelector("#preview");
const result = document.querySelector("#result");
const submitBtn = document.querySelector("#submitBtn");
const recordBtn = document.querySelector("#recordBtn");
const stopBtn = document.querySelector("#stopBtn");
const clearBtn = document.querySelector("#clearBtn");
const recordState = document.querySelector("#recordState");
const recordTimer = document.querySelector("#recordTimer");
const audioChip = document.querySelector("#audioChip");
const audioName = document.querySelector("#audioName");
const audioMeta = document.querySelector("#audioMeta");
const serviceState = document.querySelector("#serviceState");
const waveCanvas = document.querySelector("#waveCanvas");
const waveWrap = document.querySelector("#waveWrap");
const steps = [...document.querySelectorAll("#steps li")];

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
  demoPulse: 0,
};

const dialectNames = {
  cantonese: "粤语",
  sichuanese: "四川话",
  hokkien: "闽南话",
};

function supportsLiveMicrophone() {
  return Boolean(
    window.isSecureContext &&
      navigator.mediaDevices &&
      typeof navigator.mediaDevices.getUserMedia === "function" &&
      window.MediaRecorder
  );
}

function openNativeRecorder(reason = "") {
  recordState.textContent = "请在系统录音界面完成录制";
  serviceState.textContent = "Native record";
  if (reason) {
    renderMessage(`${reason} 已切换到手机系统录音。录完后选择音频即可继续生成。`, "warn");
  }
  recordInput.click();
}

function formatTime(ms) {
  const total = Math.max(0, Math.floor(ms / 1000));
  const minutes = String(Math.floor(total / 60)).padStart(2, "0");
  const seconds = String(total % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function formatSize(bytes) {
  if (!bytes) return "0 KB";
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
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
  const width = waveCanvas.width;
  const height = waveCanvas.height;
  state.demoPulse += 0.018;
  ctx.clearRect(0, 0, width, height);
  const gradient = ctx.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, "#0e1117");
  gradient.addColorStop(0.58, "#111827");
  gradient.addColorStop(1, "#d8e9ff");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);

  const glow = ctx.createRadialGradient(width * 0.62, height * 0.9, 20, width * 0.62, height * 0.9, height * 0.62);
  glow.addColorStop(0, "rgba(218, 238, 255, 0.9)");
  glow.addColorStop(0.34, "rgba(101, 153, 220, 0.34)");
  glow.addColorStop(1, "rgba(101, 153, 220, 0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = "rgba(255, 255, 255, 0.22)";
  ctx.lineWidth = 3;
  ctx.beginPath();
  for (let x = 0; x <= width; x += 8) {
    const y = height * 0.68 + Math.sin(x * 0.018 + state.demoPulse) * 10 + Math.sin(x * 0.043) * 4;
    if (x === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
  state.animationId = requestAnimationFrame(drawIdleWave);
}

function drawLiveWave() {
  if (!state.analyser) return;
  const width = waveCanvas.width;
  const height = waveCanvas.height;
  const data = new Uint8Array(state.analyser.frequencyBinCount);
  state.analyser.getByteTimeDomainData(data);

  ctx.clearRect(0, 0, width, height);
  const gradient = ctx.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, "#080b10");
  gradient.addColorStop(0.64, "#111827");
  gradient.addColorStop(1, "#9fd1ff");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);

  ctx.lineWidth = 4;
  ctx.strokeStyle = "#f8fbff";
  ctx.beginPath();
  const slice = width / data.length;
  data.forEach((value, index) => {
    const x = index * slice;
    const y = (value / 255) * height;
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  state.animationId = requestAnimationFrame(drawLiveWave);
}

function stopDrawing() {
  if (state.animationId) cancelAnimationFrame(state.animationId);
  state.animationId = null;
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

function setPreview(file) {
  if (!file) return;
  state.selectedFile = file;
  preview.src = URL.createObjectURL(file);
  audioName.textContent = file.name || "现场录音";
  audioMeta.textContent = `${formatSize(file.size)} · 已准备生成`;
  audioChip.hidden = false;
  recordState.textContent = "音频已就绪";
  serviceState.textContent = "Audio ready";
  waveWrap.classList.add("has-audio");
}

function setSelectedAudio(file, source = "upload") {
  if (!file) return;
  setPreview(file);
  if (source === "capture") {
    audioName.textContent = file.name || "手机录音";
    recordState.textContent = "手机录音已就绪";
  }
}

function clearAudio() {
  fileInput.value = "";
  recordInput.value = "";
  state.selectedFile = null;
  preview.removeAttribute("src");
  preview.load();
  audioChip.hidden = true;
  recordTimer.textContent = "00:00";
  recordState.textContent = "按住乡音，从这里开始";
  serviceState.textContent = "Ready";
  waveWrap.classList.remove("is-recording", "has-audio");
  resetSteps();
}

async function startRecording() {
  if (!supportsLiveMicrophone()) {
    openNativeRecorder("当前浏览器或 HTTP 页面不能直接访问实时麦克风。");
    return;
  }

  try {
    state.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    state.chunks = [];
    state.recorder = new MediaRecorder(state.stream);
    state.audioContext = new AudioContext();
    const source = state.audioContext.createMediaStreamSource(state.stream);
    state.analyser = state.audioContext.createAnalyser();
    state.analyser.fftSize = 2048;
    source.connect(state.analyser);

    state.recorder.ondataavailable = (event) => {
      if (event.data.size) state.chunks.push(event.data);
    };
    state.recorder.onstop = () => {
      const blob = new Blob(state.chunks, { type: "audio/webm" });
      const file = new File([blob], `live-recording-${Date.now()}.webm`, { type: "audio/webm" });
      const transfer = new DataTransfer();
      transfer.items.add(file);
      fileInput.files = transfer.files;
      setPreview(file);
      stopRecordingDevices();
    };

    stopDrawing();
    drawLiveWave();
    startTimer();
    state.recorder.start();
    recordBtn.disabled = true;
    stopBtn.disabled = false;
    waveWrap.classList.add("is-recording");
    recordState.textContent = "正在录制你的声音";
    serviceState.textContent = "Recording";
  } catch (error) {
    const message = error && error.name === "NotAllowedError"
      ? "麦克风权限被拒绝。"
      : `无法启动麦克风：${error.message || "浏览器未开放录音能力"}。`;
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
  recordBtn.disabled = false;
  stopBtn.disabled = true;
  waveWrap.classList.remove("is-recording");
  drawIdleWave();
}

function stopRecording() {
  if (state.recorder && state.recorder.state !== "inactive") {
    state.recorder.stop();
  } else {
    stopRecordingDevices();
  }
}

function renderMessage(message, level = "empty") {
  result.innerHTML = `<div class="${level === "warn" ? "warn-card" : "empty-state"}"><p>${escapeHtml(message)}</p></div>`;
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

function renderResult(data) {
  const warnings = (data.warnings || []).map((item) => `<div class="warn-card">${escapeHtml(item)}</div>`).join("");
  const dialectLabel = dialectNames[data.dialect] || "方言";
  result.innerHTML = `
    <div class="result-head">
      <p>生成完成</p>
      <h2>${dialectLabel}音色已就绪</h2>
      <span>任务 ${escapeHtml(data.job_id || "")}</span>
    </div>
    <div class="result-audio-grid">
      ${renderAudioBlock("Voice Matched 克隆音色", data.voice_matched_audio_url, "matched", Boolean(data.voice_matched_audio_url))}
      ${renderAudioBlock("Gold Teacher 标准方言", data.gold_audio_url, "gold", !data.voice_matched_audio_url)}
    </div>
    <div class="transcript-grid">
      <article>
        <span>原始识别</span>
        <p>${escapeHtml(data.source_text || "暂无文本")}</p>
      </article>
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
  `;
}

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (file) setSelectedAudio(file, "upload");
});

recordInput.addEventListener("change", () => {
  const file = recordInput.files[0];
  if (file) setSelectedAudio(file, "capture");
});

recordBtn.addEventListener("click", startRecording);
stopBtn.addEventListener("click", stopRecording);
clearBtn.addEventListener("click", clearAudio);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const selectedAudio = state.selectedFile || fileInput.files[0] || recordInput.files[0];
  if (!selectedAudio) {
    renderMessage("请先录音或点击加号上传一段音频。", "warn");
    return;
  }

  submitBtn.disabled = true;
  submitBtn.querySelector("span").textContent = "正在生成";
  serviceState.textContent = "Processing";
  renderMessage("正在识别、方言化和复刻音色，请保持页面打开。");
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
    body.append("audio", selectedAudio);
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

drawIdleWave();
