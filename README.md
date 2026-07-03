# DAW Brain

AI music production assistant for Ableton Live.

## Repo layout

- **`backend/`** — Python/Flask server: the brain. `app.py` plus the `brain/`
  package (knowledge engine, MIDI generation, vocal separation, Spotify and
  SoundCloud integrations, SQLite persistence) and the `static/` web UI.
- **`desktop/`** — cross-platform Electron wrapper (macOS + Windows). Spawns
  the Flask backend (`python app.py` from `../backend`) and loads the UI in a
  desktop window.
- **`launcher/`** — double-clickable launchers that resolve the repo location
  relative to themselves: `DAW Brain.app` (macOS bundle) and `DAW Brain.bat`
  (Windows).
- **`docs/`** — reference material: the Ableton Live 12 knowledge base and
  the pitch deck (`docs/pitch/`).

## Running

Prerequisites: Node.js, Python 3.11+, and `pip install -r backend/requirements.txt`.

```sh
# desktop app (dev) — either platform
cd desktop && npm install && npm start

# backend only (macOS)
cd backend && ./launch.sh
```

Or double-click `launcher/DAW Brain.app` (macOS) / `launcher/DAW Brain.bat`
(Windows).

The app reads `ANTHROPIC_API_KEY` from `backend/.env` (gitignored), `~/.env`,
or the environment. The `.env` file should contain
`ANTHROPIC_API_KEY=sk-ant-...`.
