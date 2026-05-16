const form = document.querySelector("#convertForm");
const fileInput = document.querySelector("#audioInput");
const preview = document.querySelector("#preview");
const result = document.querySelector("#result");
const submitBtn = document.querySelector("#submitBtn");
const recordBtn = document.querySelector("#recordBtn");
const stopBtn = document.querySelector("#stopBtn");
const recordState = document.querySelector("#recordState");

let recorder;
let chunks = [];

function setPreview(file) {
  if (!file) return;
  preview.src = URL.createObjectURL(file);
}

fileInput.addEventListener("change", () => setPreview(fileInput.files[0]));

recordBtn.addEventListener("click", async () => {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  chunks = [];
  recorder = new MediaRecorder(stream);
  recorder.ondataavailable = (event) => {
    if (event.data.size) chunks.push(event.data);
  };
  recorder.onstop = () => {
    const blob = new Blob(chunks, { type: "audio/webm" });
    const file = new File([blob], `mobile-recording-${Date.now()}.webm`, { type: "audio/webm" });
    const transfer = new DataTransfer();
    transfer.items.add(file);
    fileInput.files = transfer.files;
    setPreview(file);
    stream.getTracks().forEach((track) => track.stop());
    recordState.textContent = "录音已就绪";
  };
  recorder.start();
  recordBtn.disabled = true;
  stopBtn.disabled = false;
  recordState.textContent = "录音中";
});

stopBtn.addEventListener("click", () => {
  if (recorder && recorder.state !== "inactive") recorder.stop();
  recordBtn.disabled = false;
  stopBtn.disabled = true;
});

function renderResult(data) {
  const recommended = data.recommended_audio_url
    ? `<audio src="${data.recommended_audio_url}" controls autoplay></audio>`
    : "";
  const gold = data.gold_audio_url
    ? `<div class="text-block"><strong>Gold Teacher 标准方言</strong><audio src="${data.gold_audio_url}" controls></audio></div>`
    : "";
  const voice = data.voice_matched_audio_url
    ? `<div class="text-block"><strong>Voice Matched 克隆音色</strong><audio src="${data.voice_matched_audio_url}" controls></audio></div>`
    : "";
  const warnings = (data.warnings || []).map((x) => `<div class="warn">${x}</div>`).join("");
  result.innerHTML = `
    <h2>${data.status === "ok" ? "生成完成" : "生成失败"}</h2>
    ${recommended}
    ${voice}
    ${gold}
    <div class="text-block"><strong>识别文本</strong><span>${data.source_text || ""}</span></div>
    <div class="text-block"><strong>方言文本</strong><span>${data.dialect_text || ""}</span></div>
    ${data.pronunciation_note ? `<div class="text-block"><strong>发音说明</strong><span>${data.pronunciation_note}</span></div>` : ""}
    ${warnings}
  `;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!fileInput.files.length) {
    result.innerHTML = `<div class="warn">请先录音或上传音频。</div>`;
    return;
  }
  submitBtn.disabled = true;
  submitBtn.textContent = "生成中，请稍候";
  result.innerHTML = `<div class="empty">正在识别、方言化和复刻音色...</div>`;
  try {
    const body = new FormData(form);
    const response = await fetch("/api/convert", { method: "POST", body });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "请求失败");
    renderResult(data);
  } catch (error) {
    result.innerHTML = `<div class="warn">${error.message}</div>`;
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "生成方言复刻语音";
  }
});

