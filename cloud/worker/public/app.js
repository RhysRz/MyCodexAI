"use strict";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
let account = null;
let conversationId = null;
let files = [];
let runTimer = null;
let musicTimer = null;
let imageBlob = null;

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !(options.body instanceof ArrayBuffer) && !(options.body instanceof Blob)) headers["Content-Type"] = "application/json";
  const response = await fetch(path, { credentials: "same-origin", ...options, headers });
  if (response.status === 401) {
    location.replace("/login");
    throw new Error("เซสชันหมดอายุ");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `คำขอล้มเหลว (${response.status})`);
  return data;
}

function toast(message) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.remove("hidden");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => node.classList.add("hidden"), 3500);
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function closeSidebar() {
  $("#sidebar").classList.remove("open");
  $("#backdrop").classList.add("hidden");
}

function openSidebar() {
  $("#sidebar").classList.add("open");
  $("#backdrop").classList.remove("hidden");
}

function showView(name) {
  $$(".view").forEach((node) => node.classList.toggle("active-view", node.id === `view-${name}`));
  $$(".nav-item").forEach((node) => node.classList.toggle("active", node.dataset.view === name));
  const titles = { chat: "MyCodex", agent: "Cloud Agent", files: "ไฟล์แนบ", images: "Image Studio", music: "Music Lab", account: "บัญชีและความปลอดภัย", training: "Training Lab", system: "สถานะระบบ", admin: "ผู้ดูแลระบบ" };
  $("#view-title").textContent = titles[name] || "MyCodexAI";
  closeSidebar();
  if (name === "agent") loadRuns();
  if (name === "files") loadFiles();
  if (name === "images") loadImageStatus();
  if (name === "music") loadMusicJobs();
  if (name === "training") loadTraining();
  if (name === "system") loadSystem();
  if (name === "account") Promise.all([loadSessions(), loadMfa(), loadOAuth()]).catch((error) => toast(error.message));
}

function addBubble(role, content, pending = false) {
  const welcome = $(".welcome");
  if (welcome) welcome.remove();
  const row = element("div", `bubble-row ${role}`);
  const bubble = element("div", `bubble${pending ? " typing" : ""}`);
  bubble.append(element("span", "bubble-label", role === "user" ? "คุณ" : "MYCODEX"));
  const text = element("span", "bubble-text", content);
  bubble.append(text);
  row.append(bubble);
  $("#messages").append(row);
  $("#messages").scrollTop = $("#messages").scrollHeight;
  return { row, bubble, text };
}

async function loadHistory(id) {
  const data = await api(`/api/chat/history${id ? `?conversation=${encodeURIComponent(id)}` : ""}`);
  conversationId = data.conversation_id;
  const messages = $("#messages");
  messages.replaceChildren();
  if (!data.messages.length) {
    const welcome = element("div", "welcome");
    const mark = element("div", "brand-mark", "M");
    welcome.append(mark, element("h1", "", "สวัสดีครับ ผม MyCodex"), element("p", "", "คุย ถาม หรือให้ช่วยวางแผนได้ตามปกติ งานที่ต้องแก้โค้ดให้เลือก Cloud Agent"));
    messages.append(welcome);
  } else data.messages.forEach((item) => addBubble(item.role, item.content));
  await loadConversations();
}

async function loadConversations() {
  const data = await api("/api/chat/conversations");
  const list = $("#conversation-list");
  list.replaceChildren();
  data.conversations.forEach((item) => {
    const button = element("button", `conversation${item.id === conversationId ? " active" : ""}`, item.title || "แชทใหม่");
    button.type = "button";
    button.addEventListener("click", () => loadHistory(item.id).catch((error) => toast(error.message)));
    list.append(button);
  });
}

