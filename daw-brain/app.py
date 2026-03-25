import os
import sys
import json
import time
import logging
import tempfile
import traceback
import threading
from flask import Flask, request, jsonify, send_from_directory, redirect, session
import anthropic

from brain.system_prompts import build_system_prompt, build_taste_context
from brain.output_parser import parse_response
from brain.midi_generator import generate_midi, sanitize_filename
from brain.presets import list_presets
from brain.vocal_separator import separate_vocals, OUTPUT_DIR as STEMS_DIR
from brain.database import (
    init_db, ensure_default_user, get_connection,
    save_full_session_state, load_full_session_state,
    create_session, get_active_session, get_user_sessions,
    update_session, get_all_elements, get_session_outputs,
    clear_session, delete_session, save_output,
    build_musical_context_from_db,
    get_spotify_tokens, get_taste_profile, disconnect_spotify,
    get_user_top_artists,
    get_soundcloud_tokens, get_soundcloud_taste_profile,
    disconnect_soundcloud, get_user,
)
from brain.spotify_auth import get_auth_url, handle_callback
from brain.spotify_collector import collect_all_spotify_data
from brain.spotify_profile import compute_taste_profile, build_genre_sources, get_excluded_sources
from brain.genre_attributes import compute_weighted_taste
from brain.artist_researcher import start_background_research
from brain.soundcloud_auth import (
    get_auth_url as sc_get_auth_url,
    handle_callback as sc_handle_callback,
)
from brain.soundcloud_collector import collect_all_soundcloud_data
from brain.soundcloud_profile import compute_soundcloud_taste_profile
from brain.soundcloud_researcher import start_soundcloud_background_research

app = Flask(__name__, static_folder="static")
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB upload limit
# Stable secret key — persisted so session cookies survive server restarts
_secret_key_path = os.path.join(os.path.expanduser("~/.daw-brain"), ".flask_secret")
if os.path.exists(_secret_key_path):
    with open(_secret_key_path) as f:
        app.secret_key = f.read().strip()
else:
    app.secret_key = os.urandom(24).hex()
    os.makedirs(os.path.dirname(_secret_key_path), exist_ok=True)
    with open(_secret_key_path, "w") as f:
        f.write(app.secret_key)

# Logging setup — prints to terminal with timestamps
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("daw-brain")

OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "outputs")
ALLOWED_AUDIO_EXTENSIONS = {'.wav', '.mp3', '.flac', '.m4a'}

client = anthropic.Anthropic()

# Initialize database and default user
init_db()
DEFAULT_USER_ID = ensure_default_user()
log.info(f"Database ready, default user_id={DEFAULT_USER_ID}")

def get_current_user_id():
    """Get the current user_id from Flask session cookie, or fall back to default."""
    return session.get("user_id", DEFAULT_USER_ID)


# Heartbeat: browser pings every 3s, server shuts down after 10s of silence
last_heartbeat = time.time()
HEARTBEAT_TIMEOUT = 10


@app.route("/api/heartbeat", methods=["POST"])
def heartbeat():
    global last_heartbeat
    last_heartbeat = time.time()
    return "", 204


def watchdog():
    """Shuts down the server when the browser stops sending heartbeats."""
    # Give the browser 15s to load initially
    time.sleep(15)
    while True:
        if time.time() - last_heartbeat > HEARTBEAT_TIMEOUT:
            pidfile = os.path.join(os.path.dirname(__file__), ".server.pid")
            if os.path.exists(pidfile):
                os.remove(pidfile)
            os._exit(0)
        time.sleep(2)


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/static/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)


@app.route("/api/presets")
def get_presets():
    return jsonify(list_presets())


