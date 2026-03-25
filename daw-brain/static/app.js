// === Element Definitions ===
const ELEMENT_DEFS = {
  kick:        { label: "Kick",        group: "drums",   desc: "Four-on-the-floor patterns, ghost kicks, missing kick variations" },
  clap:        { label: "Clap/Snare",  group: "drums",   desc: "Backbeat patterns, ghost claps, layering specs" },
  hats:        { label: "Hats",        group: "drums",   desc: "Open/closed hat patterns, swing, groove" },
  perc:        { label: "Percussion",  group: "drums",   desc: "Congas, bongos, rimshots, shakers, rides" },
  toploop:     { label: "Top Loops",   group: "drums",   desc: "Audio loop selection, filtering, processing" },
  sub:         { label: "Sub Bass",    group: "bass",    desc: "Sine wave sub layer, mono, sidechain settings" },
  midbass:     { label: "Mid Bass",    group: "bass",    desc: "Character bass — Serum patch, filter envelope, rhythm" },
  stabs:       { label: "Stabs",       group: "melodic", desc: "Chord stabs, pluck sounds, rhythmic patterns" },
  lead:        { label: "Lead",        group: "melodic", desc: "Melodic hooks, riffs, arpeggiated patterns" },
  chords:      { label: "Chords",      group: "melodic", desc: "Chord progressions, pad voicings" },
  pad:         { label: "Pad",         group: "melodic", desc: "Atmospheric layers, evolving textures" },
  arps:        { label: "Arps",        group: "melodic", desc: "Arpeggiated synth patterns, sequenced melodic movement" },
  plucks:      { label: "Plucks",      group: "melodic", desc: "Short, percussive single-note melodic hits" },
  mainvox:     { label: "Main Vocal",  group: "vocals",  desc: "Full vocal arrangement, processing chain" },
  chops:       { label: "Chops",       group: "vocals",  desc: "Chopped vocal patterns, Simpler workflow" },
  hook:        { label: "Hook",        group: "vocals",  desc: "Short vocal phrases, one-shot vocal hits" },
  adlibs:      { label: "Ad-libs",    group: "vocals",  desc: "One-shot vocal hits, shouts, breaths, exclamations" },
  risers:      { label: "Risers",      group: "fx",      desc: "White noise sweeps, pitched risers" },
  downlifters: { label: "Downlifters", group: "fx",      desc: "Reverse risers, descending effects" },
  impacts:     { label: "Impacts",     group: "fx",      desc: "Hit sounds for drop moments" },
  sweeps:      { label: "Sweeps",      group: "fx",      desc: "Filter sweeps, noise textures" },
  transitions: { label: "Transitions", group: "fx",      desc: "Reverse cymbals, fills, tape stops" },
  textures:    { label: "Textures",    group: "fx",      desc: "Ambient atmospheres, vinyl noise, background washes" },
};

// === Session State ===
const sessionState = {
  bpm: 128,
  key: "E",
  scale: "minor",
  genre: "tech_house",
  spotifyProfile: null,
  skillLevel: localStorage.getItem("daw-brain-skill-level") || "expert",

  elements: {},
  activeElement: null,
  activeChatTab: "element",  // "element" or "general"

  // General chat (not tied to element)
  generalMessages: [],
  generalOutputs: [],

  presets: [],
  loading: false,
};

// Initialize all elements
Object.keys(ELEMENT_DEFS).forEach((id) => {
  sessionState.elements[id] = {
    status: "empty",       // empty | in_progress | complete | locked
    chatHistory: [],       // messages array for API
    outputs: [],           // generated outputs for this element
    summary: "",           // brief summary of what was generated
  };
});

// === DOM Refs ===
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const chatMessages = $("#chat-messages");
const chatInput = $("#chat-input");
const sendBtn = $("#send-btn");
const generalChatMessages = $("#general-chat-messages");
const generalChatInput = $("#general-chat-input");
const generalSendBtn = $("#general-send-btn");
const genreSelect = $("#genre");
const genreDesc = $("#genre-desc");
const outputList = $("#output-list");
const elementTabLabel = $("#element-tab-label");
const trackCount = $("#track-count");

// === Theme Toggle ===
const themeToggle = $("#theme-toggle");
themeToggle.addEventListener("click", () => {
  const next = document.body.dataset.theme === "dark" ? "light" : "dark";
  document.body.dataset.theme = next;
  localStorage.setItem("daw-brain-theme", next);
  // Re-render MIDI previews for new theme colors
  document.querySelectorAll(".midi-preview").forEach((canvas) => {
    if (canvas._midiNotes) renderMidiPreview(canvas._midiNotes, canvas);
  });
});

function getCSSVar(name) {
  return getComputedStyle(document.body).getPropertyValue(name).trim();
}

// === Session Persistence ===
const STORAGE_KEY = "dawbrain_session";
let _saveTimeout = null;
let _sessionReady = false;