async function sendMessage(message) {
  addBubble("user", message);
  const pending = addBubble("assistant", "", true);
  const response = await fetch("/api/chat/stream", {
    method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
  if (response.status === 401) return location.replace("/login");
  if (!response.ok || !response.body) {
    const data = await response.json().catch(() => ({}));
    pending.row.remove();
    throw new Error(data.detail || "MyCodex ยังตอบไม่ได้ กรุณาลองใหม่");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";
    for (const frame of frames) {
      const line = frame.split("\n").find((part) => part.startsWith("data:"));
      if (!line) continue;
      const event = JSON.parse(line.slice(5).trim());
      if (event.type === "delta") pending.text.textContent += event.delta;
      if (event.type === "done") conversationId = event.conversation_id || conversationId;
      if (event.type === "error") throw new Error(event.detail);
      $("#messages").scrollTop = $("#messages").scrollHeight;
    }
    if (done) break;
  }
  pending.bubble.classList.remove("typing");
  if ($("#voice-auto-read").checked && pending.text.textContent.trim()) speakThai(pending.text.textContent);
  await loadConversations();
}

function speechRecognition() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function listenThai() {
  const Recognition = speechRecognition();
  if (!Recognition) {
    toast("เบราว์เซอร์นี้ยังไม่รองรับการรับเสียง กรุณาใช้ Chrome, Edge หรือ Safari รุ่นล่าสุด");
    return;
  }
  const recognition = new Recognition();
  recognition.lang = "th-TH";
  recognition.interimResults = true;
  recognition.continuous = false;
  const button = $("#voice-input");
  const status = $("#voice-status");
  recognition.onstart = () => { button.classList.add("listening"); status.textContent = "กำลังฟัง…"; };
  recognition.onresult = (event) => {
    const transcript = [...event.results].map((result) => result[0]?.transcript || "").join("");
    $("#message-input").value = transcript;
    status.textContent = event.results[event.results.length - 1]?.isFinal ? "รับข้อความแล้ว" : "กำลังถอดเสียง…";
  };
  recognition.onerror = (event) => { status.textContent = event.error === "not-allowed" ? "ไมโครโฟนไม่ได้รับอนุญาต" : "รับเสียงไม่สำเร็จ"; };
  recognition.onend = () => button.classList.remove("listening");
  recognition.start();
}

function speakThai(text) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(String(text || "").slice(0, 5_000));
  utterance.lang = "th-TH";
  utterance.rate = 1;
  const voices = window.speechSynthesis.getVoices();
  utterance.voice = voices.find((voice) => voice.lang.toLowerCase().startsWith("th")) || null;
  window.speechSynthesis.speak(utterance);
}

async function loadFiles() {
  const data = await api("/api/files");
  files = data.files || [];
  const list = $("#file-list");
  list.replaceChildren();
  if (!files.length) list.append(element("p", "muted", "ยังไม่มีไฟล์แนบ"));
  files.forEach((file) => {
    const card = element("article", "item-card");
    card.append(element("h3", "", file.name), element("p", "", `${(file.size_bytes / 1024).toFixed(1)} KB · ${file.status === "ready" ? "พร้อมใช้" : "กำลังอัปโหลด"}`));
    const actions = element("div", "item-actions");
    const remove = element("button", "danger", "ลบ");
    remove.addEventListener("click", async () => { await api(`/api/files/${file.id}`, { method: "DELETE" }); await loadFiles(); });
    actions.append(remove); card.append(actions); list.append(card);
  });
  const choices = $("#agent-files");
  choices.replaceChildren();
  const ready = files.filter((file) => file.status === "ready");
  if (!ready.length) choices.textContent = "ยังไม่มีไฟล์พร้อมใช้";
  ready.forEach((file) => {
    const label = element("label");
    const checkbox = document.createElement("input"); checkbox.type = "checkbox"; checkbox.value = file.id;
    label.append(checkbox, document.createTextNode(file.name)); choices.append(label);
  });
  const musicSelect = $("#music-file");
  const selectedMusic = musicSelect.value;
  musicSelect.replaceChildren(new Option("เลือก PDF หรือไฟล์เสียง", ""));
  ready.filter((file) => /\.(pdf|wav|wave|mp3|flac|m4a|aac|ogg)$/i.test(file.name)).forEach((file) => musicSelect.append(new Option(file.name, file.id)));
  if ([...musicSelect.options].some((option) => option.value === selectedMusic)) musicSelect.value = selectedMusic;
}

async function uploadFile(file) {
  const meta = await api("/api/files", { method: "POST", body: JSON.stringify({ name: file.name, media_type: file.type, size_bytes: file.size }) });
  for (let index = 0; index < meta.chunk_count; index += 1) {
    $("#upload-status").textContent = `กำลังอัปโหลด ${file.name} · ${index + 1}/${meta.chunk_count}`;
    const chunk = await file.slice(index * meta.chunk_bytes, Math.min(file.size, (index + 1) * meta.chunk_bytes)).arrayBuffer();
    await api(`/api/files/${meta.id}/chunks/${index}`, { method: "PUT", body: chunk, headers: { "Content-Type": "application/octet-stream" } });
  }
  await api(`/api/files/${meta.id}/finish`, { method: "POST", body: "{}" });
}

function statusBadge(status) {
  const failed = ["failed", "cancelled"].includes(status);
  return element("span", `badge${failed ? " failed" : ""}`, status);
}

async function loadRuns() {
  const data = await api("/api/agent/runs");
  const list = $("#run-list"); list.replaceChildren();
  if (!data.runs.length) list.append(element("p", "muted", "ยังไม่มีงาน Agent"));
  let active = false;
  data.runs.forEach((run) => {
    if (!["completed", "failed", "needs_review", "cancelled"].includes(run.status)) active = true;
    const card = element("article", "item-card");
    card.append(element("h3", "", run.task), statusBadge(run.status));
    if (run.answer) card.append(element("p", "", run.answer));
    const actions = element("div", "item-actions");
    if (run.progress?.pull_request_url) {
      const link = element("a", "secondary", "เปิด Pull Request"); link.href = run.progress.pull_request_url; link.target = "_blank"; link.rel = "noopener"; actions.append(link);
    }
    if (["queued", "dispatching"].includes(run.status)) {
      const cancel = element("button", "danger", "ยกเลิก");
      cancel.addEventListener("click", async () => { await api(`/api/agent/runs/${run.run_id}/cancel`, { method: "POST", body: "{}" }); await loadRuns(); }); actions.append(cancel);
    }
    card.append(actions); list.append(card);
  });
  clearTimeout(runTimer);
  if (active) runTimer = setTimeout(() => loadRuns().catch(() => {}), 8000);
}

async function loadSessions() {
  const data = await api("/api/auth/sessions");
  const list = $("#session-list"); list.replaceChildren();
  data.sessions.forEach((session) => {
    const card = element("article", "item-card");
    card.append(element("h3", "", `${session.current ? "อุปกรณ์นี้ · " : ""}${session.device_label}`), element("p", "", `ใช้งานล่าสุด ${new Date(session.last_seen_at).toLocaleString("th-TH")}`));
    list.append(card);
  });
}

async function loadMfa() {
  const status = await api("/api/auth/mfa");
  $("#mfa-status").textContent = status.enabled
    ? `เปิดใช้งานแล้ว · มีรหัสกู้คืนเหลือ ${status.recovery_codes_remaining} รหัส`
    : status.pending ? "เริ่มตั้งค่าแล้ว แต่ยังไม่ได้ยืนยันรหัส" : "ยังไม่ได้เปิดใช้งาน";
  $("#mfa-setup").textContent = status.pending ? "สร้างรหัสตั้งค่าใหม่" : "เริ่มตั้งค่า MFA";
  $("#mfa-setup").disabled = Boolean(status.enabled);
  if (status.enabled) $("#mfa-enroll").classList.add("hidden");
}

async function loadOAuth() {
  const data = await api("/api/auth/oauth/providers");
  const list = $("#oauth-links"); list.replaceChildren();
  for (const provider of ["google", "github"]) {
    const state = data.providers?.[provider] || { configured: false, linked: false };
    const configured = typeof state === "boolean" ? state : Boolean(state.configured);
    const linked = typeof state === "object" && Boolean(state.linked);
    const card = element("article", "item-card");
    card.append(
      element("h3", "", provider === "google" ? "Google" : "GitHub"),
      element("p", "", linked ? "เชื่อมกับบัญชีนี้แล้ว" : configured ? "พร้อมให้เชื่อมต่อ" : "ยังไม่ได้ตั้งค่า Client ID และ Secret"),
    );
    if (configured) {
      const button = element("button", linked ? "danger" : "secondary", linked ? "ยกเลิกการเชื่อมต่อ" : "เชื่อมบัญชี");
      button.addEventListener("click", async () => {
        if (linked) {
          await api(`/api/auth/oauth/${provider}`, { method: "DELETE", body: "{}" });
          toast(`ยกเลิกการเชื่อมต่อ ${provider} แล้ว`);
          await loadOAuth();
          return;
        }
        const result = await api(`/api/auth/oauth/${provider}/link/start`, { method: "POST", body: "{}" });
        location.href = result.authorization_url;
      });
      card.append(button);
    }
    list.append(card);
  }
}

async function beginMfaSetup() {
  const data = await api("/api/auth/mfa/setup", { method: "POST", body: "{}" });
  $("#mfa-secret").value = data.secret;
  $("#mfa-confirm-code").value = "";
  $("#mfa-enroll").classList.remove("hidden");
  $("#mfa-recovery-wrap").classList.add("hidden");
  $("#mfa-confirm-code").focus();
  $("#mfa-status").textContent = "รอยืนยันรหัสจากแอป Authenticator";
}

async function enableMfa() {
  const code = $("#mfa-confirm-code").value.trim();
  if (!/^\d{6}$/.test(code)) throw new Error("กรอกรหัสยืนยัน 6 หลักจากแอป Authenticator");
  const data = await api("/api/auth/mfa/enable", { method: "POST", body: JSON.stringify({ code }) });
  $("#mfa-secret").value = "";
  $("#mfa-enroll").classList.add("hidden");
  $("#mfa-recovery").value = data.recovery_codes.join("\n");
  $("#mfa-recovery-wrap").classList.remove("hidden");
  toast("เปิดใช้งาน MFA แล้ว กรุณาเก็บรหัสกู้คืนทันที");
  await loadMfa();
}

async function loadImageStatus() {
  const status = await api("/api/images/status");
  $("#image-quota").textContent = status.quota_exempt ? "ผู้ดูแลระบบ · ไม่จำกัดจำนวนภาพ" : `เหลือ ${status.remaining_today}/${status.daily_limit} ภาพวันนี้`;
}

function compactMusicSummary(analysis) {
  if (!analysis || typeof analysis !== "object") return "ประมวลผลเสร็จแล้ว";
  const parts = [];
  const bpm = analysis.tempo?.bpm || analysis.tempo_bpm || analysis.bpm;
  const key = analysis.key?.name || analysis.key;
  if (bpm) parts.push(`Tempo ${Math.round(bpm)} BPM`);
  if (key) parts.push(`คีย์ ${key}`);
  if (Array.isArray(analysis.chords) && analysis.chords.length) {
    const chords = analysis.chords.slice(0, 8).map((item) => typeof item === "string" ? item : item.chord || item.name).filter(Boolean);
    if (chords.length) parts.push(`คอร์ด ${chords.join(" · ")}`);
  }
  if (Array.isArray(analysis.detected_parts) && analysis.detected_parts.length) {
    parts.push(`เครื่องดนตรี ${analysis.detected_parts.slice(0, 5).map((item) => item.name || item).join(" · ")}`);
  }
  if (analysis.advanced_music?.status === "completed") parts.push("Advanced AI: แยก stem และถอดโน้ตสำเร็จ");
  if (analysis.advanced_music?.status === "fallback") parts.push("Advanced AI ใช้ fallback · ผลพื้นฐานยังพร้อมใช้");
  return parts.join("\n") || "ประมวลผลเสร็จแล้ว พร้อมดาวน์โหลดผลลัพธ์";
}

function stemMixer(job, artifacts) {
  const labels = { vocals: "เสียงร้อง", drums: "กลอง", bass: "เบส", guitar: "กีตาร์", piano: "เปียโน", other: "เสียงอื่น" };
  const stems = Object.entries(labels).map(([stem, label]) => ({ stem, label, artifact: artifacts.get(`stem_${stem}`) })).filter((item) => item.artifact);
  if (!stems.length) return null;
  const mixer = element("section", "stem-mixer");
  mixer.append(element("strong", "", "มิกเซอร์ Stem · พรีวิวซิงก์กัน"), element("p", "muted", `พรีวิว ${job.analysis?.stem_separation?.preview_seconds || 20} วินาที · ปรับระดับเสียงแต่ละชิ้นได้`));
  const players = [];
  stems.forEach(({ stem, label, artifact }) => {
    const row = element("div", "stem-row");
    const audio = new Audio(artifact.url); audio.preload = "none";
    const volume = document.createElement("input"); volume.type = "range"; volume.min = "0"; volume.max = "1"; volume.step = "0.05"; volume.value = "1"; volume.setAttribute("aria-label", `ระดับเสียง ${label}`);
    volume.addEventListener("input", () => { audio.volume = Number(volume.value); });
    const mute = element("button", "secondary", "ปิดเสียง");
    mute.type = "button"; mute.addEventListener("click", () => { audio.muted = !audio.muted; mute.textContent = audio.muted ? "เปิดเสียง" : "ปิดเสียง"; });
    row.append(element("span", "stem-label", label), volume, mute); mixer.append(row); players.push(audio);
  });
  const controls = element("div", "item-actions");
  const play = element("button", "primary", "▶ เล่นพร้อมกัน"); play.type = "button";
  const stop = element("button", "secondary", "■ หยุด"); stop.type = "button";
  play.addEventListener("click", async () => {
    players.forEach((audio) => { audio.currentTime = 0; });
    try { await Promise.all(players.map((audio) => audio.play())); } catch { toast("เบราว์เซอร์ยังไม่อนุญาตให้เล่นเสียง โปรดลองกดอีกครั้ง"); }
  });
  stop.addEventListener("click", () => players.forEach((audio) => { audio.pause(); audio.currentTime = 0; }));
  controls.append(play, stop); mixer.append(controls); return mixer;
}

async function loadMusicJobs() {
  const data = await api("/api/music/jobs");
  const list = $("#music-list"); list.replaceChildren();
  if (!data.jobs.length) list.append(element("p", "muted", "ยังไม่มีงาน Music Lab"));
  let active = false;
  data.jobs.forEach((job) => {
    if (!["completed", "failed"].includes(job.status)) active = true;
    const card = element("article", "item-card");
    card.append(element("h3", "", job.file_name), statusBadge(job.status));
    if (job.analysis) card.append(element("p", "music-summary", compactMusicSummary(job.analysis)));
    if (job.error_detail) card.append(element("p", "error", job.error_detail));
    const actions = element("div", "item-actions");
    const artifacts = new Map((job.artifacts || []).map((artifact) => [artifact.kind, artifact]));
    (job.artifacts || []).filter((artifact) => !artifact.kind.startsWith("stem_") || artifact.kind === "stem_midi").forEach((artifact) => {
      const link = element("a", "secondary", `ดาวน์โหลด ${artifact.kind.toUpperCase()}`);
      link.href = artifact.url; link.download = artifact.file_name; actions.append(link);
    });
    card.append(actions); const mixer = stemMixer(job, artifacts); if (mixer) card.append(mixer); list.append(card);
  });
  clearTimeout(musicTimer);
  if (active) musicTimer = setTimeout(() => loadMusicJobs().catch(() => {}), 8_000);
}

function thaiUnits(value) {
  if (window.Intl?.Segmenter) return [...new Intl.Segmenter("th", { granularity: "word" }).segment(value)].map((item) => item.segment);
  return Array.from(value);
}

function wrapCanvasText(context, value, maximumWidth) {
  const lines = [];
  for (const paragraph of String(value || "").split(/\r?\n/)) {
    let line = "";
    for (const unit of thaiUnits(paragraph)) {
      const candidate = `${line}${unit}`;
      if (line && context.measureText(candidate).width > maximumWidth) {
        lines.push(line.trim());
        line = unit.trimStart();
      } else line = candidate;
    }
    if (line.trim()) lines.push(line.trim());
  }
  return lines.slice(0, 6);
}

async function imageBitmap(blob) {
  if (window.createImageBitmap) return createImageBitmap(blob);
  return new Promise((resolve, reject) => {
    const image = new Image();
    const url = URL.createObjectURL(blob);
    image.onload = () => { URL.revokeObjectURL(url); resolve(image); };
    image.onerror = () => { URL.revokeObjectURL(url); reject(new Error("เปิดภาพที่สร้างไม่สำเร็จ")); };
    image.src = url;
  });
}

async function renderGeneratedImage(blob, caption) {
  const canvas = $("#image-canvas");
  const context = canvas.getContext("2d");
  const source = await imageBitmap(blob);
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.drawImage(source, 0, 0, canvas.width, canvas.height);
  if (typeof source.close === "function") source.close();
  const cleanCaption = String(caption || "").trim();
  if (cleanCaption) {
    context.font = "700 58px 'Noto Sans Thai', 'Leelawadee UI', sans-serif";
    context.textBaseline = "top";
    const lines = wrapCanvasText(context, cleanCaption, 864);
    const lineHeight = 78;
    const height = lines.length * lineHeight + 76;
    const top = canvas.height - height - 54;
    context.fillStyle = "rgba(9, 12, 18, .76)";
    context.beginPath();
    context.roundRect(44, top, 936, height, 26);
    context.fill();
    context.fillStyle = "#ffffff";
    lines.forEach((line, index) => context.fillText(line, 80, top + 38 + index * lineHeight, 864));
  }
  canvas.classList.remove("hidden");
  $("#image-empty").classList.add("hidden");
  $("#image-actions").classList.remove("hidden");
}

async function generateImage() {
  const button = $("#generate-image");
  button.disabled = true;
  button.textContent = "กำลังสร้างภาพ…";
  try {
    const response = await fetch("/api/images/generate", {
      method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: $("#image-prompt").value, caption: $("#image-caption").value }),
    });
    if (response.status === 401) return location.replace("/login");
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `สร้างภาพไม่สำเร็จ (${response.status})`);
    }
    imageBlob = await response.blob();
    await renderGeneratedImage(imageBlob, $("#image-caption").value);
    const remaining = response.headers.get("X-Image-Remaining");
    $("#image-quota").textContent = remaining === "unlimited" ? "ผู้ดูแลระบบ · ไม่จำกัดจำนวนภาพ" : `เหลือ ${remaining} ภาพวันนี้`;
    toast("สร้างภาพเรียบร้อยแล้ว");
  } finally {
    button.disabled = false;
    button.textContent = "สร้างภาพ";
  }
}

