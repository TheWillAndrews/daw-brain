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
  sessionId: null,  // set after loading from API/DB
  bpm: 128,
  key: "E",
  scale: "minor",
  genre: "tech_house",
  spotifyProfile: null,
  skillLevel: "expert",  // kept for API compat, always "expert"
  mode: localStorage.getItem("daw-brain-mode") || "guided",  // "guided" | "studio"

  elements: {},
  activeElement: null,
  activeChatTab: "element",  // "element" or "general"

  // Guided mode state
  guidedOutputs: [],        // outputs generated in guided mode
  guidedContexts: {},       // per-element context snapshots from guided generation

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
let _saving = false;

function buildSessionData() {
  return {
    sessionId: sessionState.sessionId,
    bpm: parseInt($("#bpm").value) || 128,
    key: $("#key").value,
    scale: $("#scale").value,
    genre: genreSelect.value,
    skillLevel: sessionState.skillLevel,
    mode: sessionState.mode,
    activeElement: sessionState.activeElement,
    activeChatTab: sessionState.activeChatTab,
    elements: sessionState.elements,
    generalMessages: sessionState.generalMessages,
    generalOutputs: sessionState.generalOutputs,
  };
}

function applySessionData(data) {
  // Restore session settings to DOM
  if (data.bpm) $("#bpm").value = data.bpm;
  if (data.key) $("#key").value = data.key;
  if (data.scale) $("#scale").value = data.scale;

  // Restore mode
  if (data.mode) {
    sessionState.mode = data.mode;
    localStorage.setItem("daw-brain-mode", data.mode);
    $$("#mode-toggle .mode-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.mode === data.mode);
    });
  }

  // Restore elements
  const elements = data.elements || {};
  Object.keys(elements).forEach((id) => {
    if (sessionState.elements[id] && elements[id]) {
      const saved = elements[id];
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
}

function saveSession() {
  if (!_sessionReady) return;
  clearTimeout(_saveTimeout);
  _saveTimeout = setTimeout(async () => {
    const data = buildSessionData();

    // Save to localStorage (fast cache)
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, ...data }));
    } catch (e) {
      // localStorage full or unavailable — fail silently
    }

    // Save to API (source of truth)
    if (_saving) return;
    _saving = true;
    try {
      const result = await API.saveSessionState(data);
      if (result && result.sessionId && !sessionState.sessionId) {
        sessionState.sessionId = result.sessionId;
      }
    } catch (e) {
      // API save failed — localStorage cache is still there
    }
    _saving = false;
  }, 500);
}

function loadSessionFromLocalStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data || typeof data !== "object" || !data.elements) return null;
    applySessionData(data);
    return { genre: data.genre };
  } catch (e) {
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

async function loadSession() {
  // Try API first (database is source of truth)
  try {
    const data = await API.getActiveSession();
    if (data && data.sessionId) {
      sessionState.sessionId = data.sessionId;
      applySessionData(data);
      return { genre: data.genre };
    }
  } catch (e) {
    // API not available — fall back to localStorage
  }
  return loadSessionFromLocalStorage();
}

async function clearSession() {
  try {
    await API.clearActiveSession();
  } catch (e) {
    // Continue with local clear even if API fails
  }
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem("daw-brain-mode");
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

// === Guided Mode Element Definitions ===
// 9-element sequential flow: maps to underlying ELEMENT_DEFS IDs
const GUIDED_ELEMENTS = [
  { id: "kick",    label: "Kick",               mapTo: ["kick"],                  group: "drums",   defaultPrompt: "Generate a kick pattern for this track" },
  { id: "clap",    label: "Clap / Snare",       mapTo: ["clap"],                  group: "drums",   defaultPrompt: "Generate a clap/snare pattern for this track" },
  { id: "hats",    label: "Hi-Hats",            mapTo: ["hats"],                  group: "drums",   defaultPrompt: "Generate a hi-hat pattern for this track" },
  { id: "perc",    label: "Percussion",          mapTo: ["perc"],                  group: "drums",   defaultPrompt: "Generate a percussion pattern for this track" },
  { id: "bass",    label: "Bass",                mapTo: ["sub", "midbass"],        group: "bass",    defaultPrompt: "Generate a bass pattern for this track" },
  { id: "chords",  label: "Chords / Pads / Stabs", mapTo: ["chords", "pad", "stabs"], group: "melodic", defaultPrompt: "Generate a chords/pads part for this track" },
  { id: "lead",    label: "Melodic Lead / Hook", mapTo: ["lead", "arps", "plucks"], group: "melodic", defaultPrompt: "Generate a melodic lead or hook for this track" },
  { id: "vocals",  label: "Vocals",              mapTo: ["mainvox", "chops", "hook", "adlibs"], group: "vocals", defaultPrompt: "Describe a vocal arrangement for this track" },
  { id: "fx",      label: "FX & Transitions",    mapTo: ["risers", "downlifters", "impacts", "sweeps", "transitions", "textures"], group: "fx", defaultPrompt: "Generate FX and transition ideas for this track" },
];

// === Mode Toggle (Guided / Studio) ===
(function initModeToggle() {
  const btns = $$("#mode-toggle .mode-btn");
  const guidedArea = $("#guided-area");
  const studioArea = $("#studio-area");
  const chatSection = $("#element-chat");
  const resizeHandle = $("#resize-handle");

  function applyMode(mode) {
    sessionState.mode = mode;
    localStorage.setItem("daw-brain-mode", mode);

    btns.forEach((b) => b.classList.toggle("active", b.dataset.mode === mode));

    if (mode === "guided") {
      guidedArea.classList.remove("hidden");
      studioArea.classList.add("hidden");
      if (chatSection) chatSection.classList.add("hidden");
      if (resizeHandle) resizeHandle.classList.add("hidden");
      renderGuidedElements();
    } else {
      guidedArea.classList.add("hidden");
      studioArea.classList.remove("hidden");
      if (chatSection) chatSection.classList.remove("hidden");
      if (resizeHandle) resizeHandle.classList.remove("hidden");
    }
  }

  btns.forEach((btn) => {
    btn.addEventListener("click", () => {
      applyMode(btn.dataset.mode);
      saveSession();
    });
  });

  // Apply initial mode
  applyMode(sessionState.mode);
})();

// === Guided Mode Rendering & Logic ===
function getGuidedElementState(guidedEl) {
  // Check if any mapped element has outputs
  const hasOutput = guidedEl.mapTo.some((id) => {
    const elem = sessionState.elements[id];
    return elem && elem.outputs && elem.outputs.length > 0;
  });
  const isLoading = guidedEl.mapTo.some((id) => {
    const elem = sessionState.elements[id];
    return elem && elem.status === "in_progress" && (!elem.outputs || elem.outputs.length === 0);
  });
  if (isLoading) return "loading";
  if (hasOutput) return "generated";
  return "empty";
}

function getRecommendedGuidedIndex() {
  for (let i = 0; i < GUIDED_ELEMENTS.length; i++) {
    if (getGuidedElementState(GUIDED_ELEMENTS[i]) === "empty") return i;
  }
  return -1; // all done
}

function renderGuidedElements() {
  const container = $("#guided-elements");
  if (!container) return;

  const recommendedIdx = getRecommendedGuidedIndex();

  container.innerHTML = GUIDED_ELEMENTS.map((gel, idx) => {
    const state = getGuidedElementState(gel);
    const isRecommended = idx === recommendedIdx && state === "empty";
    const isActive = state === "loading";

    // Get mini preview if generated
    let previewHtml = "";
    if (state === "generated") {
      const primaryId = gel.mapTo[0];
      const elem = sessionState.elements[primaryId];
      const midiOutput = elem && elem.outputs
        ? [...elem.outputs].reverse().find((o) => o.type === "midi" && Array.isArray(o.notes) && o.notes.length > 0)
        : null;
      if (midiOutput) {
        previewHtml = `<canvas class="guided-preview midi-preview" data-guided-idx="${idx}"></canvas>`;
      }
    }

    const classes = [
      "guided-card",
      state === "generated" ? "generated" : "",
      isRecommended ? "recommended" : "",
      isActive ? "active" : "",
    ].filter(Boolean).join(" ");

    const btnLabel = state === "generated" ? "Regenerate" : "Generate";
    const btnClass = state === "generated" ? "guided-gen-btn regenerate" : "guided-gen-btn";

    return `
      <div class="${classes}" data-guided-idx="${idx}" data-guided-id="${gel.id}">
        <div class="guided-num">${idx + 1}</div>
        <div class="guided-info">
          <div class="guided-name">${gel.label}</div>
          <div class="guided-meta">${state === "generated" ? "Done" : isRecommended ? "Recommended next" : ""}</div>
          ${previewHtml}
        </div>
        <div class="guided-actions">
          <button class="${btnClass}" data-guided-idx="${idx}"${isActive ? " disabled" : ""}>
            ${isActive ? '<span class="loading-dots"><span></span><span></span><span></span></span>' : btnLabel}
          </button>
        </div>
      </div>
    `;
  }).join("");

  // Render MIDI previews for generated elements
  GUIDED_ELEMENTS.forEach((gel, idx) => {
    if (getGuidedElementState(gel) !== "generated") return;
    const canvas = container.querySelector(`.guided-preview[data-guided-idx="${idx}"]`);
    if (!canvas) return;
    const primaryId = gel.mapTo[0];
    const elem = sessionState.elements[primaryId];
    const midiOutput = elem && elem.outputs
      ? [...elem.outputs].reverse().find((o) => o.type === "midi" && Array.isArray(o.notes) && o.notes.length > 0)
      : null;
    if (midiOutput) renderMidiPreview(midiOutput.notes, canvas);
  });

  // Wire generate/regenerate buttons
  container.querySelectorAll(".guided-gen-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const idx = parseInt(btn.dataset.guidedIdx);
      generateGuidedElement(idx);
    });
  });

  // Wire card click to download if generated
  container.querySelectorAll(".guided-card.generated").forEach((card) => {
    card.addEventListener("click", () => {
      const idx = parseInt(card.dataset.guidedIdx);
      downloadGuidedElement(idx);
    });
  });

  // Update guided output list
  renderGuidedOutputList();
}

function downloadGuidedElement(idx) {
  const gel = GUIDED_ELEMENTS[idx];
  const primaryId = gel.mapTo[0];
  const elem = sessionState.elements[primaryId];
  const midiOutput = elem && elem.outputs
    ? [...elem.outputs].reverse().find((o) => o.type === "midi" && Array.isArray(o.notes) && o.notes.length > 0)
    : null;
  if (midiOutput) {
    downloadMidiFromNotes(midiOutput, parseInt($("#bpm").value) || 128);
    markElementDownloaded(primaryId);
  }
}