@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        messages = data.get("messages", [])
        session = data.get("session", {})
        genre = data.get("genre", "tech_house")
        active_element = data.get("activeElement", None)
        element_history = data.get("elementHistory", None)
        skill_level = data.get("skillLevel", "expert")
        musical_context = data.get("musicalContext", "")
        session_id = data.get("sessionId", None)

        if not messages:
            return jsonify({"error": "No messages provided"}), 400

        # Extract the latest user message for knowledge routing
        latest_user_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                latest_user_msg = msg.get("content", "")
                break

        log.info(f"Chat request — element: {active_element}, genre: {genre}, msg: {latest_user_msg[:80]}")

        # Build musical context from DB if session_id available and no
        # frontend-provided context
        if session_id and not musical_context:
            try:
                musical_context = build_musical_context_from_db(
                    session_id,
                    session.get("bpm", 128),
                    session.get("key", "E"),
                    session.get("scale", "minor")
                )
            except Exception as e:
                log.warning(f"DB musical context failed: {e}")

        user_id = get_current_user_id()

        system_prompt = build_system_prompt(
            session, genre, user_message=latest_user_msg,
            active_element=active_element, element_history=element_history,
            skill_level=skill_level, musical_context=musical_context,
            session_id=session_id, user_id=user_id
        )

        try:
            t0 = time.time()
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
            )
            generation_ms = int((time.time() - t0) * 1000)
        except Exception as e:
            log.error(f"Anthropic API error: {e}")
            return jsonify({"error": f"API error: {str(e)}"}), 500

        raw_text = response.content[0].text
        cleaned_text, output_data = parse_response(raw_text)

        result = {"text": cleaned_text, "output": output_data, "file_url": None}

        # Dev diagnostic: include full system prompt when diagnostic flag is set
        if data.get("diagnostic"):
            result["debug_system_prompt"] = system_prompt

        if output_data and output_data.get("type") == "midi":
            bpm = session.get("bpm", 128)
            filename = generate_midi(output_data, bpm=bpm)
            if filename:
                result["file_url"] = f"/outputs/{filename}"
                log.info(f"Generated MIDI: {filename}")

        # For arrangement and parameters, save as JSON
        if output_data and output_data.get("type") in ("arrangement", "parameters"):
            name = output_data.get("name", "output")
            safe_name = sanitize_filename(name)
            filename = f"{safe_name}.json"
            os.makedirs(OUTPUTS_DIR, exist_ok=True)
            filepath = os.path.join(OUTPUTS_DIR, filename)
            with open(filepath, "w") as f:
                json.dump(output_data, f, indent=2)
            result["file_url"] = f"/outputs/{filename}"
            log.info(f"Generated JSON: {filename}")

        # Save output to database for analytics/history
        if output_data and session_id:
            try:
                tokens = getattr(response, 'usage', None)
                token_count = (tokens.input_tokens + tokens.output_tokens) \
                    if tokens else None
                save_output(
                    session_id=session_id,
                    user_id=user_id,
                    element_name=active_element,
                    output_type=output_data.get("type"),
                    output_name=output_data.get("name"),
                    prompt_text=latest_user_msg,
                    midi_note_data=output_data.get("notes"),
                    arrangement_data=(output_data if output_data.get("type")
                                     == "arrangement" else None),
                    signal_chain_data=(output_data if output_data.get("type")
                                      == "parameters" else None),
                    bpm=session.get("bpm", 128),
                    key=session.get("key", "E"),
                    scale=session.get("scale", "minor"),
                    genre=genre,
                    skill_level=skill_level,
                    generation_time_ms=generation_ms,
                    tokens_used=token_count,
                )
            except Exception as e:
                log.warning(f"Failed to save output to DB: {e}")

        return jsonify(result)

    except Exception as e:
        log.error(f"Chat route crashed:\n{traceback.format_exc()}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route("/outputs/stems/<path:filename>")
def serve_stem(filename):
    return send_from_directory(STEMS_DIR, filename, as_attachment=False)


@app.route("/outputs/<path:filename>")
def serve_output(filename):
    return send_from_directory(OUTPUTS_DIR, filename, as_attachment=True)


@app.route("/api/vocals/separate", methods=["POST"])
def vocal_separate():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files['file']
        if not file.filename:
            return jsonify({"error": "No file selected"}), 400

        # Check file extension
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_AUDIO_EXTENSIONS:
            return jsonify({"error": "Unsupported format. Use WAV, MP3, FLAC, or M4A."}), 400

        log.info(f"Vocal separation started: {file.filename}")

        # Save to temp file
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        try:
            file.save(tmp.name)
            tmp.close()

            result = separate_vocals(tmp.name)

            if not result['vocal']:
                log.error("Separation produced no output files")
                return jsonify({"error": "Separation produced no output files"}), 500

            vocal_filename = os.path.basename(result['vocal'])
            vocal_size = os.path.getsize(result['vocal'])

            log.info(f"Vocal separation complete: {vocal_filename} ({vocal_size} bytes)")

            return jsonify({
                "status": "complete",
                "vocal_url": f"/outputs/stems/{vocal_filename}",
                "vocal_size": vocal_size,
            })
        except subprocess.TimeoutExpired:
            log.error("Vocal separation timed out (15 min limit)")
            return jsonify({"error": "Separation timed out (15 min limit). Try a shorter file."}), 500
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    except Exception as e:
        log.error(f"Vocal separator crashed:\n{traceback.format_exc()}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# ─── Session Management API ─────────────────────────────────────

@app.route("/api/sessions", methods=["GET"])
def list_sessions():
    sessions = get_user_sessions(get_current_user_id())
    return jsonify(sessions)


@app.route("/api/sessions", methods=["POST"])
def create_new_session():
    data = request.get_json() or {}
    session_id = create_session(
        get_current_user_id(),
        name=data.get("name", "Untitled Session"),
        bpm=data.get("bpm", 128),
        key=data.get("key", "E"),
        scale=data.get("scale", "minor"),
        genre=data.get("genre", "tech_house"),
        skill_level=data.get("skillLevel", "expert"),
    )
    return jsonify({"sessionId": session_id}), 201


@app.route("/api/sessions/<int:session_id>", methods=["PUT"])
def update_session_settings(session_id):
    data = request.get_json() or {}
    allowed = {"bpm", "key", "scale", "genre", "skill_level", "session_name",
               "tracks_in_session", "session_notes"}
    fields = {k: v for k, v in data.items() if k in allowed}
    if fields:
        update_session(session_id, **fields)
    return jsonify({"ok": True})


@app.route("/api/sessions/<int:session_id>/elements", methods=["GET"])
def get_elements(session_id):
    elements = get_all_elements(session_id)
    return jsonify(elements)


@app.route("/api/sessions/<int:session_id>/outputs", methods=["GET"])
def get_outputs(session_id):
    outputs = get_session_outputs(session_id)
    return jsonify(outputs)


@app.route("/api/sessions/active", methods=["GET"])
def get_active():
    """Load the active session's full state for the frontend."""
    state = load_full_session_state(get_current_user_id())
    if not state:
        return jsonify(None), 204
    return jsonify(state)


@app.route("/api/sessions/state", methods=["POST"])
def save_state():
    """Save the complete frontend session state to the database."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    try:
        session_id = save_full_session_state(get_current_user_id(), data)
        return jsonify({"sessionId": session_id})
    except Exception as e:
        log.error(f"Save state failed:\n{traceback.format_exc()}")
        return jsonify({"error": f"Save failed: {str(e)}"}), 500


@app.route("/api/sessions/active", methods=["DELETE"])
def delete_active():
    """Clear the active session (used by Clear Session button)."""
    session = get_active_session(get_current_user_id())
    if session:
        delete_session(session["id"])
    return "", 204


# ─── Spotify API ───────────────────────────────────────────────

@app.route("/api/spotify/connect")
def spotify_connect():
    """Redirect the user to Spotify authorization."""
    global last_heartbeat
    # Give extra time — browser leaves for Spotify OAuth and heartbeats stop
    last_heartbeat = time.time() + 120
    url = get_auth_url()
    return redirect(url)


@app.route("/callback/spotify")
def spotify_callback():
    """Handle the redirect from Spotify after user authorizes."""
    global last_heartbeat
    last_heartbeat = time.time()  # browser is back, reset watchdog

    code = request.args.get("code")
    error = request.args.get("error")

    if error:
        log.warning(f"Spotify auth denied: {error}")
        return redirect("/")

    if not code:
        return redirect("/")

    try:
        user = handle_callback(code)
        session["user_id"] = user["id"]
        log.info(f"Spotify user logged in: {user['display_name']} (id={user['id']})")

        # Start data collection + profile computation in background
        user_id = user["id"]
        def collect_and_compute():
            try:
                collect_all_spotify_data(user_id)
                compute_taste_profile(user_id)
                start_background_research(user_id)
            except Exception as e:
                log.error(f"Spotify post-auth pipeline failed: {e}")

        threading.Thread(target=collect_and_compute, daemon=True).start()

        return redirect("/")
    except Exception as e:
        log.error(f"Spotify callback failed:\n{traceback.format_exc()}")
        return redirect("/")


@app.route("/api/spotify/status")
def spotify_status():
    """Return Spotify connection status for the current user."""
    user_id = get_current_user_id()
    tokens = get_spotify_tokens(user_id)

    if not tokens:
        return jsonify({"connected": False})

    # Get taste profile
    profile = get_taste_profile(user_id)
    taste_data = None
    research_status = "pending"

    if profile:
        research_status = profile.get("research_status", "pending")
        top_genres = []
        try:
            import json as _json
            raw = profile.get("top_genres", "[]")
            top_genres = _json.loads(raw) if isinstance(raw, str) else (raw or [])
        except Exception:
            pass

        taste_data = {
            "preferred_bpm": profile.get("preferred_bpm"),
            "mood": profile.get("mood"),
            "energy_level": profile.get("energy_level"),
            "vocal_preference": profile.get("vocal_preference"),
            "danceability_level": profile.get("danceability_level"),
            "top_genres": top_genres,
        }

    # Get display name
    user = get_user(user_id)
    display_name = user.get("display_name", "") if user else ""

    # Get short-term top artists
    short_artists = get_user_top_artists(user_id, "short_term")
    top_artist_names = [a["artist_name"] for a in short_artists[:5]]

    return jsonify({
        "connected": True,
        "display_name": display_name,
        "research_status": research_status,
        "taste_profile": taste_data,
        "top_artists": top_artist_names,
    })


@app.route("/api/spotify/disconnect", methods=["GET", "POST"])
def spotify_disconnect():
    """Clear the user's Spotify tokens and taste data."""
    user_id = get_current_user_id()
    disconnect_spotify(user_id)
    # Reset session to default user
    session.pop("user_id", None)
    log.info(f"Spotify disconnected for user {user_id}")
    if request.method == "GET":
        return redirect("/")
    return jsonify({"ok": True})


@app.route("/api/spotify/refresh", methods=["POST"])
def spotify_refresh():
    """Trigger a full re-fetch of all Spotify data and recompute."""
    user_id = get_current_user_id()
    tokens = get_spotify_tokens(user_id)
    if not tokens:
        return jsonify({"error": "Not connected to Spotify"}), 400

    def refresh_pipeline():
        try:
            collect_all_spotify_data(user_id)
            compute_taste_profile(user_id)
            start_background_research(user_id)
        except Exception as e:
            log.error(f"Spotify refresh pipeline failed: {e}")

    threading.Thread(target=refresh_pipeline, daemon=True).start()
    return jsonify({"ok": True, "message": "Refresh started"})


@app.route("/api/spotify/exclude-source", methods=["POST"])
def exclude_taste_source():
    """Toggle a data source on/off for taste profile computation."""
    data = request.get_json()
    source = data.get("source")
    exclude = data.get("exclude", True)

    valid_sources = ["top_artists", "top_tracks", "followed_artists", "saved_tracks", "recent_plays"]
    if source not in valid_sources:
        return jsonify({"error": f"Invalid source. Must be one of: {valid_sources}"}), 400

    user_id = get_current_user_id()

    with get_connection() as db:
        # Resolve to Spotify-connected user if needed
        tokens = db.execute("SELECT user_id FROM spotify_tokens WHERE user_id = ?", (user_id,)).fetchone()
        if not tokens:
            fallback = db.execute("SELECT user_id FROM spotify_tokens ORDER BY last_refreshed DESC LIMIT 1").fetchone()
            if fallback:
                user_id = fallback["user_id"]

        row = db.execute("SELECT excluded_taste_sources FROM users WHERE id = ?", (user_id,)).fetchone()
        current = json.loads(row["excluded_taste_sources"] or "[]") if row else []

        if exclude and source not in current:
            current.append(source)
        elif not exclude and source in current:
            current.remove(source)

        db.execute("UPDATE users SET excluded_taste_sources = ? WHERE id = ?", (json.dumps(current), user_id))

    # Recompute taste profile with new exclusions
    compute_taste_profile(user_id, excluded_sources=current)

    return jsonify({"ok": True, "excluded_sources": current})


# ─── Diagnostic ──────────────────────────────────────────────

@app.route("/diagnostic")
def diagnostic_page():
    return send_from_directory("static", "diagnostic.html")


@app.route("/api/spotify/diagnostic")
def spotify_diagnostic():
    """Full pipeline state: Spotify → Research → Storage → Generation."""
    # Resolve user: try session cookie first, then find whoever has Spotify tokens
    user_id = get_current_user_id()
    diagnostic = {"stages": {}}

    with get_connection() as db:
        # Check if session user has tokens; if not, find the Spotify-connected user
        session_tokens = db.execute(
            "SELECT user_id FROM spotify_tokens WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not session_tokens:
            # Fall back: find any user with Spotify tokens
            fallback = db.execute(
                "SELECT user_id FROM spotify_tokens ORDER BY last_refreshed DESC LIMIT 1"
            ).fetchone()
            if fallback:
                user_id = fallback["user_id"]

        diagnostic["resolved_user_id"] = user_id

        # STAGE 1: Connection status
        try:
            user = db.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            tokens = db.execute(
                "SELECT user_id, token_expiry, scopes, last_refreshed "
                "FROM spotify_tokens WHERE user_id = ?", (user_id,)
            ).fetchone()
            diagnostic["stages"]["1_connection"] = {
                "status": "connected" if tokens else "not_connected",
                "user": dict(user) if user else None,
            }
        except Exception as e:
            diagnostic["stages"]["1_connection"] = {"status": "error", "error": str(e)}

        # STAGE 2: Raw data collection
        try:
            top_artists_count = db.execute(
                "SELECT COUNT(*) as c FROM spotify_top_artists WHERE user_id = ?",
                (user_id,),
            ).fetchone()["c"]
            top_tracks_count = db.execute(
                "SELECT COUNT(*) as c FROM spotify_top_tracks WHERE user_id = ?",
                (user_id,),
            ).fetchone()["c"]
            recent_plays_count = db.execute(
                "SELECT COUNT(*) as c FROM spotify_recent_plays WHERE user_id = ?",
                (user_id,),
            ).fetchone()["c"]
            saved_tracks_count = db.execute(
                "SELECT COUNT(*) as c FROM spotify_saved_tracks WHERE user_id = ?",
                (user_id,),
            ).fetchone()["c"]

            sample_artists = db.execute(
                "SELECT artist_name, genres, time_range, rank "
                "FROM spotify_top_artists WHERE user_id = ? "
                "ORDER BY time_range, rank ASC",
                (user_id,),
            ).fetchall()

            # Count genres — exclude empty JSON arrays '[]'
            all_genres_raw = db.execute(
                "SELECT genres FROM spotify_top_artists "
                "WHERE user_id = ? AND genres IS NOT NULL AND genres != '' AND genres != '[]'",
                (user_id,),
            ).fetchall()
            total_genre_tags = 0
            unique_genres = set()
            for row in all_genres_raw:
                try:
                    genres = json.loads(row["genres"]) if isinstance(row["genres"], str) else row["genres"]
                    if isinstance(genres, list):
                        total_genre_tags += len(genres)
                        unique_genres.update(genres)
                except Exception:
                    pass

            # Count how many artists have empty genres (the '[]' problem)
            empty_genre_count = db.execute(
                "SELECT COUNT(*) as c FROM spotify_top_artists "
                "WHERE user_id = ? AND (genres IS NULL OR genres = '' OR genres = '[]')",
                (user_id,),
            ).fetchone()["c"]

            all_top_tracks = db.execute(
                "SELECT track_name, artist_name, album_name, time_range, rank, bpm, energy, danceability "
                "FROM spotify_top_tracks WHERE user_id = ? "
                "ORDER BY time_range, rank ASC",
                (user_id,),
            ).fetchall()

            followed_artists_count = db.execute(
                "SELECT COUNT(*) as c FROM followed_artists WHERE user_id = ?",
                (user_id,),
            ).fetchone()["c"]

            all_followed_artists = db.execute(
                "SELECT name, genres, spotify_id FROM followed_artists "
                "WHERE user_id = ? ORDER BY name ASC",
                (user_id,),
            ).fetchall()

            all_saved_tracks = db.execute(
                "SELECT track_name, artist_name, album_name, added_at, bpm, energy, danceability "
                "FROM spotify_saved_tracks WHERE user_id = ? "
                "ORDER BY added_at DESC",
                (user_id,),
            ).fetchall()

            all_recent_plays = db.execute(
                "SELECT track_name, artist_name, played_at, context_type "
                "FROM spotify_recent_plays WHERE user_id = ? "
                "ORDER BY played_at DESC",
                (user_id,),
            ).fetchall()

            diagnostic["stages"]["2_raw_data"] = {
                "status": "has_data" if top_artists_count > 0 else "empty",
                "counts": {
                    "top_artists": top_artists_count,
                    "top_tracks": top_tracks_count,
                    "followed_artists": followed_artists_count,
                    "saved_tracks": saved_tracks_count,
                    "recent_plays": recent_plays_count,
                },
                "genre_stats": {
                    "total_genre_tags": total_genre_tags,
                    "unique_genres": len(unique_genres),
                    "sample_genres": sorted(list(unique_genres))[:20],
                    "artists_with_empty_genres": empty_genre_count,
                    "artists_total": top_artists_count,
                },
                "sample_artists": [dict(a) for a in sample_artists],
                "top_tracks": [dict(t) for t in all_top_tracks],
                "followed_artists": [dict(a) for a in all_followed_artists],
                "saved_tracks": [dict(s) for s in all_saved_tracks],
                "recent_plays": [dict(r) for r in all_recent_plays],
            }
        except Exception as e:
            diagnostic["stages"]["2_raw_data"] = {"status": "error", "error": str(e)}

        # STAGE 3: Taste profile — live-compute weighted profile from all sources
        try:
            excluded_row = db.execute(
                "SELECT excluded_taste_sources FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            excluded = json.loads(excluded_row["excluded_taste_sources"] or "[]") if excluded_row else []

            genre_sources = build_genre_sources(user_id)
            weighted = compute_weighted_taste(genre_sources, excluded_sources=excluded)

            # Also check if a stored profile exists in the DB
            stored = db.execute(
                "SELECT * FROM spotify_taste_profiles WHERE user_id = ?", (user_id,)
            ).fetchone()

            has_data = weighted.get("total_weighted_genres", 0) > 0

            reason = None
            if not has_data:
                genre_stats = diagnostic["stages"].get("2_raw_data", {}).get("genre_stats", {})
                if genre_stats.get("total_genre_tags", 0) == 0:
                    reason = (
                        f"All {genre_stats.get('artists_total', 0)} artists have empty genre arrays from Spotify. "
                        "compute_taste_profile() requires genre data to compute attributes. "
                        "This is a Spotify API limitation — many smaller/niche artists lack genre tags."
                    )
                else:
                    reason = "Genre data exists but no weighted sources contributed. Check excluded sources."

            diagnostic["stages"]["3_taste_profile"] = {
                "status": "computed" if has_data else "missing",
                "stored_in_db": stored is not None,
                "profile": weighted,
                "reason": reason,
            }
        except Exception as e:
            diagnostic["stages"]["3_taste_profile"] = {"status": "error", "error": str(e)}

        # STAGE 4: Artist research / Production DNA
        try:
            researched_count = db.execute(
                "SELECT COUNT(*) as c FROM artist_research_cache"
            ).fetchone()["c"]
            sample_research = db.execute(
                "SELECT artist_name, production_profile "
                "FROM artist_research_cache LIMIT 5"
            ).fetchall()

            # Count how many have real research vs "I don't have" placeholders
            no_data_count = db.execute(
                "SELECT COUNT(*) as c FROM artist_research_cache "
                "WHERE production_profile LIKE '%don''t have specific%' "
                "OR production_profile LIKE '%don''t have sufficient%'"
            ).fetchone()["c"]

            queue_count = 0
            try:
                queue_count = db.execute(
                    "SELECT COUNT(*) as c FROM research_queue WHERE status = 'pending'"
                ).fetchone()["c"]
            except Exception:
                pass

            diagnostic["stages"]["4_artist_research"] = {
                "status": "has_research" if researched_count > 0 else "empty",
                "researched_artists": researched_count,
                "no_data_artists": no_data_count,
                "useful_research": researched_count - no_data_count,
                "pending_in_queue": queue_count,
                "sample_research": [
                    {
                        "artist": dict(r)["artist_name"],
                        "summary_preview": (dict(r).get("production_profile") or "")[:200],
                    }
                    for r in sample_research
                ],
            }
        except Exception as e:
            diagnostic["stages"]["4_artist_research"] = {"status": "error", "error": str(e)}

        # STAGE 5: Related artists graph
        try:
            graph_edges = db.execute(
                "SELECT COUNT(*) as c FROM artist_graph"
            ).fetchone()["c"]
            sample_edges = db.execute(
                "SELECT source_name, related_name FROM artist_graph LIMIT 10"
            ).fetchall()

            diagnostic["stages"]["5_artist_graph"] = {
                "status": "populated" if graph_edges > 0 else "empty",
                "total_edges": graph_edges,
                "sample_connections": [
                    f"{dict(e)['source_name']} \u2192 {dict(e)['related_name']}"
                    for e in sample_edges
                ],
            }
        except Exception as e:
            diagnostic["stages"]["5_artist_graph"] = {"status": "not_built", "error": str(e)}

    # STAGE 6: System prompt injection (outside the db context manager)
    try:
        prompt_section = build_taste_context(user_id)
        diagnostic["stages"]["6_prompt_injection"] = {
            "status": "active" if prompt_section and len(prompt_section.strip()) > 0 else "inactive",
            "prompt_preview": prompt_section[:500] if prompt_section else "No taste profile section generated",
            "char_count": len(prompt_section) if prompt_section else 0,
        }
    except Exception as e:
        diagnostic["stages"]["6_prompt_injection"] = {"status": "error", "error": str(e)}

    # STAGE 7: Generation readiness
    stage_status_map = {
        "1_connection": ["connected"],
        "2_raw_data": ["has_data"],
        "3_taste_profile": ["computed"],
        "4_artist_research": ["has_research"],
        "5_artist_graph": ["populated"],
        "6_prompt_injection": ["active"],
    }
    all_working = all(
        diagnostic["stages"].get(key, {}).get("status") in ok_statuses
        for key, ok_statuses in stage_status_map.items()
    )
    diagnostic["stages"]["7_generation_ready"] = {
        "status": "ready" if all_working else "not_ready",
        "message": (
            "All pipeline stages have data. Taste profile will influence generations."
            if all_working
            else "Some pipeline stages are missing data. See above for details."
        ),
    }

    diagnostic["pipeline_health"] = {
        "stages_working": sum(
            1
            for key, ok_statuses in stage_status_map.items()
            if diagnostic["stages"].get(key, {}).get("status") in ok_statuses
        ),
        "stages_total": 7,
    }

    return jsonify(diagnostic)


# ─── SoundCloud API ───────────────────────────────────────────

@app.route("/api/soundcloud/connect")
def soundcloud_connect():
    """Redirect the user to SoundCloud authorization."""
    global last_heartbeat
    # Pre-flight: check env vars are set
    if not os.environ.get("SOUNDCLOUD_CLIENT_ID") or not os.environ.get("SOUNDCLOUD_CLIENT_SECRET"):
        log.error("SOUNDCLOUD_CLIENT_ID or SOUNDCLOUD_CLIENT_SECRET not set")
        return jsonify({"error": "SoundCloud not configured. Set SOUNDCLOUD_CLIENT_ID and SOUNDCLOUD_CLIENT_SECRET in ~/.zshrc"}), 500
    last_heartbeat = time.time() + 120
    url = sc_get_auth_url(session)
    log.info(f"Redirecting to SoundCloud OAuth: {url[:100]}...")
    return redirect(url)


@app.route("/callback/soundcloud")
def soundcloud_callback():
    """Handle the redirect from SoundCloud after user authorizes."""
    global last_heartbeat
    last_heartbeat = time.time()

    code = request.args.get("code")
    error = request.args.get("error")
    state = request.args.get("state")

    if error:
        log.warning(f"SoundCloud auth denied: {error}")
        return redirect("/")

    if not code:
        return redirect("/")

    # Verify state
    expected_state = session.pop("sc_oauth_state", None)
    if state and expected_state and state != expected_state:
        log.warning("SoundCloud OAuth state mismatch")
        return redirect("/")

    code_verifier = session.pop("sc_code_verifier", None)
    if not code_verifier:
        log.error("No PKCE code verifier in session")
        return redirect("/")

    try:
        user = sc_handle_callback(code, code_verifier)
        session["user_id"] = user["id"]
        log.info(f"SoundCloud user logged in: {user['display_name']} (id={user['id']})")

        user_id = user["id"]
        def collect_and_compute():
            try:
                collect_all_soundcloud_data(user_id)
                compute_soundcloud_taste_profile(user_id)
                start_soundcloud_background_research(user_id)
            except Exception as e:
                log.error(f"SoundCloud post-auth pipeline failed: {e}")

        threading.Thread(target=collect_and_compute, daemon=True).start()

        return redirect("/")
    except Exception as e:
        log.error(f"SoundCloud callback failed:\n{traceback.format_exc()}")
        return redirect("/")


@app.route("/api/soundcloud/status")
def soundcloud_status():
    """Return SoundCloud connection status for the current user."""
    user_id = get_current_user_id()
    tokens = get_soundcloud_tokens(user_id)

    if not tokens:
        return jsonify({"connected": False})

    profile = get_soundcloud_taste_profile(user_id)
    taste_data = None
    research_status = "pending"

    if profile:
        research_status = profile.get("research_status", "pending")
        top_genres = _parse_json_field(profile.get("top_genres"))
        top_tags = _parse_json_field(profile.get("top_tags"))
        top_artists = _parse_json_field(profile.get("top_artists"))

        taste_data = {
            "avg_bpm": profile.get("avg_bpm"),
            "mood": profile.get("mood"),
            "energy_level": profile.get("energy_level"),
            "vocal_preference": profile.get("vocal_preference"),
            "underground_score": profile.get("underground_score"),
            "top_genres": top_genres,
            "top_tags": top_tags,
            "top_artists": top_artists,
        }

    user = get_user(user_id)
    display_name = user.get("display_name", "") if user else ""

    return jsonify({
        "connected": True,
        "display_name": display_name,
        "research_status": research_status,
        "taste_profile": taste_data,
    })


@app.route("/api/soundcloud/disconnect", methods=["POST"])
def soundcloud_disconnect_route():
    """Clear the user's SoundCloud tokens and data."""
    user_id = get_current_user_id()
    disconnect_soundcloud(user_id)
    log.info(f"SoundCloud disconnected for user {user_id}")
    return jsonify({"ok": True})


@app.route("/api/soundcloud/refresh", methods=["POST"])
def soundcloud_refresh():
    """Trigger a full re-fetch of all SoundCloud data and recompute."""
    user_id = get_current_user_id()
    tokens = get_soundcloud_tokens(user_id)
    if not tokens:
        return jsonify({"error": "Not connected to SoundCloud"}), 400

    def refresh_pipeline():
        try:
            collect_all_soundcloud_data(user_id)
            compute_soundcloud_taste_profile(user_id)
            start_soundcloud_background_research(user_id)
        except Exception as e:
            log.error(f"SoundCloud refresh pipeline failed: {e}")

    threading.Thread(target=refresh_pipeline, daemon=True).start()
    return jsonify({"ok": True, "message": "Refresh started"})


def _parse_json_field(raw, default=None):
    """Safely parse a JSON field."""
    if default is None:
        default = []
    if not raw:
        return default
    try:
        import json as _json
        return _json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return default


@app.errorhandler(Exception)
def handle_exception(e):
    log.error(f"Unhandled exception:\n{traceback.format_exc()}")
    return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.errorhandler(413)
def handle_too_large(e):
    log.warning("Upload rejected: file exceeds 50MB limit")
    return jsonify({"error": "File too large. Max 50MB."}), 413


if __name__ == "__main__":
    debug = "--debug" in sys.argv
    log.info("DAW Brain starting on http://127.0.0.1:5050")
    # Start watchdog thread (only when launched normally, not in debug)
    if not debug:
        t = threading.Thread(target=watchdog, daemon=True)
        t.start()
    app.run(debug=debug, host="127.0.0.1", port=5050, use_reloader=False)