function downloadBlob(blob, name) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1_000);
}

function canvasPng() {
  return new Promise((resolve, reject) => $("#image-canvas").toBlob((blob) => blob ? resolve(blob) : reject(new Error("เตรียมไฟล์ PNG ไม่สำเร็จ")), "image/png"));
}

function xmlText(value) {
  return String(value || "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&apos;");
}

async function blobDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("เตรียมไฟล์สำหรับ Canva ไม่สำเร็จ"));
    reader.readAsDataURL(blob);
  });
}

async function exportCanvaSvg() {
  if (!imageBlob) throw new Error("กรุณาสร้างภาพก่อน");
  const image = await blobDataUrl(imageBlob);
  const caption = String($("#image-caption").value || "").trim();
  const canvas = $("#image-canvas");
  const context = canvas.getContext("2d");
  context.font = "700 58px 'Noto Sans Thai', 'Leelawadee UI', sans-serif";
  const lines = caption ? wrapCanvasText(context, caption, 864) : [];
  const height = lines.length * 78 + 76;
  const top = 1024 - height - 54;
  const textNodes = lines.map((line, index) => `<text x="80" y="${top + 91 + index * 78}" fill="#fff" font-family="Noto Sans Thai,Leelawadee UI,sans-serif" font-size="58" font-weight="700">${xmlText(line)}</text>`).join("");
  const overlay = lines.length ? `<rect x="44" y="${top}" width="936" height="${height}" rx="26" fill="#090c12" fill-opacity=".76"/>${textNodes}` : "";
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024"><image href="${image}" width="1024" height="1024"/>${overlay}</svg>`;
  downloadBlob(new Blob([svg], { type: "image/svg+xml;charset=utf-8" }), "mycodex-canva.svg");
  toast("ส่งออก SVG สำหรับนำเข้า Canva แล้ว");
}