function buildGuidedContext(guidedIdx) {
  // Build context string describing what's already been generated
  // Excludes the current element being generated
  const lines = [];
  GUIDED_ELEMENTS.forEach((gel, idx) => {
    if (idx === guidedIdx) return;
    if (getGuidedElementState(gel) !== "generated") return;

    const primaryId = gel.mapTo[0];
    const elem = sessionState.elements[primaryId];
    if (!elem || !elem.outputs || elem.outputs.length === 0) return;

    const midiOutput = [...elem.outputs].reverse()
      .find((o) => o.type === "midi" && Array.isArray(o.notes) && o.notes.length > 0);
    if (!midiOutput) return;

    lines.push(`${gel.label}: ${elem.summary || midiOutput.name || "generated"}`);
  });

  return lines.length > 0
    ? "Already generated elements:\n" + lines.join("\n")
    : "";
}

async function generateGuidedElement(idx) {
  if (sessionState.loading) return;
  const gel = GUIDED_ELEMENTS[idx];
  const primaryId = gel.mapTo[0]; // use first mapped element as the target

  sessionState.loading = true;

  // Mark loading state and re-render
  const elem = sessionState.elements[primaryId];
  const wasGenerated = elem.outputs && elem.outputs.length > 0;
  if (!wasGenerated) {
    elem.status = "in_progress";
    updateElementStatus(primaryId);
  }
  renderGuidedElements();

  try {
    // Build context-aware prompt with cross-element analysis
    const guidedContext = buildGuidedContext(idx);
    const contextAnalysis = buildContextAnalysis(sessionState.elements, primaryId);
    const elementInstructions = buildElementSpecificInstructions(gel, sessionState.elements);
    const musicalContext = buildMusicalContext(sessionState.elements);
    let prompt = gel.defaultPrompt;
    if (elementInstructions) {
      prompt += "\n\n[ELEMENT INSTRUCTIONS: " + elementInstructions + "]";
    }

    // Set active element so backend knows what we're generating
    sessionState.activeElement = primaryId;

    const apiMessages = [{ role: "user", content: prompt }];

    const result = await API.chat(
      apiMessages,
      getSession(),
      getGenre(),
      primaryId,
      buildElementHistory(),
      sessionState.skillLevel,
      [musicalContext, contextAnalysis, guidedContext].filter(Boolean).join("\n\n"),
      sessionState.sessionId
    );

    // Store output on the element
    const assistantMsg = {
      role: "assistant",
      content: result.text,
      _outputData: result.output || null,
      _fileUrl: result.file_url || null,
    };
    elem.chatHistory = [
      { role: "user", content: prompt },
      assistantMsg,
    ];

    if (result.output) {
      const outputEntry = {
        type: result.output.type,
        name: result.output.name,
        url: result.file_url,
        element: primaryId,
      };
      if (result.output.type === "midi" && Array.isArray(result.output.notes)) {
        outputEntry.notes = result.output.notes;
      }
      // Replace outputs on regen, append on first gen
      if (wasGenerated) {
        elem.outputs = [outputEntry];
      } else {
        elem.outputs.push(outputEntry);
      }
      elem.summary = result.output.musical_summary || result.output.description || result.output.name || "";
      elem.status = "in_progress"; // stays in_progress until downloaded
    }

    updateElementStatus(primaryId);
    saveSession();
  } catch (e) {
    console.error("Guided generation error:", e);
  }

  sessionState.loading = false;
  renderGuidedElements();
}

function renderGuidedOutputList() {
  const list = $("#guided-output-list");
  const dlAllBtn = $("#guided-download-all-btn");
  if (!list) return;

  const outputs = [];
  GUIDED_ELEMENTS.forEach((gel) => {
    gel.mapTo.forEach((id) => {
      const elem = sessionState.elements[id];
      if (elem && elem.outputs) {
        elem.outputs.forEach((o) => outputs.push({ ...o, element: id, label: gel.label }));
      }
    });
  });

  if (outputs.length === 0) {
    list.innerHTML = '<div class="outputs-empty">No outputs yet</div>';
    if (dlAllBtn) dlAllBtn.classList.add("hidden");
    return;
  }

  list.innerHTML = outputs.map((o, i) => {
    const typeLabel = getTypeLabel(o.type);
    return `
      <div class="output-item" data-guided-output-idx="${i}">
        <span class="output-badge ${o.type}">${typeLabel}</span>
        <span class="output-name">${escapeHtml(o.name || o.label)}</span>
      </div>
    `;
  }).join("");

  if (dlAllBtn) dlAllBtn.classList.remove("hidden");

  // Click to download individual
  list.querySelectorAll(".output-item").forEach((item) => {
    item.addEventListener("click", () => {
      const idx = parseInt(item.dataset.guidedOutputIdx);
      const o = outputs[idx];
      if (o && o.type === "midi" && Array.isArray(o.notes) && o.notes.length > 0) {
        downloadMidiFromNotes(o, parseInt($("#bpm").value) || 128);
        markElementDownloaded(o.element);
      }
    });
  });
}

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

