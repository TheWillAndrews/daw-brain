const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  /** Trigger native file drag from the app to Finder / Ableton / etc. */
  startDrag: (filePath) => ipcRenderer.send("ondragstart", filePath),

  /**
   * Write a MIDI blob (as Uint8Array) to disk so it can be dragged.
   * Returns the absolute file path.
   */
  writeMidi: (bytes, filename) =>
    ipcRenderer.invoke("write-midi", Array.from(bytes), filename),
});
