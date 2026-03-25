const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const { spawn, execSync } = require("child_process");
const path = require("path");
const http = require("http");
const fs = require("fs");

const PORT = 5050;
const POLL_INTERVAL = 500;
const POLL_TIMEOUT = 15000;

// Find Python 3 — try common locations, fall back to PATH
function findPython() {
  const candidates = [
    "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3",
    "/usr/local/bin/python3",
    "/opt/homebrew/bin/python3",
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return "python3"; // rely on PATH
}

let mainWindow = null;
let flaskProcess = null;
let serverReady = false;

// --- Resolve backend path ---
// In dev: ./backend (symlink to daw-brain/)
// In packaged app: process.resourcesPath/backend
function getBackendPath() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "backend");
  }
  return path.join(__dirname, "backend");
}

// --- Load ANTHROPIC_API_KEY from the backend .env file ---
function loadApiKey() {
  const envPaths = [
    path.join(getBackendPath(), ".env"),
    path.join(process.env.HOME || "", ".env"),
  ];

  for (const envPath of envPaths) {
    try {
      const content = fs.readFileSync(envPath, "utf8");
      const match = content.match(
        /(?:export\s+)?ANTHROPIC_API_KEY\s*=\s*(.+)/
      );
      if (match) {
        return match[1].trim().replace(/^["']|["']$/g, "");
      }
    } catch (_) {
      // File doesn't exist, try next
    }
  }

  // Fallback: try sourcing zshrc
  try {
    const result = execSync(
      'source ~/.zshrc 2>/dev/null; echo "$ANTHROPIC_API_KEY"',
      { shell: "/bin/zsh", encoding: "utf8", timeout: 5000 }
    );
    const key = result.trim();
    if (key && key.startsWith("sk-")) return key;
  } catch (_) {
    // zshrc source failed
  }

  return null;
}

// --- Check if server is already running ---
function checkServer() {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${PORT}/`, (res) => {
      resolve(true);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(1000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

// --- Start Flask server ---
function startFlask(apiKey) {
  const backendPath = getBackendPath();
  const logPath = path.join(backendPath, "server.log");

  // Ensure outputs directory exists
  const outputsDir = path.join(backendPath, "outputs");
  if (!fs.existsSync(outputsDir)) {
    fs.mkdirSync(outputsDir, { recursive: true });
  }

  const env = {
    ...process.env,
    ANTHROPIC_API_KEY: apiKey,
    PYTHONUNBUFFERED: "1",
  };

  const logStream = fs.createWriteStream(logPath, { flags: "a" });

  flaskProcess = spawn(findPython(), ["app.py"], {
    cwd: backendPath,
    env: env,
    stdio: ["ignore", "pipe", "pipe"],
  });

  flaskProcess.stdout.pipe(logStream);
  flaskProcess.stderr.pipe(logStream);

  flaskProcess.on("error", (err) => {
    console.error("Failed to start Flask:", err.message);
  });

  flaskProcess.on("exit", (code, signal) => {
    console.log(`Flask exited: code=${code}, signal=${signal}`);
    flaskProcess = null;
  });

  return flaskProcess;
}

// --- Poll until server responds ---
function waitForServer() {
  return new Promise((resolve, reject) => {
    const start = Date.now();

    function poll() {
      checkServer().then((alive) => {
        if (alive) {
          serverReady = true;
          resolve();
        } else if (Date.now() - start > POLL_TIMEOUT) {
          reject(new Error("Flask server did not start within 15 seconds."));
        } else if (flaskProcess && flaskProcess.exitCode !== null) {
          reject(
            new Error(
              `Flask process exited with code ${flaskProcess.exitCode}. Check server.log.`
            )
          );
        } else {
          setTimeout(poll, POLL_INTERVAL);
        }
      });
    }

    poll();
  });
}

// --- Kill Flask on quit ---
function killFlaskSync() {
  try {
    execSync(`lsof -ti:${PORT} | xargs kill -9 2>/dev/null`, {
      shell: "/bin/zsh",
      timeout: 3000,
    });
  } catch (_) {}

  if (flaskProcess) {
    try {
      flaskProcess.kill("SIGKILL");
    } catch (_) {}
    flaskProcess = null;
  }
}

function killFlask() {
  if (!flaskProcess) {
    killFlaskSync();
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    const proc = flaskProcess;
    flaskProcess = null;

    const forceKill = setTimeout(() => {
      try {
        proc.kill("SIGKILL");
      } catch (_) {}
      killFlaskSync();
      resolve();
    }, 3000);

    proc.on("exit", () => {
      clearTimeout(forceKill);
      resolve();
    });

    try {
      proc.kill("SIGTERM");
    } catch (_) {
      clearTimeout(forceKill);
      killFlaskSync();
      resolve();
    }
  });
}

process.on("exit", killFlaskSync);

// --- IPC: Native file drag (for dragging MIDI into Ableton) ---
const dragIconPath = path.join(__dirname, "drag-icon.png");

ipcMain.on("ondragstart", (event, filePath) => {
  // filePath is relative like "outputs/kick_pattern.mid"
  const absolute = path.resolve(getBackendPath(), filePath);
  if (fs.existsSync(absolute)) {
    event.sender.startDrag({
      file: absolute,
      icon: dragIconPath,
    });
  }
});

ipcMain.handle("write-midi", (_event, bytesArray, filename) => {
  const outputsDir = path.join(getBackendPath(), "outputs");
  if (!fs.existsSync(outputsDir)) {
    fs.mkdirSync(outputsDir, { recursive: true });
  }
  const safeName = filename.replace(/[^a-zA-Z0-9_\-.]/g, "_");
  const filePath = path.join(outputsDir, safeName);
  fs.writeFileSync(filePath, Buffer.from(bytesArray));
  return path.join("outputs", safeName);
});

// --- Electron drag region CSS ---
// With titleBarStyle:'hiddenInset', Electron overlays macOS traffic lights on
// the page content. We need to:
//  1. Make the top-nav the window drag handle (so the window is draggable)
//  2. Exclude all interactive children so clicks still work
//  3. Pad the left side so content clears the traffic lights
//  4. Ensure everything below the top-nav is NOT a drag region
const ELECTRON_CSS = `
  /* Make the top nav the window drag bar */
  .top-nav {
    -webkit-app-region: drag;
    padding-left: 78px !important;
  }

  /* All interactive elements inside top-nav must opt out of drag */
  .top-nav-tabs,
  .top-nav-tab,
  .top-nav-right,
  .top-nav-right *,
  .theme-toggle,
  .skill-level-pills,
  .skill-pill {
    -webkit-app-region: no-drag;
  }

  /* Everything below the nav is normal content — not draggable */
  .session-bar,
  .kanban-area,
  .element-chat,
  .resize-handle,
  .view,
  .midi-draggable {
    -webkit-app-region: no-drag;
  }
`;

// --- Create the window ---
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    titleBarStyle: "hiddenInset",
    trafficLightPosition: { x: 16, y: 14 },
    backgroundColor: "#0a0a10",
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
  });

  // Show loading screen immediately
  mainWindow.loadFile("loading.html");
  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  return mainWindow;
}

// --- App lifecycle ---
app.whenReady().then(async () => {
  // 1. Load API key
  const apiKey = loadApiKey();
  if (!apiKey) {
    dialog.showErrorBox(
      "DAW Brain — Missing API Key",
      "Could not find ANTHROPIC_API_KEY.\n\n" +
        "Make sure your key is in one of these locations:\n" +
        "  • ~/Desktop/TRK_TOOLS/daw-brain/.env\n" +
        "  • ~/.zshrc (export ANTHROPIC_API_KEY=sk-...)\n\n" +
        "The .env file should contain:\n" +
        "ANTHROPIC_API_KEY=sk-ant-..."
    );
    app.quit();
    return;
  }

  // 2. Create window with loading screen
  createWindow();

  // 3. Check if Flask is already running
  const alreadyRunning = await checkServer();

  if (!alreadyRunning) {
    // 4. Start Flask
    startFlask(apiKey);

    try {
      await waitForServer();
    } catch (err) {
      dialog.showErrorBox(
        "DAW Brain — Server Error",
        `${err.message}\n\nCheck the log at:\n${path.join(getBackendPath(), "server.log")}\n\nMake sure Python 3.11 is installed and all dependencies are available:\n  pip3 install flask anthropic midiutil`
      );
      app.quit();
      return;
    }
  } else {
    serverReady = true;
  }

  // 5. Load the app and inject Electron-specific CSS
  if (mainWindow) {
    mainWindow.loadURL(`http://127.0.0.1:${PORT}`);
    mainWindow.webContents.once("did-finish-load", () => {
      mainWindow.webContents.insertCSS(ELECTRON_CSS);
    });
  }
});

app.on("window-all-closed", () => {
  app.quit();
});

app.on("will-quit", (e) => {
  if (flaskProcess) {
    e.preventDefault();
    killFlask().then(() => {
      app.quit();
    });
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0 && serverReady) {
    createWindow();
    if (mainWindow) {
      mainWindow.loadURL(`http://127.0.0.1:${PORT}`);
      mainWindow.webContents.once("did-finish-load", () => {
        mainWindow.webContents.insertCSS(ELECTRON_CSS);
      });
    }
  }
});