// === Musical Context Builder (Deep Cross-Element Awareness) ===
const DRUM_ELEMENTS = new Set(["kick", "clap", "hats", "perc", "toploop"]);
const MELODIC_ELEMENTS = new Set(["sub", "midbass", "stabs", "lead", "chords", "pad", "arps", "plucks"]);

const ELEMENT_FREQ_RANGES = {
  kick: "Sub (30-60 Hz)", clap: "Mid (200-2000 Hz)", hats: "High (3-10 kHz)",
  perc: "Mid-High (500-5000 Hz)", toploop: "High (2-8 kHz)",
  sub: "Sub (30-80 Hz)", midbass: "Low-Mid (80-300 Hz)",
  stabs: "Mid-High (300-5000 Hz)", lead: "Mid-High (500-8000 Hz)",
  chords: "Mid (200-4000 Hz)", pad: "Mid (200-4000 Hz)",
  arps: "Mid-High (500-8000 Hz)", plucks: "Mid-High (500-8000 Hz)",
};

const INTERVAL_NAMES = {
  0: "P1", 1: "m2", 2: "M2", 3: "m3", 4: "M3", 5: "P4",
  6: "TT", 7: "P5", 8: "m6", 9: "M6", 10: "m7", 11: "M7", 12: "P8",
};

function notePosition(start) {
  const zeroIndexed = start - 1;
  const bar = Math.floor(zeroIndexed / 4) + 1;
  const beatInBar = zeroIndexed % 4;
  const beat = Math.floor(beatInBar) + 1;
  const frac = beatInBar - Math.floor(beatInBar);
  const sub = Math.round(frac / 0.25) + 1;
  return `${bar}.${beat}.${sub}`;
}

function buildRhythmSummary(notes) {
  const subCounts = { 1: 0, 2: 0, 3: 0, 4: 0 };
  const velocities = [];
  notes.forEach((n) => {
    const frac = (n.start - 1) % 1;
    const sub = Math.round(frac / 0.25) + 1;
    subCounts[sub] = (subCounts[sub] || 0) + 1;
    velocities.push(n.velocity || 100);
  });

  const total = notes.length;
  const parts = [];

  if (subCounts[1] / total > 0.4) parts.push("Main hits on .1 positions (on-beat)");
  else if (subCounts[1] > 0) parts.push("some on-beat hits (.1)");

  if (subCounts[3] / total > 0.3) parts.push("strong .3 presence (offbeat)");
  else if (subCounts[3] > 0) parts.push("some .3 hits (offbeat)");

  if (subCounts[2] > 0 || subCounts[4] > 0) {
    const sixteenthCount = subCounts[2] + subCounts[4];
    if (sixteenthCount / total > 0.3) parts.push("16th note movement (.2/.4)");
    else if (sixteenthCount > 0) parts.push("occasional 16th fills");
  }

  const avgVel = Math.round(velocities.reduce((a, b) => a + b, 0) / velocities.length);
  const minVel = Math.min(...velocities);
  const maxVel = Math.max(...velocities);
  if (maxVel - minVel < 10) {
    parts.push(`flat velocity ~${avgVel}`);
  } else {
    const ghostThreshold = avgVel * 0.7;
    const ghostCount = velocities.filter((v) => v < ghostThreshold).length;
    if (ghostCount > 0) {
      parts.push(`ghost hits at ~${Math.round((minVel / maxVel) * 100)}% velocity`);
    } else {
      parts.push(`velocity range ${minVel}-${maxVel}`);
    }
  }

  return parts.join(", ");
}

function barsFromNotes(notes) {
  if (!notes.length) return 0;
  const maxBeat = Math.max(...notes.map((n) => n.start + (n.duration || 0.25)));
  return Math.ceil((maxBeat - 1) / 4);
}

function collapseRepeatedBars(notes, totalBars) {
  if (totalBars <= 2) return null;

  const barNotes = {};
  for (let b = 1; b <= totalBars; b++) barNotes[b] = [];
  notes.forEach((n) => {
    const bar = Math.floor((n.start - 1) / 4) + 1;
    if (barNotes[bar]) barNotes[bar].push(n);
  });

  function barFingerprint(barNum) {
    return (barNotes[barNum] || [])
      .map((n) => {
        const relStart = ((n.start - 1) % 4).toFixed(3);
        return `${relStart}:${n.pitch}:${n.velocity}`;
      })
      .sort()
      .join("|");
  }

  const fingerprints = {};
  const repeats = {};
  for (let b = 1; b <= totalBars; b++) {
    const fp = barFingerprint(b);
    if (fingerprints[fp] !== undefined) {
      repeats[b] = fingerprints[fp];
    } else {
      fingerprints[fp] = b;
    }
  }
  return Object.keys(repeats).length > 0 ? repeats : null;
}

