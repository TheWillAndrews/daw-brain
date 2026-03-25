const API = {
  async chat(messages, session, genre, activeElement, elementHistory, skillLevel) {
    const body = { messages, session, genre };
    if (activeElement) body.activeElement = activeElement;
    if (elementHistory) body.elementHistory = elementHistory;
    if (skillLevel) body.skillLevel = skillLevel;

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
};
