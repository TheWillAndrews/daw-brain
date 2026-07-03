# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

DAW Brain — an AI music production assistant for Ableton Live. A Python/Flask backend calls the Anthropic API to generate MIDI patterns, arrangements, and device-chain parameters for electronic music (tech house focus), personalized by the user's Spotify/SoundCloud listening taste. A vanilla-JS web UI is served by Flask and optionally wrapped in Electron for desktop.

## Commands

```sh
# Install backend deps (Python 3.11+)
pip install -r backend/requirements.txt

# Run backend only — serves UI at http://127.0.0.1:5050
cd backend && python app.py            # python3 on macOS
cd backend && python app.py --debug    # Flask debug mode, disables the watchdog (see Gotchas)

# Desktop app (Electron spawns the Flask backend itself)
cd desktop && npm install && npm start

# Package desktop app (currently macOS-only config)
cd desktop && npm run build
```

Double-click launchers: `launcher/DAW Brain.bat` (Windows, runs `npm start` in `desktop/`) and `launcher/DAW Brain.app` (macOS). `backend/launch.sh` is a macOS-only backend launcher.

There are no tests and no linter configured in this repo.

## Configuration / environment

- `ANTHROPIC_API_KEY` — read from the environment, `backend/.env`, or `~/.env` (Electron parses the `.env` files itself in `desktop/main.js`; on macOS it also falls back to sourcing `~/.zshrc`).
- `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` and `SOUNDCLOUD_CLIENT_ID` / `SOUNDCLOUD_CLIENT_SECRET` — required for the OAuth integrations. The backend's fallback of sourcing `~/.zshrc` (`spotify_auth._load_env_from_shell`) only works on macOS; on Windows these must be real environment variables.
- OAuth redirect URIs are hardcoded to `http://127.0.0.1:5050/callback/spotify` and `/callback/soundcloud` — the port and host must match the app registrations.
- Port **5050** is hardcoded in both `backend/app.py` and `desktop/main.js`; change both or neither.
- All persistent data lives in `~/.daw-brain/`: `dawbrain.db` (SQLite, WAL mode) and `.flask_secret`. Generated files (MIDI, JSON, vocal stems) go to `backend/outputs/` (gitignored).

## Architecture

### Chat → generation pipeline (the core loop)

`POST /api/chat` in `backend/app.py` drives everything:

1. `brain/system_prompts.py: build_system_prompt()` assembles the system prompt from: the genre preset (`brain/presets/` — tech_house, uk_bass, minimal_tech, bassline), keyword-routed knowledge bases, skill-level response style, musical context built from the session's prior outputs in SQLite (`build_musical_context_from_db`), and the listener taste profile (`build_taste_context`).
2. Knowledge routing: `brain/knowledge/__init__.py` scores each `brain/knowledge/*.md` file against the user's message by keyword hits and loads at most 3; `tech_house_production.md` is always loaded. New knowledge files must be registered in `KNOWLEDGE_MAP` there.
3. The Anthropic API is called (model set inline in `app.py`), and `brain/output_parser.py` extracts an `[OUTPUT]...[/OUTPUT]` JSON block from the response. Valid types: `midi` (needs `notes`), `arrangement` (needs `sections`), `parameters` (needs `chain`).
4. `midi` outputs become `.mid` files via `brain/midi_generator.py` (mido, 480 PPQ, note `start` is 1-based in beats); `arrangement`/`parameters` are written as JSON. Both land in `backend/outputs/` and are served at `/outputs/<file>`. Outputs are also saved to SQLite for history/analytics.

### Taste pipeline (Spotify / SoundCloud)

OAuth connect (`brain/spotify_auth.py` / `soundcloud_auth.py`, tokens in SQLite) kicks off a background thread: collector (`*_collector.py`) fetches raw listening data into SQLite → profile (`*_profile.py`) computes a taste profile → `artist_researcher.py` / `soundcloud_researcher.py` use Claude to generate structured per-artist "production DNA" JSON profiles (schema v1.0.0, cached in `artist_research_cache` with confidence scores and expiry) → `taste_aggregator.py` / `genre_attributes.py` aggregate these into the profile injected into system prompts as the LISTENER PROFILE section. Spotify deprecated genre tags (Nov 2024), so AI artist research is the primary taste source, not Spotify genre data.

`/diagnostic` (page) and `/api/spotify/diagnostic` (JSON) report the health of this pipeline as 7 explicit stages — use them first when debugging taste-profile issues.

### Database

`brain/database.py` is the single data layer (~2300 lines): schema (in the `SCHEMA` string, `CREATE TABLE IF NOT EXISTS`), all queries, and music-theory constants. **There is no migration system** — altering an existing table needs manual handling for existing `~/.daw-brain/dawbrain.db` files; new tables/columns via `CREATE TABLE IF NOT EXISTS` only apply to fresh DBs. A single default user exists until a Spotify/SoundCloud login binds a real user to the Flask session cookie.

### Frontend

`backend/static/` — no framework, no build step: `index.html`, `app.js` (all state + UI, ~2200 lines), `api.js` (fetch wrappers), `styles.css`. Session state auto-saves to the backend (`/api/sessions/state`). Two UI modes: "guided" and "studio" (persisted in localStorage).

### The 23 track elements

Elements (kick, hats, sub, midbass, stabs, chords, mainvox, risers, …) are the app's core domain concept, grouped into drums/bass/melodic/vocals/fx. They are defined in **three places that must stay in sync** when adding or renaming an element:

- `brain/database.py: ELEMENT_CATEGORIES` (+ frequency ranges, drum/melodic sets)
- `brain/system_prompts.py: ELEMENT_NAMES` and `ELEMENT_KB_HINTS`
- `static/app.js: ELEMENT_DEFS`

### Electron wrapper

`desktop/main.js`: locates a working Python (filters out the Windows Store stub), spawns `python app.py` in `../backend` (or `resources/backend` when packaged), polls port 5050 until ready, then loads the URL. Flask stdout/stderr go to `backend/server.log` — check there when the desktop app fails to start. On quit it kills whatever is listening on port 5050.

## Gotchas

- **Watchdog:** the browser UI POSTs `/api/heartbeat`; without heartbeats the server calls `os._exit(0)` after the timeout (`HEARTBEAT_TIMEOUT` in `app.py`). If you run the backend headless (e.g. testing with curl), it will eventually kill itself — run with `--debug` to disable the watchdog.
- Vocal separation (`brain/vocal_separator.py`) shells out to the `audio-separator` CLI (Kim_Vocal_2.onnx) — an external install not in `requirements.txt`, and its PATH augmentation is macOS-specific (`/opt/homebrew/bin` etc.).
- Cross-platform: this repo targets macOS and Windows. Watch for macOS-only assumptions (zshrc sourcing, `lsof`, `open`) — Windows equivalents live behind `isWin` checks in `desktop/main.js`.
- The Anthropic model ID is hardcoded in two places: `app.py` (chat) and `brain/artist_researcher.py` (artist research).