function buildMusicalContext(elements) {
  const bpm = parseInt(document.getElementById("bpm").value) || 128;
  const key = document.getElementById("key").value || "C";
  const scale = document.getElementById("scale").value || "minor";

  const blocks = [];

  Object.entries(elements).forEach(([elemId, elem]) => {
    if (!elem.outputs || elem.outputs.length === 0) return;
    if (!["in_progress", "complete"].includes(elem.status)) return;

    // Use the most recent MIDI output with notes
    const midiOutput = [...elem.outputs]
      .reverse()
      .find((o) => o.type === "midi" && Array.isArray(o.notes) && o.notes.length > 0);
    if (!midiOutput) return;

    const notes = midiOutput.notes;
    const isDrum = DRUM_ELEMENTS.has(elemId);
    const isMelodic = MELODIC_ELEMENTS.has(elemId);
    const totalBars = barsFromNotes(notes);

    const pitchSet = new Set(notes.map((n) => n.pitch));
    const pitchNames = [...pitchSet]
      .sort((a, b) => a - b)
      .map((p) => `${midiNoteName(p)}(${p})`);

    let block = `[ELEMENT: ${elemId}]\n`;
    block += `Bars: ${totalBars} | BPM: ${bpm}`;
    if (isMelodic) block += ` | Key: ${key} ${scale}`;
    block += ` | Notes: ${notes.length}\n`;
    block += `Pitches${isMelodic ? " used" : ""}: ${pitchNames.join(", ")}\n`;

    // Sort notes by start time
    const sorted = [...notes].sort((a, b) => a.start - b.start);
    let patternNotes = sorted;

    // For drums, collapse repeated bars
    const repeats = isDrum ? collapseRepeatedBars(sorted, totalBars) : null;
    let repeatNote = "";
    if (repeats) {
      const repeatedBars = new Set(Object.keys(repeats).map(Number));
      patternNotes = sorted.filter((n) => {
        const bar = Math.floor((n.start - 1) / 4) + 1;
        return !repeatedBars.has(bar);
      });
      const bySource = {};
      Object.entries(repeats).forEach(([repBar, srcBar]) => {
        if (!bySource[srcBar]) bySource[srcBar] = [];
        bySource[srcBar].push(repBar);
      });
      const repeatParts = Object.entries(bySource).map(
        ([src, reps]) => `bar ${reps.join(", ")} = bar ${src}`
      );
      repeatNote = `  (Repeats: ${repeatParts.join("; ")})\n`;
    }

    // Cap at 32 notes — show first 16 + ... + last 16
    let truncated = false;
    if (patternNotes.length > 32) {
      const first16 = patternNotes.slice(0, 16);
      const last16 = patternNotes.slice(-16);
      patternNotes = [...first16, null, ...last16];
      truncated = true;
    }

    block += "Pattern:\n";
    patternNotes.forEach((n) => {
      if (n === null) {
        block += "  ...\n";
      } else {
        block += `  ${notePosition(n.start)} → ${midiNoteName(n.pitch)} @ ${n.velocity || 100}\n`;
      }
    });
    if (repeatNote) block += repeatNote;

    block += `Rhythm summary: ${buildRhythmSummary(notes)}\n`;

    const freqRange = ELEMENT_FREQ_RANGES[elemId];
    if (freqRange) block += `Frequency range: ${freqRange}\n`;

    // Melodic-specific: note lengths, pitch center, intervals
    if (isMelodic && pitchSet.size > 1) {
      const durations = notes.map((n) => n.duration || 0.25);
      const avgDur = durations.reduce((a, b) => a + b, 0) / durations.length;
      let durChar;
      if (avgDur >= 0.9) durChar = "legato";
      else if (avgDur >= 0.45) durChar = "~85% grid (legato gapped)";
      else if (avgDur >= 0.2) durChar = "staccato";
      else durChar = "very short";
      block += `Note lengths: ${durChar}\n`;

      const pitchCounts = {};
      notes.forEach((n) => {
        pitchCounts[n.pitch] = (pitchCounts[n.pitch] || 0) + 1;
      });
      const centerPitch = Number(
        Object.entries(pitchCounts).sort((a, b) => b[1] - a[1])[0][0]
      );
      block += `Pitch center: ${midiNoteName(centerPitch)} (gravity note)\n`;

      const intervals = [];
      for (let i = 1; i < sorted.length; i++) {
        const semitones = Math.abs(sorted[i].pitch - sorted[i - 1].pitch) % 12;
        const name = INTERVAL_NAMES[semitones];
        if (name && !intervals.includes(name)) intervals.push(name);
      }
      if (intervals.length > 0) {
        block += `Intervals used: ${intervals.join(", ")}\n`;
      }
    }

    blocks.push(block);
  });

  return blocks.length > 0 ? blocks.join("\n") : "";
}