async function loadTraining() {
  if (account?.role !== "admin") return;
  const data = await api("/api/learning/overview");
  const summary = $("#training-summary");
  summary.replaceChildren();
  [["ตัวอย่าง", data.examples.length], ["โจทย์ประเมิน", data.evaluations.length]].forEach(([label, value]) => {
    const card = element("div", "stat-card"); card.append(element("strong", "", String(value)), element("span", "", label)); summary.append(card);
  });
  const list = $("#training-list"); list.replaceChildren();
  if (!data.examples.length) list.append(element("p", "muted", "ยังไม่มีตัวอย่างการตอบ"));
  data.examples.slice(0, 20).forEach((item) => {
    const card = element("article", "item-card");
    card.append(element("h3", "", item.instruction), element("p", "", item.ideal_response), element("span", "badge", (item.tags || []).join(" · ") || "ไม่มีแท็ก"));
    list.append(card);
  });
}

async function loadSystem() {
  if (account?.role !== "admin") return;
  const [overview, auditLog] = await Promise.all([api("/api/admin/overview"), api("/api/admin/audit")]);
  const counts = $("#system-counts"); counts.replaceChildren();
  const labels = { users: "ผู้ใช้", conversations: "แชท", messages: "ข้อความ", agent_runs: "งาน Agent", active_runs: "งานที่กำลังรัน", files: "ไฟล์", images_today: "ภาพวันนี้", training_examples: "ตัวอย่างฝึก", training_evaluations: "โจทย์ประเมิน", music_jobs: "งานเพลง" };
  Object.entries(labels).forEach(([key, label]) => { const card = element("div", "stat-card"); card.append(element("strong", "", String(overview.counts[key] || 0)), element("span", "", label)); counts.append(card); });
  const capabilities = $("#capability-list"); capabilities.replaceChildren();
  overview.capabilities.forEach((item) => {
    const card = element("article", "item-card capability-card");
    const ready = !["remote-worker-required", "configuration-required"].includes(item.state);
    const stateLabel = item.state === "cloud-runner" ? "พร้อมผ่าน GitHub Runner" : item.state === "configuration-required" ? "รอตั้งค่า Client ID / Secret" : ready ? "พร้อมบน Cloud" : "ต้องเชื่อม Remote Worker";
    card.append(element("h3", "", item.label), element("span", `badge${ready ? "" : " warning"}`, stateLabel));
    capabilities.append(card);
  });
  $("#music-worker-state").textContent = overview.remote_worker.status;
  const auditList = $("#audit-list"); auditList.replaceChildren();
  auditLog.events.forEach((item) => {
    const card = element("article", "item-card");
    card.append(element("h3", "", `${item.kind} · ${item.outcome}`), element("p", "", `${item.username || "system"} · ${new Date(item.created_at * 1000).toLocaleString("th-TH")}`), element("p", "", item.detail));
    auditList.append(card);
  });
}

