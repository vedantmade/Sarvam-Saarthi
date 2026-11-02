// Sarthi front end: rural voice assistant (voice agent, recording, chat, TTS playback, documents, PWA).
const $ = (id) => document.getElementById(id);
let sessionId = null;

async function api(path, options = {}) {
  const res = await fetch(path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || data.detail || `Request failed (${res.status})`);
  return data;
}

// ---------------------------------------------------------------- setup
async function init() {
  const cfg = await api("/api/config");
  if (!cfg.key_configured) $("keyWarning").classList.remove("hidden");
  $("language").innerHTML = cfg.languages
    .map((l) => `<option value="${l.code}">${l.native} (${l.name})</option>`).join("");
  $("docType").innerHTML = cfg.doc_types.map((d) => `<option>${d}</option>`).join("");
  ttsLangs = new Set(cfg.languages.filter((l) => l.tts).map((l) => l.code));
  $("docType").onchange();
}
let ttsLangs = new Set();

function addMsg(text, who, speakable = false) {
  const div = document.createElement("div");
  div.className = `msg ${who}`;
  div.textContent = text;
  if (speakable) {
    const b = document.createElement("button");
    b.className = "speak"; b.textContent = "🔊 Listen";
    b.onclick = () => {
      // Replay: pause the agent's mic so it doesn't hear (and answer) the replay itself.
      if (agentOn) { agentSession++; agentListening = false; }
      speak(text, { resumeAgent: true });
    };
    div.appendChild(document.createElement("br"));
    div.appendChild(b);
  }
  $("messages").appendChild(div);
  $("messages").scrollTop = $("messages").scrollHeight;
  return div;
}

// ---------------------------------------------------------------- document
$("uploadBtn").onclick = async () => {
  const fd = new FormData();
  const file = $("fileInput").files[0];
  if (file) fd.append("file", file);
  fd.append("text", $("pasteText").value);
  if (sessionId) fd.append("session_id", sessionId);
  $("docStatus").textContent = "Reading document...";
  try {
    const out = await api("/api/upload", { method: "POST", body: fd });
    sessionId = out.session_id;
    $("docStatus").textContent = `✅ Loaded "${out.doc_name}" (${out.chars} characters).`;
    $("explainBtn").disabled = false;
  } catch (e) {
    $("docStatus").textContent = "⚠️ " + e.message;
  }
};

$("explainBtn").onclick = () => sendChat("📄 Explain my document", true);

// Groundwater mode answers from built-in CGWB data, so no document is needed.
$("docType").onchange = () => {
  const topic = $("docType").value;
  const gw = topic === "Groundwater";
  $("textInput").placeholder = topic === "Rural Assistant"
    ? "Ask about crops, schemes, water or documents…"
    : gw ? "Ask about groundwater, e.g. Which states are over-exploited?" : "Ask about your document…";
  $("docTools").classList.toggle("hidden", gw); // groundwater uses built-in data
  $("docStatus").textContent = gw ? "💧 Groundwater uses built-in CGWB data. No upload needed."
    : topic === "Rural Assistant" ? "Optional: upload a form or letter and Sarthi will explain it." : "";
};

// Colour a figure by groundwater status when it is a stage-of-development percentage.
function statusClass(value) {
  const m = String(value).match(/(\d+(?:\.\d+)?)\s*%/);
  if (!m) return "";
  const p = parseFloat(m[1]);
  return p > 100 ? "over" : p >= 90 ? "critical" : p >= 70 ? "semi" : "safe";
}

// Suggested questions
document.querySelectorAll("#chips .chip").forEach((c) => {
  c.onclick = () => { $("docType").value = "Rural Assistant"; $("docType").onchange(); sendChat(c.textContent); };
});

// Voice-agent label follows the status line (listening / understanding / speaking).
new MutationObserver(() => {
  const t = $("micStatus").textContent;
  $("agentLabel").textContent = !agentOn ? "Tap to talk"
    : /Understanding/.test(t) ? "Understanding…"
    : currentAudio && !currentAudio.paused ? "Speaking… (talk to interrupt)"
    : "Listening…";
}).observe($("micStatus"), { childList: true, characterData: true, subtree: true });