// === Cross-Element Context Analysis (for Guided Mode) ===
// Analyzes all generated MIDI data to produce a compact summary of
// occupied/open beat positions, harmonic content, frequency ranges, density, and groove.
function buildContextAnalysis(elements, excludeElementId) {
  const bpm = parseInt(document.getElementById("bpm").value) || 128;
  const key = document.getElementById("key").value || "C";
  const scale = document.getElementById("scale").value || "minor";

  const allNotes = {};  // elemId -> notes array
  const occupiedPositions = new Set();  // "bar.beat.sub" strings
  const freqRangesCovered = new Set();
  const harmonicPitches = new Set();  // pitch classes (0-11) from melodic elements
  let totalNoteCount = 0;
  let maxBars = 0;

  Object.entries(elements).forEach(([elemId, elem]) => {
    if (elemId === excludeElementId) return;
    if (!elem.outputs || elem.outputs.length === 0) return;
    if (!["in_progress", "complete"].includes(elem.status)) return;

    const midiOutput = [...elem.outputs].reverse()
      .find((o) => o.type === "midi" && Array.isArray(o.notes) && o.notes.length > 0);
    if (!midiOutput) return;

    allNotes[elemId] = midiOutput.notes;
    totalNoteCount += midiOutput.notes.length;

    const bars = barsFromNotes(midiOutput.notes);
    if (bars > maxBars) maxBars = bars;

    // Track occupied positions
    midiOutput.notes.forEach((n) => {
      const pos = notePosition(n.start);
      occupiedPositions.add(pos);
    });

    // Track frequency ranges
    const fr = ELEMENT_FREQ_RANGES[elemId];
    if (fr) freqRangesCovered.add(fr);

    // Track harmonic content from melodic elements
    if (MELODIC_ELEMENTS.has(elemId)) {
      midiOutput.notes.forEach((n) => {
        harmonicPitches.add(n.pitch % 12);
      });
    }
  });

  if (Object.keys(allNotes).length === 0) return "";

  // Build analysis
  const lines = [];
  lines.push("CROSS-ELEMENT ANALYSIS:");
  lines.push(`Session: ${bpm} BPM, ${key} ${scale}, ${maxBars} bars`);
  lines.push(`Elements generated: ${Object.keys(allNotes).join(", ")}`);
  lines.push(`Total note density: ${totalNoteCount} notes across ${maxBars} bars`);

  // Beat density analysis — find busiest and emptiest positions
  const beatDensity = {};  // "beat.sub" -> count (collapsed across bars)
  Object.values(allNotes).forEach((notes) => {
    notes.forEach((n) => {
      const beatInBar = ((n.start - 1) % 4);
      const beat = Math.floor(beatInBar) + 1;
      const frac = beatInBar - Math.floor(beatInBar);
      const sub = Math.round(frac / 0.25) + 1;
      const pos = `${beat}.${sub}`;
      beatDensity[pos] = (beatDensity[pos] || 0) + 1;
    });
  });

  const sortedPositions = Object.entries(beatDensity).sort((a, b) => b[1] - a[1]);
  if (sortedPositions.length > 0) {
    const busiest = sortedPositions.slice(0, 4).map(([p, c]) => `${p}(${c})`).join(", ");
    lines.push(`Busiest beat positions: ${busiest}`);

    // Find open positions (subdivisions with no hits)
    const allSubs = [];
    for (let beat = 1; beat <= 4; beat++) {
      for (let sub = 1; sub <= 4; sub++) {
        allSubs.push(`${beat}.${sub}`);
      }
    }
    const openPositions = allSubs.filter((p) => !beatDensity[p]);
    if (openPositions.length > 0 && openPositions.length <= 8) {
      lines.push(`Open beat positions: ${openPositions.join(", ")}`);
    } else if (openPositions.length > 8) {
      lines.push(`Open positions: ${openPositions.length}/16 subdivisions open — sparse arrangement`);
    }
  }

  // Frequency coverage
  if (freqRangesCovered.size > 0) {
    lines.push(`Frequency ranges covered: ${[...freqRangesCovered].join(", ")}`);
    // Identify gaps
    const allRanges = ["Sub (30-80 Hz)", "Low-Mid (80-300 Hz)", "Mid (200-2000 Hz)", "Mid-High (500-5000 Hz)", "High (3-10 kHz)"];
    const uncovered = allRanges.filter((r) => {
      return ![...freqRangesCovered].some((covered) => covered.includes(r.split(" ")[0]));
    });
    if (uncovered.length > 0) {
      lines.push(`Frequency gaps: ${uncovered.join(", ")}`);
    }
  }

  // Harmonic content
  if (harmonicPitches.size > 0) {
    const pitchClassNames = [...harmonicPitches].sort((a, b) => a - b)
      .map((pc) => NOTE_NAMES[pc]);
    lines.push(`Pitch classes in use: ${pitchClassNames.join(", ")}`);
  }

  // Groove analysis — swing detection
  let onBeatHits = 0;
  let offBeatHits = 0;
  Object.values(allNotes).forEach((notes) => {
    notes.forEach((n) => {
      const frac = (n.start - 1) % 1;
      if (Math.abs(frac) < 0.01 || Math.abs(frac - 0.5) < 0.01) {
        onBeatHits++;
      } else {
        offBeatHits++;
      }
    });
  });
  const swingRatio = totalNoteCount > 0 ? offBeatHits / totalNoteCount : 0;
  if (swingRatio > 0.4) {
    lines.push("Groove character: heavy syncopation/swing");
  } else if (swingRatio > 0.2) {
    lines.push("Groove character: moderate swing/offbeat presence");
  } else {
    lines.push("Groove character: straight/on-beat dominant");
  }

  return lines.join("\n");
}