async function boot() {
  account = await api("/api/auth/me");
  $("#account-name").textContent = `@${account.username}`;
  $("#account-role").textContent = account.role === "admin" ? "ผู้ดูแลระบบ" : "ผู้ใช้ทั่วไป";
  if (account.role === "admin") $$(".admin-only").forEach((node) => node.classList.remove("hidden"));
  const status = await api("/api/cloud/status");
  $("#cloud-state").textContent = status.agent_configured ? "Cloudflare · Agent พร้อม" : "Cloudflare · ต้องเชื่อม GitHub";
  await Promise.all([loadHistory(), loadFiles(), loadImageStatus()]);
  const query = new URLSearchParams(location.search);
  if (query.get("oauth_success") === "linked") toast("เชื่อมบัญชี Social Login แล้ว");
  if (query.get("oauth_success") === "login") toast("เข้าสู่ระบบด้วย Social Login แล้ว");
  if (query.get("oauth_error")) toast("เชื่อมบัญชี Social Login ไม่สำเร็จหรือบัญชีนี้ถูกใช้งานแล้ว");
  if (query.has("oauth_success") || query.has("oauth_error")) history.replaceState(null, "", location.pathname);
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
}

$("#open-sidebar").addEventListener("click", openSidebar); $("#close-sidebar").addEventListener("click", closeSidebar); $("#backdrop").addEventListener("click", closeSidebar);
$$(".nav-item").forEach((node) => node.addEventListener("click", () => showView(node.dataset.view)));
$("#refresh-history").addEventListener("click", () => loadConversations().catch((error) => toast(error.message)));
$("#refresh-files").addEventListener("click", () => loadFiles().catch((error) => toast(error.message)));
$("#refresh-runs").addEventListener("click", () => loadRuns().catch((error) => toast(error.message)));
$("#new-chat").addEventListener("click", async () => { const data = await api("/api/chat/conversations", { method: "POST", body: "{}" }); await loadHistory(data.id); showView("chat"); });
$("#composer").addEventListener("submit", async (event) => { event.preventDefault(); const input = $("#message-input"); const message = input.value.trim(); if (!message) return; input.value = ""; input.disabled = true; try { await sendMessage(message); } catch (error) { toast(error.message); } finally { input.disabled = false; input.focus(); } });
$("#message-input").addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); $("#composer").requestSubmit(); } });
$("#voice-input").addEventListener("click", listenThai);
$("#file-picker").addEventListener("change", async (event) => { try { for (const file of event.target.files) await uploadFile(file); $("#upload-status").textContent = "อัปโหลดเรียบร้อย"; await loadFiles(); } catch (error) { toast(error.message); } finally { event.target.value = ""; } });
$("#agent-form").addEventListener("submit", async (event) => { event.preventDefault(); const attachments = $$("#agent-files input:checked").map((node) => node.value); try { await api("/api/agent/runs", { method: "POST", body: JSON.stringify({ task: $("#agent-task").value, mode: $("#agent-mode").value, attachments }) }); $("#agent-task").value = ""; toast("ส่งงานเข้าคิวแล้ว"); await loadRuns(); } catch (error) { toast(error.message); } });
$("#image-form").addEventListener("submit", async (event) => { event.preventDefault(); try { await generateImage(); } catch (error) { toast(error.message); } });
$("#music-form").addEventListener("submit", async (event) => { event.preventDefault(); const button = $("#start-music"); button.disabled = true; try { await api("/api/music/jobs", { method: "POST", body: JSON.stringify({ file_id: $("#music-file").value }) }); toast("ส่งงาน Music Lab เข้าคิวแล้ว"); await loadMusicJobs(); } catch (error) { toast(error.message); } finally { button.disabled = false; } });
$("#refresh-music").addEventListener("click", () => loadMusicJobs().catch((error) => toast(error.message)));
$("#download-image").addEventListener("click", async () => { try { downloadBlob(await canvasPng(), "mycodex-image.png"); } catch (error) { toast(error.message); } });
$("#export-canva").addEventListener("click", () => exportCanvaSvg().catch((error) => toast(error.message)));
$("#training-example-form").addEventListener("submit", async (event) => { event.preventDefault(); try { await api("/api/learning/examples", { method: "POST", body: JSON.stringify({ instruction: $("#training-instruction").value, ideal_response: $("#training-response").value, tags: $("#training-tags").value.split(",").map((item) => item.trim()).filter(Boolean) }) }); event.target.reset(); toast("บันทึกตัวอย่างแล้ว"); await loadTraining(); } catch (error) { toast(error.message); } });
$("#training-evaluation-form").addEventListener("submit", async (event) => { event.preventDefault(); try { await api("/api/learning/evaluations", { method: "POST", body: JSON.stringify({ prompt: $("#evaluation-prompt").value, expected: $("#evaluation-expected").value }) }); event.target.reset(); toast("บันทึกโจทย์ประเมินแล้ว"); await loadTraining(); } catch (error) { toast(error.message); } });
$("#refresh-training").addEventListener("click", () => loadTraining().catch((error) => toast(error.message)));
$("#export-training").addEventListener("click", () => { location.href = "/api/learning/export"; });
$("#refresh-system").addEventListener("click", () => loadSystem().catch((error) => toast(error.message)));
$("#create-invite").addEventListener("click", async () => { try { const data = await api("/api/auth/invites", { method: "POST", body: JSON.stringify({ role: $("#invite-role").value }) }); $("#invite-result").value = `${location.origin}/login?invite=${encodeURIComponent(data.token)}`; } catch (error) { toast(error.message); } });
$("#mfa-setup").addEventListener("click", () => beginMfaSetup().catch((error) => toast(error.message)));
$("#mfa-enable").addEventListener("click", () => enableMfa().catch((error) => toast(error.message)));
$("#revoke-sessions").addEventListener("click", async () => { await api("/api/auth/sessions/revoke-others", { method: "POST", body: "{}" }); toast("ออกจากระบบอุปกรณ์อื่นแล้ว"); await loadSessions(); });
$("#logout").addEventListener("click", async () => { await api("/api/auth/logout", { method: "POST", body: "{}" }); location.replace("/login"); });

boot().catch((error) => toast(error.message));