// ---------------------------------------------------------------- chat
let chatSeq = 0; // only the newest question's answer is shown/spoken
async function sendChat(text, explain = false) {
  if (!text.trim()) return;
  const mySeq = ++chatSeq;
  stopAudio(); // a new question silences any answer still playing
  addMsg(text, "user");
  const thinking = addMsg("Sarthi is thinking", "bot thinking");
  try {
    const out = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId, message: text, explain,
        language_code: $("language").value, doc_type: $("docType").value,
      }),
    });
    sessionId = out.session_id;
    thinking.remove();
    const msg = addMsg(out.reply, "bot", true);
    const latest = mySeq === chatSeq; // a newer question was asked meanwhile -> don't speak this one
    if (out.skill) { // which skill answered (Rural Assistant routes automatically)
      const tag = document.createElement("div");
      tag.className = "skill";
      tag.textContent = out.skill === "groundwater" ? "💧 Groundwater data (CGWB)" : "🌾 Rural assistant";
      msg.prepend(tag);
    }
    if (out.map_data && out.map_data.length) {
      // Groundwater answers: show the state-wise figures under the reply (not spoken).
      const list = document.createElement("div");
      list.className = "mapdata";
      for (const item of out.map_data) {
        for (const [place, value] of Object.entries(item)) {
          const card = document.createElement("div");
          card.className = "stat " + statusClass(value);
          const b = document.createElement("b"); b.textContent = place;
          const s = document.createElement("span"); s.textContent = value;
          card.append(b, s);
          list.appendChild(card);
        }
      }
      msg.appendChild(list);
    }
    if (latest && $("autoSpeak").checked) await speak(out.reply, { resumeAgent: true });
    else if (latest) resumeAgent();
  } catch (e) {
    thinking.remove();
    addMsg("⚠️ " + e.message, "bot");
    if (mySeq === chatSeq) resumeAgent();
  }
}

$("chatForm").onsubmit = (e) => {
  e.preventDefault();
  const t = $("textInput").value;
  $("textInput").value = "";
  sendChat(t);
};

// ---------------------------------------------------------------- text to speech
// One voice at a time: every speak() call takes a new token; starting a new one (or stopAudio)
// invalidates older calls, so they never start playing after their audio arrives.
let currentAudio = null, speakToken = 0, finishClip = null;

function stopAudio() {
  speakToken++;
  if (currentAudio) { currentAudio.pause(); currentAudio = null; }
  if (finishClip) { finishClip(); finishClip = null; } // release the waiting playback loop
}

async function speak(text, { resumeAgent: resume = false } = {}) {
  stopAudio();
  const token = speakToken;
  if (!ttsLangs.has($("language").value)) {
    $("micStatus").textContent = "🔇 Voice output is not available for this language yet; showing text.";
    if (resume) setTimeout(resumeAgent, 300);
    return;
  }
  try {
    const out = await api("/api/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, language_code: $("language").value }),
    });
    for (const b64 of out.audios) {
      if (token !== speakToken) return; // superseded or interrupted: stay silent
      await new Promise((resolve) => {
        finishClip = resolve;
        currentAudio = new Audio("data:audio/wav;base64," + b64);
        currentAudio.onended = resolve;
        currentAudio.onerror = resolve;
        currentAudio.play().catch(resolve);
      });
    }
  } catch (e) {
    $("micStatus").textContent = "🔇 Could not play audio: " + e.message;
  }
  if (token !== speakToken) return;
  currentAudio = null; finishClip = null;
  if (resume) resumeAgent(); // voice agent: listen again only after its own answer
}

// ---------------------------------------------------------------- voice agent (hands-free)
// Tap 🗣️ once: the agent listens, ends the turn on ~1.2 s of silence, answers aloud,
// and listens again. Speaking while it talks interrupts it (barge-in).
let agentOn = false, agentStream = null, agentListening = false, agentSession = 0;

function resumeAgent() { if (agentOn) agentListen(); }

async function agentListen() {
  if (!agentOn || agentListening) return; // never run two listeners at once
  agentListening = true;
  const session = agentSession;
  agentStream = agentStream || (await navigator.mediaDevices.getUserMedia({ audio: true }));
  if (!agentOn || session !== agentSession) { agentListening = false; return; }
  const ctx = new AudioContext();
  const analyser = ctx.createAnalyser();
  ctx.createMediaStreamSource(agentStream).connect(analyser);
  const buf = new Uint8Array(analyser.fftSize);
  const rec = new MediaRecorder(agentStream);
  const parts = [];
  let spoke = false, lastVoice = Date.now(), started = Date.now();
  rec.ondataavailable = (e) => parts.push(e.data);
  rec.onstop = async () => {
    ctx.close();
    agentListening = false;
    if (!agentOn || session !== agentSession) return;
    if (!spoke) return agentListen();
    $("micStatus").textContent = "Understanding your voice...";
    try {
      const fd = new FormData();
      fd.append("audio", await toWav(new Blob(parts)), "speech.wav");
      fd.append("language_code", "unknown");
      const out = await api("/api/transcribe", { method: "POST", body: fd });
      if (!agentOn || session !== agentSession) return;
      const sel = $("language");
      if (out.language_code && [...sel.options].some((o) => o.value === out.language_code)) sel.value = out.language_code;
      if (out.transcript) { $("autoSpeak").checked = true; await sendChat(out.transcript); } // resumes listening after the answer
      else agentListen();
    } catch (e) { $("micStatus").textContent = "⚠️ " + e.message; agentListen(); }
  };
  rec.start();
  $("micStatus").textContent = "🗣️ Listening... just speak.";
  const tick = () => {
    if (rec.state !== "recording") return;
    analyser.getByteTimeDomainData(buf);
    const level = Math.max(...buf.map((v) => Math.abs(v - 128)));
    if (level > 12) { spoke = true; lastVoice = Date.now(); }
    if ((spoke && Date.now() - lastVoice > 1200) || Date.now() - started > 25000 || !agentOn || session !== agentSession) rec.stop();
    else requestAnimationFrame(tick);
  };
  tick();
}

