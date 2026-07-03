const API = {
  async chat(messages, session, genre, activeElement, elementHistory, skillLevel, musicalContext, sessionId) {
    const body = { messages, session, genre };
    if (activeElement) body.activeElement = activeElement;
    if (elementHistory) body.elementHistory = elementHistory;
    if (skillLevel) body.skillLevel = skillLevel;
    if (musicalContext) body.musicalContext = musicalContext;
    if (sessionId) body.sessionId = sessionId;

    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: "Request failed" }));
      throw new Error(err.error || "Request failed");
    }
    return res.json();
  },

  async getPresets() {
    const res = await fetch("/api/presets");
    if (!res.ok) throw new Error("Failed to load presets");
    return res.json();
  },

  async separateVocals(file) {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch("/api/vocals/separate", {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: "Request failed" }));
      throw new Error(err.error || "Separation failed");
    }
    return res.json();
  },

  // ─── Session Management ────────────────────────────────────

  async getActiveSession() {
    const res = await fetch("/api/sessions/active");
    if (res.status === 204) return null;
    if (!res.ok) throw new Error("Failed to load session");
    return res.json();
  },

  async saveSessionState(state) {
    const res = await fetch("/api/sessions/state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state),
    });
    if (!res.ok) throw new Error("Failed to save session");
    return res.json();
  },

  async createSession(data) {
    const res = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data || {}),
    });
    if (!res.ok) throw new Error("Failed to create session");
    return res.json();
  },

  async listSessions() {
    const res = await fetch("/api/sessions");
    if (!res.ok) throw new Error("Failed to list sessions");
    return res.json();
  },

  async clearActiveSession() {
    const res = await fetch("/api/sessions/active", { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to clear session");
  },

  async getSessionElements(sessionId) {
    const res = await fetch(`/api/sessions/${sessionId}/elements`);
    if (!res.ok) throw new Error("Failed to load elements");
    return res.json();
  },

  async getSessionOutputs(sessionId) {
    const res = await fetch(`/api/sessions/${sessionId}/outputs`);
    if (!res.ok) throw new Error("Failed to load outputs");
    return res.json();
  },

  // ─── Spotify ────────────────────────────────────────────────

  async getSpotifyStatus() {
    const res = await fetch("/api/spotify/status");
    if (!res.ok) throw new Error("Failed to get Spotify status");
    return res.json();
  },

  async disconnectSpotify() {
    const res = await fetch("/api/spotify/disconnect", { method: "POST" });
    if (!res.ok) throw new Error("Failed to disconnect Spotify");
    return res.json();
  },

  async refreshSpotify() {
    const res = await fetch("/api/spotify/refresh", { method: "POST" });
    if (!res.ok) throw new Error("Failed to refresh Spotify data");
    return res.json();
  },

  // ─── SoundCloud ─────────────────────────────────────────────

  async getSoundCloudStatus() {
    const res = await fetch("/api/soundcloud/status");
    if (!res.ok) throw new Error("Failed to get SoundCloud status");
    return res.json();
  },

  async disconnectSoundCloud() {
    const res = await fetch("/api/soundcloud/disconnect", { method: "POST" });
    if (!res.ok) throw new Error("Failed to disconnect SoundCloud");
    return res.json();
  },

  async refreshSoundCloud() {
    const res = await fetch("/api/soundcloud/refresh", { method: "POST" });
    if (!res.ok) throw new Error("Failed to refresh SoundCloud data");
    return res.json();
  },
};