function saveSession() {
  if (!_sessionReady) return;
  clearTimeout(_saveTimeout);
  _saveTimeout = setTimeout(() => {
    try {
      const data = {
        version: 1,
        bpm: parseInt($("#bpm").value) || 128,
        key: $("#key").value,
        scale: $("#scale").value,
        genre: genreSelect.value,
        skillLevel: sessionState.skillLevel,
        activeElement: sessionState.activeElement,
        activeChatTab: sessionState.activeChatTab,
        elements: sessionState.elements,
        generalMessages: sessionState.generalMessages,
        generalOutputs: sessionState.generalOutputs,
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (e) {
      // localStorage full or unavailable — fail silently
    }
  }, 500);
}

function loadSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data || typeof data !== "object" || !data.elements) return null;

    // Restore session settings to DOM
    if (data.bpm) $("#bpm").value = data.bpm;
    if (data.key) $("#key").value = data.key;
    if (data.scale) $("#scale").value = data.scale;

    // Restore skill level
    if (data.skillLevel) {
      sessionState.skillLevel = data.skillLevel;
      localStorage.setItem("daw-brain-skill-level", data.skillLevel);
      $$("#skill-level-pills .skill-pill").forEach((pill) => {
        pill.classList.toggle("active", pill.dataset.level === data.skillLevel);
      });
    }

    // Restore elements
    Object.keys(data.elements).forEach((id) => {
      if (sessionState.elements[id] && data.elements[id]) {
        const saved = data.elements[id];
        sessionState.elements[id] = {
          status: saved.status || "empty",
          chatHistory: Array.isArray(saved.chatHistory) ? saved.chatHistory : [],
          outputs: Array.isArray(saved.outputs) ? saved.outputs : [],
          summary: saved.summary || "",
        };
        updateElementStatus(id);
      }
    });

    // Restore general chat
    if (Array.isArray(data.generalMessages)) sessionState.generalMessages = data.generalMessages;
    if (Array.isArray(data.generalOutputs)) sessionState.generalOutputs = data.generalOutputs;

    // Render output list
    renderOutputList();

    // Render general chat messages
    if (sessionState.generalMessages.length > 0) {
      const starters = generalChatMessages.querySelector(".starter-prompts");
      if (starters) starters.classList.add("hidden");
      sessionState.generalMessages.forEach((msg) => {
        appendMessageToContainer(
          generalChatMessages, msg.role, msg.content,
          msg._outputData || null, msg._fileUrl || null
        );
      });
    }

    // Restore active element and chat tab
    if (data.activeElement && ELEMENT_DEFS[data.activeElement]) {
      selectElement(data.activeElement);
    }
    if (data.activeChatTab) switchChatTab(data.activeChatTab);

    return { genre: data.genre };
  } catch (e) {
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

function clearSession() {
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem("daw-brain-skill-level");
  location.reload();
}

// === HTML Sanitization ===
function escapeHtml(str) {
  const div = document.createElement("div");
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

const TYPE_LABELS = { parameters: "CHAIN", arrangement: "MAP", midi: "MIDI" };
function getTypeLabel(type) { return TYPE_LABELS[type] || "MIDI"; }

// === Client-side MIDI File Generation ===
function generateMidiBlob(notes, bpm) {
  const ppq = 480;
  function writeVLQ(value) {
    if (value < 0) value = 0;
    const bytes = [];
    bytes.push(value & 0x7f);
    value >>= 7;
    while (value > 0) {
      bytes.push((value & 0x7f) | 0x80);
      value >>= 7;
    }
    return bytes.reverse();
  }

  const trackEvents = [];
  const uspb = Math.round(60000000 / bpm);
  trackEvents.push({
    tick: 0,
    data: [0xff, 0x51, 0x03, (uspb >> 16) & 0xff, (uspb >> 8) & 0xff, uspb & 0xff],
  });

  notes.forEach((n) => {
    const startTick = Math.round((n.start - 1) * ppq);
    const durTick = Math.round((n.duration || 0.25) * ppq);
    const vel = Math.max(1, Math.min(127, n.velocity || 100));
    const pitch = Math.max(0, Math.min(127, n.pitch));
    trackEvents.push({ tick: startTick, data: [0x90, pitch, vel] });
    trackEvents.push({ tick: startTick + durTick, data: [0x80, pitch, 0] });
  });

  trackEvents.sort((a, b) => a.tick - b.tick || (a.data[0] === 0x80 ? -1 : 1));

  const trackBytes = [];
  let lastTick = 0;
  trackEvents.forEach((e) => {
    const delta = Math.max(0, e.tick - lastTick);
    lastTick = e.tick;
    trackBytes.push(...writeVLQ(delta));
    trackBytes.push(...e.data);
  });
  trackBytes.push(0x00, 0xff, 0x2f, 0x00);

  const file = [
    0x4d, 0x54, 0x68, 0x64, 0x00, 0x00, 0x00, 0x06,
    0x00, 0x00, 0x00, 0x01, (ppq >> 8) & 0xff, ppq & 0xff,
    0x4d, 0x54, 0x72, 0x6b,
  ];
  const len = trackBytes.length;
  file.push((len >> 24) & 0xff, (len >> 16) & 0xff, (len >> 8) & 0xff, len & 0xff);
  file.push(...trackBytes);

  return new Blob([new Uint8Array(file)], { type: "audio/midi" });
}

function downloadMidiFromNotes(outputData, bpm) {
  const blob = generateMidiBlob(outputData.notes, bpm);
  const name = (outputData.name || "output").replace(/\.mid$/, "") + ".mid";
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// === Skill Level Toggle ===
(function initSkillLevel() {
  const pills = $$("#skill-level-pills .skill-pill");
  // Restore from state (which already read localStorage)
  pills.forEach((pill) => {
    pill.classList.toggle("active", pill.dataset.level === sessionState.skillLevel);
    pill.addEventListener("click", () => {
      pills.forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      sessionState.skillLevel = pill.dataset.level;
      localStorage.setItem("daw-brain-skill-level", pill.dataset.level);
      saveSession();
    });
  });
})();

// === Session Helpers ===
function getSession() {
  return {
    bpm: parseInt($("#bpm").value) || 128,
    key: $("#key").value,
    scale: $("#scale").value,
  };
}

function getGenre() {
  return genreSelect.value || "tech_house";
}

// === Presets ===
async function loadPresets() {
  try {
    sessionState.presets = await API.getPresets();
    genreSelect.innerHTML = sessionState.presets
      .map((p) => `<option value="${p.id}">${p.label}</option>`)
      .join("");
    updatePresetDesc();
  } catch (e) {
    genreSelect.innerHTML = '<option value="tech_house">Tech House</option>';
  }
}

function updatePresetDesc() {
  const preset = sessionState.presets.find((p) => p.id === genreSelect.value);
  genreDesc.textContent = preset ? preset.description : "";
}

genreSelect.addEventListener("change", updatePresetDesc);

// === Track Count ===
function updateTrackCount() {
  const total = Object.keys(ELEMENT_DEFS).length;
  const built = Object.values(sessionState.elements).filter(
    (e) => e.status === "complete"
  ).length;
  trackCount.textContent = `${built}/${total} elements built`;
}

// === Element Selection ===
function selectElement(elementId) {
  if (!ELEMENT_DEFS[elementId]) return;

  // Deselect previous
  $$(".element-card.active").forEach((el) => el.classList.remove("active"));

  // Select new
  sessionState.activeElement = elementId;
  const card = $(`.element-card[data-element="${elementId}"]`);
  if (card) card.classList.add("active");

  // Switch to element tab
  switchChatTab("element");

  // Update tab label
  const def = ELEMENT_DEFS[elementId];
  elementTabLabel.textContent = `Working on: ${def.label}`;

  // Render chat history for this element
  renderElementChat(elementId);

  // Focus input
  chatInput.focus();
  saveSession();
}

function updateElementStatus(elementId) {
  const elem = sessionState.elements[elementId];
  const statusEl = $(`.element-card[data-element="${elementId}"] .element-status`);
  if (statusEl) {
    statusEl.setAttribute("data-status", elem.status);
  }
  updateTrackCount();
}

function markElementDownloaded(elementId) {
  if (!elementId || !sessionState.elements[elementId]) return;
  const elem = sessionState.elements[elementId];
  if (elem.status !== "complete") {
    elem.status = "complete";
    updateElementStatus(elementId);
    saveSession();
  }
}

// === Chat Tab Switching ===
function switchChatTab(tab) {
  sessionState.activeChatTab = tab;
  $$(".chat-tab").forEach((t) => t.classList.remove("active"));
  $(`.chat-tab[data-chat-tab="${tab}"]`).classList.add("active");

  $("#element-chat-panel").classList.toggle("active", tab === "element");
  $("#general-chat-panel").classList.toggle("active", tab === "general");

  if (tab === "general") {
    generalChatInput.focus();
  } else {
    chatInput.focus();
  }
}

$$(".chat-tab").forEach((tab) => {
  tab.addEventListener("click", () => switchChatTab(tab.dataset.chatTab));
});

// === Element Card Click Handlers ===
$$(".element-card").forEach((card) => {
  card.addEventListener("click", () => {
    selectElement(card.dataset.element);
  });
});

// === Render Element Chat ===
function renderElementChat(elementId) {
  const elem = sessionState.elements[elementId];
  const def = ELEMENT_DEFS[elementId];

  chatMessages.innerHTML = "";

  if (elem.chatHistory.length === 0) {
    // Show element-specific starter
    chatMessages.innerHTML = `
      <div class="starter-prompts">
        <div class="element-context-header ${def.group}">
          ${def.label}
        </div>
        <p class="starter-hint">${def.desc}</p>
        <div class="starter-prompt" data-prompt="Give me a ${def.label.toLowerCase()} pattern for the current session">
          Generate ${def.label.toLowerCase()} pattern
        </div>
        <div class="starter-prompt" data-prompt="What should I consider for the ${def.label.toLowerCase()} in this track?">
          Production tips for ${def.label.toLowerCase()}
        </div>
      </div>
    `;
    // Re-bind starter click handlers
    chatMessages.querySelectorAll(".starter-prompt").forEach((el) => {
      el.addEventListener("click", () => sendElementMessage(el.dataset.prompt));
    });
  } else {
    // Render existing messages
    elem.chatHistory.forEach((msg) => {
      const outputData = msg._outputData || null;
      const fileUrl = msg._fileUrl || null;
      appendMessageToContainer(chatMessages, msg.role, msg.content, outputData, fileUrl);
    });
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  chatInput.placeholder = `Describe what you need for ${def.label.toLowerCase()}...`;
}

// === MIDI Piano Roll Preview ===
const NOTE_NAMES = ["C","C#","D","Eb","E","F","F#","G","Ab","A","Bb","B"];

function midiNoteName(pitch) {
  const octave = Math.floor(pitch / 12) - 2;
  return NOTE_NAMES[pitch % 12] + octave;
}

function renderMidiPreview(notes, canvas) {
  if (!notes || !notes.length) return;
  canvas._midiNotes = notes;

  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;

  // Layout constants
  const LABEL_W = 44;
  const TOP_H = 16;
  const BOT_PAD = 4;

  // Calculate data bounds
  const pitches = notes.map((n) => n.pitch);
  let minPitch = Math.min(...pitches);
  let maxPitch = Math.max(...pitches);
  // Pad pitch range so notes aren't squished to edges
  if (minPitch === maxPitch) { minPitch -= 1; maxPitch += 1; }
  const pitchRange = maxPitch - minPitch + 1;

  const minStart = Math.min(...notes.map((n) => n.start));
  const maxEnd = Math.max(...notes.map((n) => n.start + (n.duration || 0.25)));
  // Snap to full bars (4 beats per bar, 1-indexed)
  const firstBar = Math.floor((minStart - 1) / 4);
  const lastBar = Math.ceil((maxEnd - 1) / 4);
  const totalBeats = (lastBar - firstBar) * 4;
  const beatOffset = firstBar * 4 + 1; // first beat shown (1-indexed)

  // Size the canvas
  const w = canvas.clientWidth;
  const h = Math.max(120, Math.min(150, pitchRange * 14 + TOP_H + BOT_PAD));
  canvas.style.height = h + "px";
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  ctx.scale(dpr, dpr);

  const plotW = w - LABEL_W;
  const plotH = h - TOP_H - BOT_PAD;
  const beatW = plotW / totalBeats;
  const rowH = plotH / pitchRange;

  // Background
  ctx.fillStyle = getCSSVar("--bg");
  ctx.fillRect(0, 0, w, h);

  // Beat grid lines
  const gridColor = getCSSVar("--border");
  const gridColorStrong = getCSSVar("--border-light");
  for (let i = 0; i <= totalBeats; i++) {
    const x = LABEL_W + i * beatW;
    const isBar = i % 4 === 0;
    ctx.strokeStyle = isBar ? gridColorStrong : gridColor;
    ctx.lineWidth = isBar ? 1 : 0.5;
    ctx.beginPath();
    ctx.moveTo(x, TOP_H);
    ctx.lineTo(x, h - BOT_PAD);
    ctx.stroke();
  }

  // Horizontal pitch grid lines
  for (let i = 0; i <= pitchRange; i++) {
    const y = TOP_H + i * rowH;
    ctx.strokeStyle = gridColor;
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    ctx.moveTo(LABEL_W, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  // Bar numbers at top
  ctx.fillStyle = getCSSVar("--text-muted");
  ctx.font = "10px 'JetBrains Mono', monospace";
  ctx.textBaseline = "top";
  for (let bar = firstBar; bar < lastBar; bar++) {
    const x = LABEL_W + (bar - firstBar) * 4 * beatW;
    ctx.fillText("Bar " + (bar + 1), x + 3, 2);
  }

  // Y-axis pitch labels
  ctx.fillStyle = getCSSVar("--text-dim");
  ctx.font = "9px 'JetBrains Mono', monospace";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  // Show labels for each pitch that has notes, but limit to avoid clutter
  const uniquePitches = [...new Set(pitches)].sort((a, b) => a - b);
  const maxLabels = Math.floor(plotH / 14);
  const step = Math.max(1, Math.ceil(uniquePitches.length / maxLabels));
  for (let i = 0; i < uniquePitches.length; i += step) {
    const p = uniquePitches[i];
    const y = TOP_H + (maxPitch - p) * rowH + rowH / 2;
    ctx.fillText(midiNoteName(p), LABEL_W - 4, y);
  }

  // Draw notes — velocity → amber gradient (dim to bright)
  const isDark = document.body.dataset.theme !== "light";
  const VEL_STOPS = isDark ? [
    { v: 1,   r: 57,  g: 44,  b: 19  },
    { v: 40,  r: 140, g: 96,  b: 25  },
    { v: 80,  r: 210, g: 148, b: 35  },
    { v: 127, r: 240, g: 180, b: 60  },
  ] : [
    { v: 1,   r: 224, g: 208, b: 179 },
    { v: 40,  r: 210, g: 160, b: 70  },
    { v: 80,  r: 190, g: 120, b: 30  },
    { v: 127, r: 160, g: 90,  b: 10  },
  ];
  function velColor(vel) {
    const v = Math.max(1, Math.min(127, vel));
    // Find the two stops to lerp between
    let lo = VEL_STOPS[0], hi = VEL_STOPS[VEL_STOPS.length - 1];
    for (let i = 0; i < VEL_STOPS.length - 1; i++) {
      if (v >= VEL_STOPS[i].v && v <= VEL_STOPS[i + 1].v) {
        lo = VEL_STOPS[i];
        hi = VEL_STOPS[i + 1];
        break;
      }
    }
    const t = (v - lo.v) / (hi.v - lo.v || 1);
    const r = Math.round(lo.r + (hi.r - lo.r) * t);
    const g = Math.round(lo.g + (hi.g - lo.g) * t);
    const b = Math.round(lo.b + (hi.b - lo.b) * t);
    return `rgb(${r},${g},${b})`;
  }

  notes.forEach((n) => {
    const x = LABEL_W + (n.start - beatOffset) * beatW;
    const noteW = Math.max((n.duration || 0.25) * beatW, 2);
    const y = TOP_H + (maxPitch - n.pitch) * rowH + 1;
    const noteH = Math.max(rowH - 2, 3);
    const vel = Math.max(1, Math.min(127, n.velocity || 100));

    // Fill with shadow
    ctx.shadowColor = "rgba(0,0,0,0.3)";
    ctx.shadowBlur = 2;
    ctx.shadowOffsetY = 1;
    ctx.fillStyle = velColor(vel);
    ctx.beginPath();
    if (ctx.roundRect) {
      ctx.roundRect(x, y, noteW, noteH, 2);
    } else {
      ctx.rect(x, y, noteW, noteH);
    }
    ctx.fill();
    ctx.shadowColor = "transparent";
    ctx.shadowBlur = 0;
    ctx.shadowOffsetY = 0;

    // 1px outline so adjacent notes are visually distinct
    ctx.strokeStyle = getCSSVar("--border");
    ctx.lineWidth = 1;
    ctx.beginPath();
    if (ctx.roundRect) {
      ctx.roundRect(x, y, noteW, noteH, 2);
    } else {
      ctx.rect(x, y, noteW, noteH);
    }
    ctx.stroke();
  });
}

// === Message Rendering ===
function appendMessageToContainer(container, role, content, outputData, fileUrl) {
  const div = document.createElement("div");
  div.className = `message ${role}`;

  let html = `<div class="message-content">`;

  const paragraphs = content.split("\n\n").filter(Boolean);
  paragraphs.forEach((p) => {
    const formatted = escapeHtml(p).replace(/\n/g, "<br>");
    html += `<p>${formatted}</p>`;
  });

  if (outputData) {
    const typeClass = outputData.type || "midi";
    const typeLabel = getTypeLabel(outputData.type);
    const hasMidiNotes = outputData.type === "midi" && Array.isArray(outputData.notes) && outputData.notes.length > 0;
    const previewId = hasMidiNotes ? `midi-preview-${Date.now()}` : "";

    // For MIDI: show specs line. For others: show description + meta.
    let cardBody = "";
    if (hasMidiNotes) {
      const specsLine = outputData.specs || "";
      cardBody = specsLine ? `<div class="output-card-specs">${escapeHtml(specsLine)}</div>` : "";
    } else {
      const meta = outputData.sections
        ? outputData.sections.length + " sections"
        : outputData.chain
          ? outputData.chain.length + " devices"
          : "";
      cardBody = (outputData.description ? `<div class="output-card-desc">${escapeHtml(outputData.description)}</div>` : "")
        + (meta ? `<div class="output-card-meta">${meta}</div>` : "");
    }

    html += `
      <div class="output-card ${typeClass}">
        <div class="output-card-header">
          <span class="output-badge ${typeClass}">${typeLabel}</span>
          <span class="output-card-name">${escapeHtml(outputData.name || "output")}</span>
        </div>
        ${cardBody}
        ${hasMidiNotes ? `<canvas class="midi-preview" id="${previewId}"></canvas>` : ""}
        ${hasMidiNotes ? `<button class="download-btn midi-download-btn">Download</button>` : fileUrl ? `<a href="${fileUrl}" class="download-btn" download>Download</a>` : ""}
      </div>
    `;
  }

  html += `</div>`;
  div.innerHTML = html;
  container.appendChild(div);

  const hasMidi = outputData && outputData.type === "midi" && Array.isArray(outputData.notes) && outputData.notes.length > 0;

  // Render MIDI piano roll preview and attach download handler
  if (hasMidi) {
    const canvas = div.querySelector(".midi-preview");
    if (canvas) renderMidiPreview(outputData.notes, canvas);

    const dlBtn = div.querySelector(".midi-download-btn");
    if (dlBtn) {
      const capturedOutput = outputData;
      dlBtn.addEventListener("click", () => {
        downloadMidiFromNotes(capturedOutput, parseInt($("#bpm").value) || 128);
      });
    }
  }

  // Track downloads — mark element as complete when user downloads a file
  div.querySelectorAll(".download-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      markElementDownloaded(sessionState.activeElement);
    });
  });

  // Native drag-and-drop for MIDI files (Electron → Ableton)
  if (window.electronAPI && hasMidi) {
    const card = div.querySelector(".output-card");
    if (card) {
      card.setAttribute("draggable", "true");
      card.classList.add("midi-draggable");
      const capturedNotes = outputData.notes;
      const capturedName = (outputData.name || "output").replace(/[^a-zA-Z0-9_\-.]/g, "_") + ".mid";
      const capturedUrl = fileUrl; // e.g. "/outputs/filename.mid"

      card.addEventListener("dragstart", async (e) => {
        e.preventDefault();
        let relativePath;
        if (capturedUrl && capturedUrl.startsWith("/outputs/")) {
          // Server already wrote this file — use it directly
          relativePath = capturedUrl.replace(/^\//, "");
        } else {
          // Generate from notes and write to disk
          const currentBpm = parseInt(document.getElementById("bpm").value) || 128;
          const blob = generateMidiBlob(capturedNotes, currentBpm);
          const bytes = new Uint8Array(await blob.arrayBuffer());
          relativePath = await window.electronAPI.writeMidi(bytes, capturedName);
        }
        window.electronAPI.startDrag(relativePath);
      });
    }
  }
}

function showLoading(container) {
  const div = document.createElement("div");
  div.className = "loading";
  div.id = "loading-indicator";
  div.innerHTML = `
    <div class="loading-dots"><span></span><span></span><span></span></div>
    <span class="loading-text">DAW Brain is thinking...</span>
  `;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function hideLoading() {
  const el = $("#loading-indicator");
  if (el) el.remove();
}

// === Build Element History for Cross-Element Awareness ===
function buildElementHistory() {
  const history = {};
  Object.entries(sessionState.elements).forEach(([id, elem]) => {
    if (elem.status !== "empty") {
      history[id] = {
        status: elem.status,
        summary: elem.summary || "",
      };
    }
  });
  return history;
}

// === Send Element Message ===
async function sendElementMessage(text) {
  if (!text.trim() || sessionState.loading) return;

  const elementId = sessionState.activeElement;
  if (!elementId) return;

  sessionState.loading = true;
  sendBtn.disabled = true;
  chatInput.value = "";
  chatInput.style.height = "auto";

  const elem = sessionState.elements[elementId];

  // Mark as in_progress on first prompt sent
  if (elem.status === "empty") {
    elem.status = "in_progress";
    updateElementStatus(elementId);
  }

  // Add user message
  elem.chatHistory.push({ role: "user", content: text });
  appendMessageToContainer(chatMessages, "user", text);
  showLoading(chatMessages);

  // Hide starters
  const starters = chatMessages.querySelector(".starter-prompts");
  if (starters) starters.classList.add("hidden");

  try {
    // Build API messages (strip our custom metadata)
    const apiMessages = elem.chatHistory.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    const result = await API.chat(
      apiMessages,
      getSession(),
      getGenre(),
      elementId,
      buildElementHistory(),
      sessionState.skillLevel
    );
    hideLoading();

    // Store metadata on the message for re-rendering
    const assistantMsg = {
      role: "assistant",
      content: result.text,
      _outputData: result.output || null,
      _fileUrl: result.file_url || null,
    };
    elem.chatHistory.push(assistantMsg);
    appendMessageToContainer(chatMessages, "assistant", result.text, result.output, result.file_url);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Track output (status stays in_progress until user downloads)
    if (result.output) {
      const outputEntry = {
        type: result.output.type,
        name: result.output.name,
        url: result.file_url,
        element: elementId,
      };
      if (result.output.type === "midi" && Array.isArray(result.output.notes)) {
        outputEntry.notes = result.output.notes;
      }
      elem.outputs.push(outputEntry);
      elem.summary = result.output.description || result.output.name || "";
      renderOutputList();
    }
    saveSession();
  } catch (e) {
    hideLoading();
    appendMessageToContainer(chatMessages, "assistant", `Error: ${e.message}. Check that your ANTHROPIC_API_KEY is set and the server is running.`);
  }

  sessionState.loading = false;
  sendBtn.disabled = false;
  chatInput.focus();
}

// === Send General Message ===
async function sendGeneralMessage(text) {
  if (!text.trim() || sessionState.loading) return;

  sessionState.loading = true;
  generalSendBtn.disabled = true;
  generalChatInput.value = "";
  generalChatInput.style.height = "auto";

  // Hide starters
  const starters = generalChatMessages.querySelector(".starter-prompts");
  if (starters) starters.classList.add("hidden");

  sessionState.generalMessages.push({ role: "user", content: text });
  appendMessageToContainer(generalChatMessages, "user", text);
  showLoading(generalChatMessages);

  try {
    const apiMessages = sessionState.generalMessages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    const result = await API.chat(
      apiMessages,
      getSession(),
      getGenre(),
      null,
      buildElementHistory(),
      sessionState.skillLevel
    );
    hideLoading();

    const assistantMsg = {
      role: "assistant",
      content: result.text,
      _outputData: result.output || null,
      _fileUrl: result.file_url || null,
    };
    sessionState.generalMessages.push(assistantMsg);
    appendMessageToContainer(generalChatMessages, "assistant", result.text, result.output, result.file_url);
    generalChatMessages.scrollTop = generalChatMessages.scrollHeight;

    if (result.output) {
      const outputEntry = {
        type: result.output.type,
        name: result.output.name,
        url: result.file_url,
        element: "general",
      };
      if (result.output.type === "midi" && Array.isArray(result.output.notes)) {
        outputEntry.notes = result.output.notes;
      }
      sessionState.generalOutputs.push(outputEntry);
      renderOutputList();
    }
    saveSession();
  } catch (e) {
    hideLoading();
    appendMessageToContainer(generalChatMessages, "assistant", `Error: ${e.message}`);
  }

  sessionState.loading = false;
  generalSendBtn.disabled = false;
  generalChatInput.focus();
}

// === Output List Rendering ===
function renderOutputList() {
  const allOutputs = [];

  // Gather from all elements
  Object.entries(sessionState.elements).forEach(([id, elem]) => {
    elem.outputs.forEach((o) => allOutputs.push({ ...o, element: id }));
  });

  // Gather from general
  sessionState.generalOutputs.forEach((o) => allOutputs.push(o));

  if (allOutputs.length === 0) {
    outputList.innerHTML = '<div class="outputs-empty">No outputs yet</div>';
    $("#download-all-btn").classList.add("hidden");
    return;
  }

  // Group by element
  const grouped = {};
  allOutputs.forEach((o) => {
    const key = o.element || "general";
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(o);
  });

  let html = "";
  let flatIndex = 0;
  Object.entries(grouped).forEach(([elementId, outputs]) => {
    const label = ELEMENT_DEFS[elementId]
      ? ELEMENT_DEFS[elementId].label.toUpperCase()
      : "GENERAL";
    html += `<div class="output-group-label">${label}</div>`;
    outputs.forEach((o) => {
      const typeLabel = getTypeLabel(o.type);
      const elemAttr = o.element ? `data-dl-element="${o.element}"` : "";
      const isMidi = o.type === "midi" && Array.isArray(o.notes) && o.notes.length > 0;
      html += `
        <div class="output-item${isMidi ? " midi-draggable" : ""}" ${elemAttr} ${o.url ? `data-dl-url="${o.url}"` : ""} data-flat-idx="${flatIndex}">
          <span class="output-badge ${o.type}">${typeLabel}</span>
          <span class="output-name">${escapeHtml(o.name || "output")}</span>
        </div>
      `;
      flatIndex++;
    });
  });

  outputList.innerHTML = html;
  $("#download-all-btn").classList.remove("hidden");

  // Attach click handlers for download tracking
  outputList.querySelectorAll(".output-item[data-dl-url]").forEach((item) => {
    item.addEventListener("click", () => {
      window.open(item.dataset.dlUrl, "_blank");
      markElementDownloaded(item.dataset.dlElement);
    });
  });

  // Attach native drag for MIDI items in output list (Electron only)
  if (window.electronAPI) {
    outputList.querySelectorAll(".output-item.midi-draggable").forEach((item) => {
      const idx = parseInt(item.dataset.flatIdx);
      const o = allOutputs[idx];
      if (!o) return;
      item.setAttribute("draggable", "true");
      item.addEventListener("dragstart", async (e) => {
        e.preventDefault();
        let relativePath;
        if (o.url && o.url.startsWith("/outputs/")) {
          relativePath = o.url.replace(/^\//, "");
        } else {
          const currentBpm = parseInt(document.getElementById("bpm").value) || 128;
          const blob = generateMidiBlob(o.notes, currentBpm);
          const bytes = new Uint8Array(await blob.arrayBuffer());
          const safeName = (o.name || "output").replace(/[^a-zA-Z0-9_\-.]/g, "_") + ".mid";
          relativePath = await window.electronAPI.writeMidi(bytes, safeName);
        }
        window.electronAPI.startDrag(relativePath);
      });
    });
  }
}

// === Chat Input Handlers ===

// Element chat
sendBtn.addEventListener("click", () => sendElementMessage(chatInput.value));

chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendElementMessage(chatInput.value);
  }
});

chatInput.addEventListener("input", () => {
  chatInput.style.height = "auto";
  chatInput.style.height = Math.min(chatInput.scrollHeight, 80) + "px";
  sendBtn.classList.toggle("dimmed", !chatInput.value.trim());
});

// General chat
generalSendBtn.addEventListener("click", () => sendGeneralMessage(generalChatInput.value));

generalChatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendGeneralMessage(generalChatInput.value);
  }
});