// Barge-in: while the agent is speaking, watch the mic and stop playback if the user talks.
setInterval(async () => {
  if (!agentOn || !agentStream || !currentAudio || currentAudio.paused) return;
  const ctx = new AudioContext(), an = ctx.createAnalyser();
  ctx.createMediaStreamSource(agentStream).connect(an);
  await new Promise((r) => setTimeout(r, 150));
  const b = new Uint8Array(an.fftSize); an.getByteTimeDomainData(b); ctx.close();
  if (currentAudio && Math.max(...b.map((v) => Math.abs(v - 128))) > 40) { stopAudio(); resumeAgent(); } // user barged in
}, 400);

$("agentBtn").onclick = async () => {
  agentOn = !agentOn;
  agentSession++; // ends any listener from a previous on/off cycle
  agentListening = false;
  $("agentBtn").classList.toggle("recording", agentOn);
  $("agentBtn").querySelector(".orb-icon").textContent = agentOn ? "⏹" : "🎙️";
  $("agentLabel").textContent = agentOn ? "Listening…" : "Tap to talk";
  if (agentOn) agentListen();
  else {
    stopAudio();
    if (agentStream) { agentStream.getTracks().forEach((t) => t.stop()); agentStream = null; }
    $("micStatus").textContent = "";
  }
};

// ---------------------------------------------------------------- microphone
let recorder = null, chunks = [];

$("micBtn").onclick = async () => {
  if (recorder && recorder.state === "recording") { recorder.stop(); return; }
  stopAudio(); // don't record the assistant's own voice
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    chunks = [];
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (e) => chunks.push(e.data);
    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      $("micBtn").classList.remove("recording");
      $("micStatus").textContent = "Understanding your voice...";
      try {
        const wav = await toWav(new Blob(chunks));
        const fd = new FormData();
        fd.append("audio", wav, "speech.wav");
        fd.append("language_code", "unknown"); // let Saarika auto-detect
        const out = await api("/api/transcribe", { method: "POST", body: fd });
        $("micStatus").textContent = out.language_code ? `Heard (${out.language_code})` : "";
        const sel = $("language");
        if (out.language_code && [...sel.options].some((o) => o.value === out.language_code)) {
          sel.value = out.language_code; // answer in the language the user spoke
        }
        if (out.transcript) sendChat(out.transcript);
        else $("micStatus").textContent = "Could not hear anything. Please try again.";
      } catch (e) {
        $("micStatus").textContent = "⚠️ " + e.message;
      }
    };
    recorder.start();
    $("micBtn").classList.add("recording");
    $("micStatus").textContent = "Listening... tap 🎤 again to stop.";
  } catch (e) {
    $("micStatus").textContent = "⚠️ Microphone not available: " + e.message;
  }
};

// Convert any recorded audio blob into 16 kHz mono 16-bit WAV, which Sarvam STT accepts reliably.
async function toWav(blob) {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const decoded = await ctx.decodeAudioData(await blob.arrayBuffer());
  const rate = 16000;
  const offline = new OfflineAudioContext(1, Math.ceil(decoded.duration * rate), rate);
  const src = offline.createBufferSource();
  src.buffer = decoded; src.connect(offline.destination); src.start();
  const samples = (await offline.startRendering()).getChannelData(0);
  ctx.close();

  const buf = new ArrayBuffer(44 + samples.length * 2);
  const v = new DataView(buf);
  const str = (o, s) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
  str(0, "RIFF"); v.setUint32(4, 36 + samples.length * 2, true); str(8, "WAVE");
  str(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  str(36, "data"); v.setUint32(40, samples.length * 2, true);
  samples.forEach((s, i) => v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, s)) * 0x7fff, true));
  return new Blob([v], { type: "audio/wav" });
}

// ---------------------------------------------------------------- installable app (PWA / Android WebAPK)
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js");
let installEvt = null;
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault(); installEvt = e; $("installBtn").classList.remove("hidden");
});
$("installBtn").onclick = async () => {
  if (!installEvt) return;
  installEvt.prompt(); await installEvt.userChoice; installEvt = null; $("installBtn").classList.add("hidden");
};

init();