// === Element-Specific Generation Instructions ===
// Returns targeted instructions for the guided mode generation based on what already exists.
function buildElementSpecificInstructions(guidedEl, elements) {
  const instructions = [];

  const hasElement = (id) => {
    const e = elements[id];
    return e && e.outputs && e.outputs.length > 0;
  };

  switch (guidedEl.id) {
    case "kick":
      instructions.push("Generate the foundational kick pattern. This is the first element — establish the rhythmic backbone.");
      break;
    case "clap":
      if (hasElement("kick")) {
        instructions.push("The kick pattern exists. Place clap/snare to complement it — typically on beats 2 and 4, but check the kick positions to avoid masking.");
      }
      break;
    case "hats":
      if (hasElement("kick") || hasElement("clap")) {
        instructions.push("Kick and/or clap exist. Design hi-hats that weave between the existing drum hits. Fill gaps in the rhythmic grid, add 16th-note movement where the kick and clap leave space.");
      }
      break;
    case "perc":
      if (hasElement("kick") || hasElement("hats")) {
        instructions.push("Core drums exist. Add percussion that complements without cluttering. Target open beat positions — use the cross-element analysis to find rhythmic gaps.");
      }
      break;
    case "bass":
      if (hasElement("kick")) {
        instructions.push("Kick pattern exists. Lock the bass to the kick rhythm — root notes typically align with kick hits, with movement between kicks. Respect sidechain ducking.");
      }
      instructions.push("Bass should sit in Sub (30-80 Hz) for sub and Low-Mid (80-300 Hz) for character. Keep mono below 150 Hz.");
      break;
    case "chords":
      if (hasElement("sub") || hasElement("midbass")) {
        instructions.push("Bass exists. Chords/pads should sit above the bass frequency range (above 300 Hz). Avoid root-heavy voicings that clash with the bass fundamental.");
      }
      instructions.push("Use the session key and scale. Chord voicings should complement existing melodic content if any.");
      break;
    case "lead":
      instructions.push("This is the melodic hook. It should be memorable and sit in a frequency range that cuts through the existing arrangement.");
      if (hasElement("chords") || hasElement("pad") || hasElement("stabs")) {
        instructions.push("Harmonic content already exists — use complementary intervals. Create call-and-response with existing melodic elements.");
      }
      break;
    case "vocals":
      instructions.push("Describe a vocal arrangement approach rather than MIDI. Consider vocal style, processing chain, rhythmic placement relative to existing elements.");
      break;
    case "fx":
      instructions.push("Generate FX and transition ideas. Consider risers, impacts, sweeps that work with the arrangement. These are arrangement automation tools, not permanent layers.");
      break;
  }

  return instructions.length > 0 ? instructions.join(" ") : "";
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

    const musicalContext = buildMusicalContext(sessionState.elements);
    const result = await API.chat(
      apiMessages,
      getSession(),
      getGenre(),
      elementId,
      buildElementHistory(),
      sessionState.skillLevel,
      musicalContext,
      sessionState.sessionId
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
      elem.summary = result.output.musical_summary || result.output.description || result.output.name || "";
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

    const musicalContext = buildMusicalContext(sessionState.elements);
    const result = await API.chat(
      apiMessages,
      getSession(),
      getGenre(),
      null,
      buildElementHistory(),
      sessionState.skillLevel,
      musicalContext,
      sessionState.sessionId
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

// === Spotify Integration ===
async function checkSpotifyStatus() {
  try {
    const status = await API.getSpotifyStatus();
    const connectBtn = $("#spotify-connect-btn");
    const connectedNav = $("#spotify-connected-nav");

    if (status.connected) {
      connectBtn.classList.add("hidden");
      connectedNav.classList.remove("hidden");
      $("#spotify-nav-user").textContent = status.display_name || "";
      sessionState.spotifyProfile = status;
    } else {
      connectBtn.classList.remove("hidden");
      connectedNav.classList.add("hidden");
      sessionState.spotifyProfile = null;
    }
  } catch (e) {
    // Spotify status endpoint not available — keep defaults
  }
}

// === Spotify Disconnect ===
$("#spotify-disconnect-btn").addEventListener("click", async () => {
  try {
    await API.disconnectSpotify();
  } catch (e) {
    window.location.href = "/api/spotify/disconnect";
    return;
  }
  $("#spotify-connect-btn").classList.remove("hidden");
  $("#spotify-connected-nav").classList.add("hidden");
  $("#spotify-nav-user").textContent = "";
  sessionState.spotifyProfile = null;
});

// === SoundCloud Integration ===
async function checkSoundCloudStatus() {
  try {
    const status = await API.getSoundCloudStatus();
    const connectBtn = $("#soundcloud-connect-btn");
    const connectedNav = $("#soundcloud-connected-nav");

    if (status.connected) {
      connectBtn.classList.add("hidden");
      connectedNav.classList.remove("hidden");
      $("#soundcloud-nav-user").textContent = status.display_name || "";
      sessionState.soundcloudProfile = status;
    } else {
      connectBtn.classList.remove("hidden");
      connectedNav.classList.add("hidden");
      sessionState.soundcloudProfile = null;
    }
  } catch (e) {
    // SoundCloud status endpoint not available — keep defaults
  }
}

// === SoundCloud Disconnect ===
$("#soundcloud-disconnect-btn").addEventListener("click", async () => {
  try {
    await API.disconnectSoundCloud();
  } catch (e) {
    return;
  }
  $("#soundcloud-connect-btn").classList.remove("hidden");
  $("#soundcloud-connected-nav").classList.add("hidden");
  $("#soundcloud-nav-user").textContent = "";
  sessionState.soundcloudProfile = null;
});

// === Init ===
(async function init() {
  sendBtn.classList.add("dimmed");
  generalSendBtn.classList.add("dimmed");

  const _savedSession = await loadSession();
  await loadPresets();
  if (_savedSession && _savedSession.genre) {
    genreSelect.value = _savedSession.genre;
    updatePresetDesc();
  }
  _sessionReady = true;
  updateTrackCount();

  // Apply mode visibility after session restore
  const guidedArea = $("#guided-area");
  const studioArea = $("#studio-area");
  const chatSection = $("#element-chat");
  const resizeHandle = $("#resize-handle");
  if (sessionState.mode === "guided") {
    guidedArea.classList.remove("hidden");
    studioArea.classList.add("hidden");
    if (chatSection) chatSection.classList.add("hidden");
    if (resizeHandle) resizeHandle.classList.add("hidden");
    renderGuidedElements();
  } else {
    guidedArea.classList.add("hidden");
    studioArea.classList.remove("hidden");
    if (chatSection) chatSection.classList.remove("hidden");
    if (resizeHandle) resizeHandle.classList.remove("hidden");
  }

  // Check service statuses (non-blocking)
  checkSpotifyStatus();
  checkSoundCloudStatus();
})();

// Persist on session settings change
$("#bpm").addEventListener("change", saveSession);
$("#key").addEventListener("change", saveSession);
$("#scale").addEventListener("change", saveSession);
genreSelect.addEventListener("change", saveSession);

// Download All — zip bundle
$("#download-all-btn").addEventListener("click", async () => {
  const bpm = parseInt($("#bpm").value) || 128;
  const allOutputs = [];

  Object.entries(sessionState.elements).forEach(([id, elem]) => {
    elem.outputs.forEach((o) => {
      if (o.type === "midi" && Array.isArray(o.notes) && o.notes.length > 0) {
        allOutputs.push({ ...o, element: id });
      }
    });
  });
  sessionState.generalOutputs.forEach((o) => {
    if (o.type === "midi" && Array.isArray(o.notes) && o.notes.length > 0) {
      allOutputs.push(o);
    }
  });

  if (allOutputs.length === 0) return;

  const zip = new JSZip();
  const fileLines = [];

  allOutputs.forEach((o) => {
    const bars = barsFromNotes(o.notes);
    const elemName = o.element || "general";
    const filename = `${elemName}_${bars}bar.mid`;
    const blob = generateMidiBlob(o.notes, bpm);
    zip.file(filename, blob);

    const vels = o.notes.map((n) => n.velocity || 100);
    const minVel = Math.min(...vels);
    const maxVel = Math.max(...vels);
    fileLines.push(`- ${filename} (${o.notes.length} notes, vel ${minVel}-${maxVel})`);
  });

  const keyVal = $("#key").value || "C";
  const scaleVal = $("#scale").value || "minor";
  const scaleCap = scaleVal.charAt(0).toUpperCase() + scaleVal.slice(1);
  const genre = genreSelect.options[genreSelect.selectedIndex]?.text || "Tech House";
  const modeCap = sessionState.mode.charAt(0).toUpperCase() + sessionState.mode.slice(1);
  const today = new Date().toISOString().split("T")[0];

  const sessionInfo = `DAW Brain Session Export
Date: ${today}
BPM: ${bpm}
Key: ${keyVal} ${scaleCap}
Genre: ${genre}
Mode: ${modeCap}

Included Files:
${fileLines.join("\n")}
`;

  zip.file("session_info.txt", sessionInfo);

  const zipBlob = await zip.generateAsync({ type: "blob" });
  const url = URL.createObjectURL(zipBlob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `BeatBrain_Session_${today}.zip`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

// Clear session
$("#clear-session-btn").addEventListener("click", clearSession);
$("#guided-clear-session-btn").addEventListener("click", clearSession);

// Guided download all
$("#guided-download-all-btn").addEventListener("click", async () => {
  const bpm = parseInt($("#bpm").value) || 128;
  const allOutputs = [];

  GUIDED_ELEMENTS.forEach((gel) => {
    gel.mapTo.forEach((id) => {
      const elem = sessionState.elements[id];
      if (!elem || !elem.outputs) return;
      elem.outputs.forEach((o) => {
        if (o.type === "midi" && Array.isArray(o.notes) && o.notes.length > 0) {
          allOutputs.push({ ...o, element: id });
        }
      });
    });
  });

  if (allOutputs.length === 0) return;

  const zip = new JSZip();
  const fileLines = [];

  allOutputs.forEach((o) => {
    const bars = barsFromNotes(o.notes);
    const elemName = o.element || "general";
    const filename = `${elemName}_${bars}bar.mid`;
    const blob = generateMidiBlob(o.notes, bpm);
    zip.file(filename, blob);
    const vels = o.notes.map((n) => n.velocity || 100);
    fileLines.push(`- ${filename} (${o.notes.length} notes, vel ${Math.min(...vels)}-${Math.max(...vels)})`);
  });

  const keyVal = $("#key").value || "C";
  const scaleVal = $("#scale").value || "minor";
  const genre = genreSelect.options[genreSelect.selectedIndex]?.text || "Tech House";
  const today = new Date().toISOString().split("T")[0];

  zip.file("session_info.txt", `DAW Brain Guided Session Export\nDate: ${today}\nBPM: ${bpm}\nKey: ${keyVal} ${scaleVal}\nGenre: ${genre}\n\nFiles:\n${fileLines.join("\n")}\n`);

  const zipBlob = await zip.generateAsync({ type: "blob" });
  const url = URL.createObjectURL(zipBlob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `DAWBrain_Guided_${today}.zip`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