generalChatInput.addEventListener("input", () => {
  generalChatInput.style.height = "auto";
  generalChatInput.style.height = Math.min(generalChatInput.scrollHeight, 80) + "px";
  generalSendBtn.classList.toggle("dimmed", !generalChatInput.value.trim());
});

// General chat starter prompts
$$("#general-starters .starter-prompt").forEach((el) => {
  el.addEventListener("click", () => sendGeneralMessage(el.dataset.prompt));
});

// === Heartbeat ===
setInterval(() => {
  fetch("/api/heartbeat", { method: "POST" }).catch(() => {});
}, 3000);

// === Top Navigation (View Switching) ===
$$(".top-nav-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    $$(".top-nav-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");

    const viewId = tab.dataset.view + "-view";
    $$(".view").forEach((v) => v.classList.remove("active"));
    const view = document.getElementById(viewId);
    if (view) view.classList.add("active");
  });
});

// === Vocal Separator ===
(function () {
  const dropzone = $("#vocal-dropzone");
  const fileInput = $("#vocal-file-input");
  const browseBtn = $("#vocal-browse-btn");
  const filenameEl = $("#vocal-filename");
  const goBtn = $("#vocal-go-btn");
  const uploadArea = $("#vocal-upload-area");
  const processing = $("#vocal-processing");
  const results = $("#vocal-results");
  const errorArea = $("#vocal-error");
  const errorMsg = $("#vocal-error-msg");
  const newBtn = $("#vocal-new-btn");
  const retryBtn = $("#vocal-error-retry");

  let selectedFile = null;

  function formatSize(bytes) {
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  function showState(state) {
    uploadArea.classList.toggle("hidden", state !== "upload");
    processing.classList.toggle("hidden", state !== "processing");
    results.classList.toggle("hidden", state !== "results");
    errorArea.classList.toggle("hidden", state !== "error");
  }

  function resetUpload() {
    selectedFile = null;
    filenameEl.textContent = "";
    goBtn.classList.add("hidden");
    fileInput.value = "";
    showState("upload");
  }

  function handleFile(file) {
    if (!file) return;
    const ext = file.name.split(".").pop().toLowerCase();
    if (!["wav", "mp3", "flac", "m4a"].includes(ext)) {
      alert("Unsupported format. Use WAV, MP3, FLAC, or M4A.");
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      alert("File too large. Max 50MB.");
      return;
    }
    selectedFile = file;
    filenameEl.textContent = file.name + " (" + formatSize(file.size) + ")";
    goBtn.classList.remove("hidden");
  }

  // Browse button
  browseBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    fileInput.click();
  });

  fileInput.addEventListener("change", () => {
    handleFile(fileInput.files[0]);
  });

  // Dropzone click
  dropzone.addEventListener("click", () => fileInput.click());

  // Drag and drop
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("drag-over");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("drag-over");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag-over");
    const file = e.dataTransfer.files[0];
    handleFile(file);
  });

  // Separate button
  goBtn.addEventListener("click", async () => {
    if (!selectedFile) return;

    showState("processing");

    try {
      const result = await API.separateVocals(selectedFile);

      // Set audio source, size, and download link
      $("#vocal-audio").src = result.vocal_url;
      $("#vocal-size").textContent = formatSize(result.vocal_size);
      $("#vocal-download").href = result.vocal_url;

      showState("results");
    } catch (e) {
      errorMsg.textContent = e.message;
      showState("error");
    }
  });

  // Reset buttons
  newBtn.addEventListener("click", resetUpload);
  retryBtn.addEventListener("click", resetUpload);
})();

// === Resize Handle (Kanban / Chat divider) ===
(function initResize() {
  const handle = $("#resize-handle");
  const builderView = $("#builder-view");
  const chat = $("#element-chat");
  const sessionBar = $("#session-bar");
  const CHAT_KEY = "dawbrain_chat_height";
  const MIN_KANBAN = 120;
  const MIN_CHAT = 150;

  function getMaxChat() {
    const viewH = builderView.getBoundingClientRect().height;
    return viewH - sessionBar.offsetHeight - handle.offsetHeight - MIN_KANBAN;
  }

  function applyChatHeight(h) {
    const clamped = Math.max(MIN_CHAT, Math.min(h, getMaxChat()));
    chat.style.height = clamped + "px";
    return clamped;
  }

  // Restore saved height or compute 60% default
  const saved = localStorage.getItem(CHAT_KEY);
  if (saved) {
    applyChatHeight(parseInt(saved));
  } else {
    requestAnimationFrame(() => {
      const available = builderView.getBoundingClientRect().height
        - sessionBar.offsetHeight - handle.offsetHeight;
      applyChatHeight(Math.round(available * 0.6));
    });
  }

  let dragging = false;
  let startY = 0;
  let startH = 0;

  handle.addEventListener("mousedown", (e) => {
    e.preventDefault();
    dragging = true;
    startY = e.clientY;
    startH = chat.offsetHeight;
    handle.classList.add("dragging");
    document.body.style.cursor = "ns-resize";
    document.body.style.userSelect = "none";
    document.body.style.webkitUserSelect = "none";
  });

  document.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    const deltaY = startY - e.clientY;
    applyChatHeight(startH + deltaY);
  });

  document.addEventListener("mouseup", () => {
    if (!dragging) return;
    dragging = false;
    handle.classList.remove("dragging");
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    document.body.style.webkitUserSelect = "";
    localStorage.setItem(CHAT_KEY, chat.offsetHeight);
  });

  // Clamp on window resize
  window.addEventListener("resize", () => {
    const current = chat.offsetHeight;
    const max = getMaxChat();
    if (current > max) {
      chat.style.height = Math.max(MIN_CHAT, max) + "px";
    }
  });
})();

// === Init ===
const _savedSession = loadSession();
loadPresets().then(() => {
  if (_savedSession && _savedSession.genre) {
    genreSelect.value = _savedSession.genre;
    updatePresetDesc();
  }
}).finally(() => {
  _sessionReady = true;
});
updateTrackCount();
sendBtn.classList.add("dimmed");
generalSendBtn.classList.add("dimmed");

// Persist on session settings change
$("#bpm").addEventListener("change", saveSession);
$("#key").addEventListener("change", saveSession);
$("#scale").addEventListener("change", saveSession);
genreSelect.addEventListener("change", saveSession);

// Clear session
$("#clear-session-btn").addEventListener("click", clearSession);
