"""
DAW Brain SQLite database — single source of truth for all app data.
Location: ~/.daw-brain/dawbrain.db
"""

import os
import json
import math
import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime

log = logging.getLogger("daw-brain")

DB_DIR = os.path.expanduser("~/.daw-brain")
DB_PATH = os.path.join(DB_DIR, "dawbrain.db")

ELEMENT_CATEGORIES = {
    "kick": "drums", "clap": "drums", "hats": "drums",
    "perc": "drums", "toploop": "drums",
    "sub": "bass", "midbass": "bass",
    "stabs": "melodic", "lead": "melodic", "chords": "melodic",
    "pad": "melodic", "arps": "melodic", "plucks": "melodic",
    "mainvox": "vocals", "chops": "vocals", "hook": "vocals", "adlibs": "vocals",
    "risers": "fx", "downlifters": "fx", "impacts": "fx",
    "sweeps": "fx", "transitions": "fx", "textures": "fx",
}

ALL_ELEMENTS = list(ELEMENT_CATEGORIES.keys())

# ─── Music Theory Constants ────────────────────────────────────

NOTE_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
DRUM_ELEMENTS = {"kick", "clap", "hats", "perc", "toploop"}
MELODIC_ELEMENTS_SET = {"sub", "midbass", "stabs", "lead", "chords", "pad", "arps", "plucks"}
ELEMENT_FREQ_RANGES = {
    "kick": "Sub (30-60 Hz)", "clap": "Mid (200-2000 Hz)", "hats": "High (3-10 kHz)",
    "perc": "Mid-High (500-5000 Hz)", "toploop": "High (2-8 kHz)",
    "sub": "Sub (30-80 Hz)", "midbass": "Low-Mid (80-300 Hz)",
    "stabs": "Mid-High (300-5000 Hz)", "lead": "Mid-High (500-8000 Hz)",
    "chords": "Mid (200-4000 Hz)", "pad": "Mid (200-4000 Hz)",
    "arps": "Mid-High (500-8000 Hz)", "plucks": "Mid-High (500-8000 Hz)",
}
INTERVAL_NAMES_MAP = {
    0: "P1", 1: "m2", 2: "M2", 3: "m3", 4: "M3", 5: "P4",
    6: "TT", 7: "P5", 8: "m6", 9: "M6", 10: "m7", 11: "M7", 12: "P8",
}


# ─── Connection Management ─────────────────────────────────────

@contextmanager
def get_connection():
    """Context manager for database connections with auto-commit/rollback."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def _rows_to_dicts(rows):
    return [dict(r) for r in rows]


# ─── Schema ────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    spotify_id        TEXT UNIQUE,
    soundcloud_id     TEXT UNIQUE,
    display_name      TEXT,
    email             TEXT,
    avatar_url        TEXT,
    spotify_country   TEXT,
    spotify_product   TEXT,
    skill_level       TEXT DEFAULT 'expert',
    preferred_genre   TEXT DEFAULT 'tech_house',
    preferred_bpm     INTEGER DEFAULT 128,
    preferred_key     TEXT DEFAULT 'E',
    preferred_scale   TEXT DEFAULT 'minor',
    theme             TEXT DEFAULT 'dark',
    excluded_taste_sources TEXT DEFAULT '[]',
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS spotify_tokens (
    user_id           INTEGER PRIMARY KEY REFERENCES users(id),
    access_token      TEXT NOT NULL,
    refresh_token     TEXT NOT NULL,
    token_expiry      TIMESTAMP,
    scopes            TEXT,
    last_refreshed    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS spotify_taste_profiles (
    user_id               INTEGER PRIMARY KEY REFERENCES users(id),
    avg_bpm               REAL,
    bpm_range_low         REAL,
    bpm_range_high        REAL,
    preferred_bpm         REAL,
    preferred_keys        TEXT,
    avg_energy            REAL,
    avg_danceability      REAL,
    avg_valence           REAL,
    avg_instrumentalness  REAL,
    avg_acousticness      REAL,
    avg_speechiness       REAL,
    avg_liveness          REAL,
    avg_loudness          REAL,
    avg_tempo             REAL,
    mood                  TEXT,
    energy_level          TEXT,
    vocal_preference      TEXT,
    danceability_level    TEXT,
    top_genres            TEXT,
    evolving_taste        TEXT,
    production_dna        TEXT,
    research_status       TEXT DEFAULT 'pending',
    raw_data              TEXT,
    last_updated          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS spotify_top_artists (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER REFERENCES users(id),
    artist_id         TEXT,
    artist_name       TEXT,
    genres            TEXT,
    popularity        INTEGER,
    follower_count    INTEGER,
    image_url         TEXT,
    time_range        TEXT,
    rank              INTEGER,
    fetched_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS spotify_top_tracks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER REFERENCES users(id),
    track_id          TEXT,
    track_name        TEXT,
    artist_name       TEXT,
    artist_id         TEXT,
    album_name        TEXT,
    duration_ms       INTEGER,
    popularity        INTEGER,
    explicit          BOOLEAN,
    time_range        TEXT,
    rank              INTEGER,
    bpm               REAL,
    energy            REAL,
    danceability      REAL,
    valence           REAL,
    instrumentalness  REAL,
    acousticness      REAL,
    speechiness       REAL,
    liveness          REAL,
    loudness          REAL,
    key               INTEGER,
    mode              INTEGER,
    time_signature    INTEGER,
    fetched_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS spotify_recent_plays (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER REFERENCES users(id),
    track_id          TEXT,
    track_name        TEXT,
    artist_name       TEXT,
    played_at         TIMESTAMP,
    context_type      TEXT,
    context_name      TEXT,
    fetched_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS spotify_saved_tracks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER REFERENCES users(id),
    track_id          TEXT,
    track_name        TEXT,
    artist_name       TEXT,
    artist_id         TEXT,
    album_name        TEXT,
    added_at          TIMESTAMP,
    bpm               REAL,
    energy            REAL,
    danceability      REAL,
    valence           REAL,
    instrumentalness  REAL,
    key               INTEGER,
    mode              INTEGER,
    fetched_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS artist_research_cache (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_name           TEXT UNIQUE,
    spotify_artist_id     TEXT,
    genres                TEXT,
    popularity            INTEGER,
    production_profile    TEXT,
    bpm_range             TEXT,
    drum_style            TEXT,
    bass_style            TEXT,
    sound_design_notes    TEXT,
    arrangement_style     TEXT,
    mixing_character      TEXT,
    signature_elements    TEXT,
    researched_by_model   TEXT,
    research_version      INTEGER DEFAULT 1,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS soundcloud_tokens (
    user_id           INTEGER PRIMARY KEY REFERENCES users(id),
    access_token      TEXT NOT NULL,
    refresh_token     TEXT NOT NULL,
    token_expiry      TIMESTAMP,
    last_refreshed    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS soundcloud_likes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER REFERENCES users(id),
    track_id          TEXT,
    track_title       TEXT,
    artist_name       TEXT,
    artist_id         TEXT,
    genre             TEXT,
    tag_list          TEXT,
    duration_ms       INTEGER,
    playback_count    INTEGER,
    likes_count       INTEGER,
    reposts_count     INTEGER,
    created_at_sc     TEXT,
    liked_at          TIMESTAMP,
    fetched_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS soundcloud_followings (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER REFERENCES users(id),
    artist_id         TEXT,
    artist_name       TEXT,
    artist_permalink  TEXT,
    followers_count   INTEGER,
    track_count       INTEGER,
    genre             TEXT,
    city              TEXT,
    country           TEXT,
    fetched_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS soundcloud_reposts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER REFERENCES users(id),
    track_id          TEXT,
    track_title       TEXT,
    artist_name       TEXT,
    artist_id         TEXT,
    genre             TEXT,
    tag_list          TEXT,
    reposted_at       TIMESTAMP,
    fetched_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS soundcloud_playlists (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER REFERENCES users(id),
    playlist_id       TEXT,
    playlist_title    TEXT,
    description       TEXT,
    genre             TEXT,
    tag_list          TEXT,
    track_count       INTEGER,
    is_public         BOOLEAN,
    created_at_sc     TEXT,
    fetched_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS soundcloud_user_tracks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER REFERENCES users(id),
    track_id          TEXT,
    track_title       TEXT,
    genre             TEXT,
    tag_list          TEXT,
    bpm               REAL,
    key_signature     TEXT,
    duration_ms       INTEGER,
    playback_count    INTEGER,
    likes_count       INTEGER,
    created_at_sc     TEXT,
    fetched_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS soundcloud_taste_profiles (
    user_id           INTEGER PRIMARY KEY REFERENCES users(id),
    top_genres        TEXT,
    top_tags          TEXT,
    top_artists       TEXT,
    underground_score REAL,
    avg_bpm           REAL,
    preferred_keys    TEXT,
    mood              TEXT,
    energy_level      TEXT,
    vocal_preference  TEXT,
    production_dna    TEXT,
    research_status   TEXT DEFAULT 'pending',
    evolving_taste    TEXT,
    raw_data          TEXT,
    last_updated      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS followed_artists (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL REFERENCES users(id),
    spotify_id        TEXT NOT NULL,
    name              TEXT NOT NULL,
    genres            TEXT,
    images            TEXT,
    collected_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, spotify_id)
);

CREATE TABLE IF NOT EXISTS genre_profiles (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    genre_name        TEXT UNIQUE NOT NULL,
    bpm_low           INTEGER,
    bpm_high          INTEGER,
    energy            REAL,
    mood              TEXT,
    vocal_density     TEXT,
    key_tendency      TEXT,
    description       TEXT,
    key_artists       TEXT,
    source            TEXT DEFAULT 'lookup_table',
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS artist_graph (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    source_artist_id  TEXT NOT NULL,
    related_artist_id TEXT NOT NULL,
    source_name       TEXT,
    related_name      TEXT,
    crawled_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_artist_id, related_artist_id)
);

CREATE TABLE IF NOT EXISTS research_queue (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER,
    spotify_id        TEXT NOT NULL,
    artist_name       TEXT NOT NULL,
    priority          INTEGER DEFAULT 0,
    status            TEXT DEFAULT 'pending',
    queued_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at      TIMESTAMP,
    UNIQUE(spotify_id)
);

CREATE TABLE IF NOT EXISTS trend_snapshots (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_type     TEXT NOT NULL,
    data              TEXT NOT NULL,
    captured_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER REFERENCES users(id),
    session_name      TEXT DEFAULT 'Untitled Session',
    bpm               INTEGER DEFAULT 128,
    key               TEXT DEFAULT 'E',
    scale             TEXT DEFAULT 'minor',
    genre             TEXT DEFAULT 'tech_house',
    skill_level       TEXT DEFAULT 'expert',
    active_element    TEXT,
    active_chat_tab   TEXT DEFAULT 'element',
    tracks_in_session TEXT,
    session_notes     TEXT,
    is_active         BOOLEAN DEFAULT 1,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS session_elements (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        INTEGER REFERENCES sessions(id),
    element_name      TEXT,
    element_category  TEXT,
    status            TEXT DEFAULT 'empty',
    summary           TEXT,
    midi_note_data    TEXT,
    output_metadata   TEXT,
    bars              INTEGER,
    note_count        INTEGER,
    velocity_range_low  INTEGER,
    velocity_range_high INTEGER,
    pitch_range_low   INTEGER,
    pitch_range_high  INTEGER,
    rhythm_summary    TEXT,
    pitch_center      TEXT,
    intervals_used    TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, element_name)
);

CREATE TABLE IF NOT EXISTS chat_history (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        INTEGER REFERENCES sessions(id),
    element_name      TEXT,
    role              TEXT,
    content           TEXT,
    has_output        BOOLEAN DEFAULT 0,
    output_id         INTEGER,
    output_data       TEXT,
    file_url          TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS generated_outputs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        INTEGER REFERENCES sessions(id),
    user_id           INTEGER REFERENCES users(id),
    element_name      TEXT,
    output_type       TEXT,
    output_name       TEXT,
    midi_note_data    TEXT,
    arrangement_data  TEXT,
    signal_chain_data TEXT,
    bars              INTEGER,
    bpm               INTEGER,
    key               TEXT,
    scale             TEXT,
    genre             TEXT,
    skill_level       TEXT,
    prompt_text       TEXT,
    system_prompt_hash TEXT,
    was_downloaded    BOOLEAN DEFAULT 0,
    was_kept          BOOLEAN DEFAULT 1,
    generation_time_ms INTEGER,
    tokens_used       INTEGER,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_feedback (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER REFERENCES users(id),
    output_id         INTEGER REFERENCES generated_outputs(id),
    rating            INTEGER,
    feedback_text     TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_analytics (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER REFERENCES users(id),
    event_type        TEXT,
    event_data        TEXT,
    session_id        INTEGER,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db():
    """Create all tables if they don't exist."""
    os.makedirs(DB_DIR, exist_ok=True)
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        # Migration: add soundcloud_id column if missing (for pre-SoundCloud DBs)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "soundcloud_id" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN soundcloud_id TEXT")
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_soundcloud_id "
                "ON users(soundcloud_id) WHERE soundcloud_id IS NOT NULL"
            )
    log.info(f"Database initialized at {DB_PATH}")


def ensure_default_user():
    """Create a default local user if none exists. Returns user_id."""
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        if row:
            return row["id"]
        cursor = conn.execute(
            "INSERT INTO users (display_name, skill_level) VALUES (?, ?)",
            ("Local User", "expert")
        )
        return cursor.lastrowid


# ─── Users ─────────────────────────────────────────────────────

def create_user(spotify_id=None, soundcloud_id=None, display_name=None,
                email=None, avatar_url=None, spotify_country=None,
                spotify_product=None, skill_level="expert",
                preferred_genre="tech_house", preferred_bpm=128,
                preferred_key="E", preferred_scale="minor", theme="dark"):
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO users (spotify_id, soundcloud_id, display_name,
               email, avatar_url, spotify_country, spotify_product,
               skill_level, preferred_genre, preferred_bpm, preferred_key,
               preferred_scale, theme)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (spotify_id, soundcloud_id, display_name, email, avatar_url,
             spotify_country, spotify_product, skill_level, preferred_genre,
             preferred_bpm, preferred_key, preferred_scale, theme)
        )
        return cursor.lastrowid


def get_user(user_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _row_to_dict(row)


def get_user_by_spotify_id(spotify_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE spotify_id = ?", (spotify_id,)
        ).fetchone()
        return _row_to_dict(row)


def get_user_by_soundcloud_id(soundcloud_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE soundcloud_id = ?", (soundcloud_id,)
        ).fetchone()
        return _row_to_dict(row)


def update_user(user_id, **fields):
    if not fields:
        return
    fields["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f'"{k}" = ?' for k in fields)
    values = list(fields.values()) + [user_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)


def update_last_login(user_id):
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
            (user_id,)
        )


# ─── Spotify Tokens ────────────────────────────────────────────

def save_spotify_tokens(user_id, access_token, refresh_token, expiry, scopes=None):
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO spotify_tokens
               (user_id, access_token, refresh_token, token_expiry, scopes,
                last_refreshed)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (user_id, access_token, refresh_token, expiry, scopes)
        )


def get_spotify_tokens(user_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM spotify_tokens WHERE user_id = ?", (user_id,)
        ).fetchone()
        return _row_to_dict(row)


def update_access_token(user_id, new_access_token, new_expiry):
    with get_connection() as conn:
        conn.execute(
            """UPDATE spotify_tokens SET access_token = ?, token_expiry = ?,
               last_refreshed = CURRENT_TIMESTAMP WHERE user_id = ?""",
            (new_access_token, new_expiry, user_id)
        )


# ─── Spotify Taste Data ────────────────────────────────────────

def save_top_artists(user_id, artists_list, time_range):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM spotify_top_artists WHERE user_id = ? AND time_range = ?",
            (user_id, time_range)
        )
        for i, artist in enumerate(artists_list):
            conn.execute(
                """INSERT INTO spotify_top_artists
                   (user_id, artist_id, artist_name, genres, popularity,
                    follower_count, image_url, time_range, rank)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, artist.get("id"), artist.get("name"),
                 json.dumps(artist.get("genres", [])), artist.get("popularity"),
                 artist.get("follower_count"), artist.get("image_url"),
                 time_range, i + 1)
            )


def save_top_tracks(user_id, tracks_list, time_range):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM spotify_top_tracks WHERE user_id = ? AND time_range = ?",
            (user_id, time_range)
        )
        for i, track in enumerate(tracks_list):
            features = track.get("audio_features", {}) or {}
            conn.execute(
                """INSERT INTO spotify_top_tracks
                   (user_id, track_id, track_name, artist_name, artist_id,
                    album_name, duration_ms, popularity, explicit,
                    time_range, rank, bpm, energy, danceability, valence,
                    instrumentalness, acousticness, speechiness, liveness,
                    loudness, key, mode, time_signature)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (user_id, track.get("id"), track.get("name"),
                 track.get("artist_name"), track.get("artist_id"),
                 track.get("album_name"), track.get("duration_ms"),
                 track.get("popularity"), track.get("explicit"),
                 time_range, i + 1,
                 features.get("tempo"), features.get("energy"),
                 features.get("danceability"), features.get("valence"),
                 features.get("instrumentalness"), features.get("acousticness"),
                 features.get("speechiness"), features.get("liveness"),
                 features.get("loudness"), features.get("key"),
                 features.get("mode"), features.get("time_signature"))
            )


def save_recent_plays(user_id, plays_list):
    with get_connection() as conn:
        for play in plays_list:
            conn.execute(
                """INSERT INTO spotify_recent_plays
                   (user_id, track_id, track_name, artist_name,
                    played_at, context_type, context_name)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, play.get("track_id"), play.get("track_name"),
                 play.get("artist_name"), play.get("played_at"),
                 play.get("context_type"), play.get("context_name"))
            )


def save_saved_tracks(user_id, tracks_list):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM spotify_saved_tracks WHERE user_id = ?", (user_id,)
        )
        for track in tracks_list:
            features = track.get("audio_features", {}) or {}
            conn.execute(
                """INSERT INTO spotify_saved_tracks
                   (user_id, track_id, track_name, artist_name, artist_id,
                    album_name, added_at, bpm, energy, danceability, valence,
                    instrumentalness, key, mode)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (user_id, track.get("id"), track.get("name"),
                 track.get("artist_name"), track.get("artist_id"),
                 track.get("album_name"), track.get("added_at"),
                 features.get("tempo"), features.get("energy"),
                 features.get("danceability"), features.get("valence"),
                 features.get("instrumentalness"), features.get("key"),
                 features.get("mode"))
            )


def get_user_top_artists(user_id, time_range=None):
    with get_connection() as conn:
        if time_range:
            rows = conn.execute(
                """SELECT * FROM spotify_top_artists
                   WHERE user_id = ? AND time_range = ? ORDER BY rank""",
                (user_id, time_range)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM spotify_top_artists
                   WHERE user_id = ? ORDER BY time_range, rank""",
                (user_id,)
            ).fetchall()
        return _rows_to_dicts(rows)


def get_user_top_tracks(user_id, time_range=None):
    with get_connection() as conn:
        if time_range:
            rows = conn.execute(
                """SELECT * FROM spotify_top_tracks
                   WHERE user_id = ? AND time_range = ? ORDER BY rank""",
                (user_id, time_range)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM spotify_top_tracks
                   WHERE user_id = ? ORDER BY time_range, rank""",
                (user_id,)
            ).fetchall()
        return _rows_to_dicts(rows)


def save_taste_profile(user_id, profile_dict):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT user_id FROM spotify_taste_profiles WHERE user_id = ?",
            (user_id,)
        ).fetchone()

        if existing:
            fields = {k: v for k, v in profile_dict.items() if k != "user_id"}
            fields["last_updated"] = datetime.utcnow().isoformat()
            set_clause = ", ".join(f'"{k}" = ?' for k in fields)
            values = list(fields.values()) + [user_id]
            conn.execute(
                f"UPDATE spotify_taste_profiles SET {set_clause} WHERE user_id = ?",
                values
            )
        else:
            profile_dict["user_id"] = user_id
            cols = ", ".join(f'"{k}"' for k in profile_dict)
            placeholders = ", ".join("?" * len(profile_dict))
            conn.execute(
                f"INSERT INTO spotify_taste_profiles ({cols}) VALUES ({placeholders})",
                list(profile_dict.values())
            )


def get_taste_profile(user_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM spotify_taste_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
        return _row_to_dict(row)


# ─── Artist Research Cache ──────────────────────────────────────

def get_artist_research(artist_name):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM artist_research_cache WHERE artist_name = ? COLLATE NOCASE",
            (artist_name,)
        ).fetchone()
        return _row_to_dict(row)


def save_artist_research(artist_name, spotify_id, research_data):
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO artist_research_cache
               (artist_name, spotify_artist_id, genres, popularity,
                production_profile, bpm_range, drum_style, bass_style,
                sound_design_notes, arrangement_style, mixing_character,
                signature_elements, researched_by_model, research_version,
                updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
            (artist_name, spotify_id,
             json.dumps(research_data.get("genres", [])),
             research_data.get("popularity"),
             research_data.get("production_profile"),
             research_data.get("bpm_range"),
             research_data.get("drum_style"),
             research_data.get("bass_style"),
             research_data.get("sound_design_notes"),
             research_data.get("arrangement_style"),
             research_data.get("mixing_character"),
             research_data.get("signature_elements"),
             research_data.get("researched_by_model"),
             research_data.get("research_version", 1))
        )


def get_unresearched_artists(artist_names):
    if not artist_names:
        return []
    with get_connection() as conn:
        placeholders = ", ".join("?" * len(artist_names))
        rows = conn.execute(
            f"""SELECT artist_name FROM artist_research_cache
                WHERE artist_name IN ({placeholders}) COLLATE NOCASE""",
            artist_names
        ).fetchall()
        researched = {r["artist_name"].lower() for r in rows}
        return [name for name in artist_names if name.lower() not in researched]


def get_all_researched_artists():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM artist_research_cache ORDER BY artist_name"
        ).fetchall()
        return _rows_to_dicts(rows)


def get_stale_artist_research(artist_names, max_age_days=30):
    """Return artist names whose cache is older than max_age_days."""
    if not artist_names:
        return []
    with get_connection() as conn:
        placeholders = ", ".join("?" * len(artist_names))
        rows = conn.execute(
            f"""SELECT artist_name FROM artist_research_cache
                WHERE artist_name IN ({placeholders}) COLLATE NOCASE
                AND updated_at < datetime('now', ?)""",
            artist_names + [f'-{max_age_days} days']
        ).fetchall()
        return [r["artist_name"] for r in rows]


def get_user_saved_tracks(user_id):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM spotify_saved_tracks
               WHERE user_id = ? ORDER BY added_at DESC""",
            (user_id,)
        ).fetchall()
        return _rows_to_dicts(rows)


def get_user_recent_plays(user_id):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM spotify_recent_plays
               WHERE user_id = ? ORDER BY played_at DESC""",
            (user_id,)
        ).fetchall()
        return _rows_to_dicts(rows)


def save_followed_artists(user_id, artists_list):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM followed_artists WHERE user_id = ?", (user_id,)
        )
        for artist in artists_list:
            conn.execute(
                """INSERT OR IGNORE INTO followed_artists
                   (user_id, spotify_id, name, genres, images)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, artist.get("id"), artist.get("name"),
                 json.dumps(artist.get("genres", [])),
                 json.dumps(artist.get("images") or []))
            )


def get_followed_artists(user_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM followed_artists WHERE user_id = ?",
            (user_id,)
        ).fetchall()
        return _rows_to_dicts(rows)


def get_all_genres_for_user(user_id):
    """Pull all genre tags from top_artists + followed_artists for taste profiling."""
    all_genres = []
    with get_connection() as conn:
        # Top artists (weighted: short_term genres appear 3x, medium 2x, long 1x)
        for time_range, weight in [("short_term", 3), ("medium_term", 2), ("long_term", 1)]:
            rows = conn.execute(
                """SELECT genres FROM spotify_top_artists
                   WHERE user_id = ? AND time_range = ?""",
                (user_id, time_range)
            ).fetchall()
            for row in rows:
                try:
                    genres = json.loads(row["genres"]) if row["genres"] else []
                except (json.JSONDecodeError, TypeError):
                    genres = []
                all_genres.extend(genres * weight)

        # Followed artists (weight 1x each)
        rows = conn.execute(
            "SELECT genres FROM followed_artists WHERE user_id = ?",
            (user_id,)
        ).fetchall()
        for row in rows:
            try:
                genres = json.loads(row["genres"]) if row["genres"] else []
            except (json.JSONDecodeError, TypeError):
                genres = []
            all_genres.extend(genres)

    return all_genres


def save_artist_edge(edge_data):
    """Save a relationship edge in the artist graph."""
    with get_connection() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO artist_graph
               (source_artist_id, related_artist_id, source_name, related_name)
               VALUES (?, ?, ?, ?)""",
            (edge_data.get("source_artist_id"),
             edge_data.get("related_artist_id"),
             edge_data.get("source_name"),
             edge_data.get("related_name"))
        )


def get_artist_graph_edges(user_id=None):
    """Get all artist graph edges. Optionally filter by user's top artist IDs."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM artist_graph ORDER BY crawled_at DESC"
        ).fetchall()
        return _rows_to_dicts(rows)


def queue_for_research(spotify_id, artist_name, user_id=None, priority=0):
    """Add an artist to the research queue if not already there."""
    with get_connection() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO research_queue
               (user_id, spotify_id, artist_name, priority)
               VALUES (?, ?, ?, ?)""",
            (user_id, spotify_id, artist_name, priority)
        )


def get_research_queue(status="pending", limit=20):
    """Get pending items from the research queue."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM research_queue WHERE status = ?
               ORDER BY priority DESC, queued_at ASC LIMIT ?""",
            (status, limit)
        ).fetchall()
        return _rows_to_dicts(rows)


def artist_in_research_cache(artist_name):
    """Check if an artist is already in the research cache."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM artist_research_cache WHERE artist_name = ? COLLATE NOCASE",
            (artist_name,)
        ).fetchone()
        return row is not None


def clear_spotify_data(user_id):
    """Clear all Spotify listening data for a user (not artist_research_cache)."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM spotify_saved_tracks WHERE user_id = ?", (user_id,)
        )
        conn.execute(
            "DELETE FROM spotify_recent_plays WHERE user_id = ?", (user_id,)
        )
        conn.execute(
            "DELETE FROM spotify_top_tracks WHERE user_id = ?", (user_id,)
        )
        conn.execute(
            "DELETE FROM spotify_top_artists WHERE user_id = ?", (user_id,)
        )
        conn.execute(
            "DELETE FROM followed_artists WHERE user_id = ?", (user_id,)
        )


def disconnect_spotify(user_id):
    """Clear all Spotify data including tokens and taste profile."""
    clear_spotify_data(user_id)
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM spotify_taste_profiles WHERE user_id = ?", (user_id,)
        )
        conn.execute(
            "DELETE FROM spotify_tokens WHERE user_id = ?", (user_id,)
        )
        conn.execute(
            """UPDATE users SET spotify_id = NULL, email = NULL,
               avatar_url = NULL, spotify_country = NULL,
               spotify_product = NULL, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (user_id,)
        )


def update_research_status(user_id, status):
    """Update the research_status field in taste profile."""
    with get_connection() as conn:
        conn.execute(
            """UPDATE spotify_taste_profiles SET research_status = ?,
               last_updated = CURRENT_TIMESTAMP WHERE user_id = ?""",
            (status, user_id)
        )


def save_production_dna(user_id, dna_text):
    """Save the synthesized Production DNA to the taste profile."""
    with get_connection() as conn:
        conn.execute(
            """UPDATE spotify_taste_profiles SET production_dna = ?,
               research_status = 'complete',
               last_updated = CURRENT_TIMESTAMP WHERE user_id = ?""",
            (dna_text, user_id)
        )


# ─── SoundCloud Tokens ────────────────────────────────────────

def save_soundcloud_tokens(user_id, access_token, refresh_token, expiry):
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO soundcloud_tokens
               (user_id, access_token, refresh_token, token_expiry,
                last_refreshed)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (user_id, access_token, refresh_token, expiry)
        )


def get_soundcloud_tokens(user_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM soundcloud_tokens WHERE user_id = ?", (user_id,)
        ).fetchone()
        return _row_to_dict(row)


# ─── SoundCloud Data ──────────────────────────────────────────

def save_soundcloud_likes(user_id, likes_list):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM soundcloud_likes WHERE user_id = ?", (user_id,)
        )
        for like in likes_list:
            conn.execute(
                """INSERT INTO soundcloud_likes
                   (user_id, track_id, track_title, artist_name, artist_id,
                    genre, tag_list, duration_ms, playback_count, likes_count,
                    reposts_count, created_at_sc, liked_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (user_id, like.get("track_id"), like.get("track_title"),
                 like.get("artist_name"), like.get("artist_id"),
                 like.get("genre"), like.get("tag_list"),
                 like.get("duration_ms"), like.get("playback_count"),
                 like.get("likes_count"), like.get("reposts_count"),
                 like.get("created_at_sc"), like.get("liked_at"))
            )


def save_soundcloud_followings(user_id, followings_list):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM soundcloud_followings WHERE user_id = ?", (user_id,)
        )
        for f in followings_list:
            conn.execute(
                """INSERT INTO soundcloud_followings
                   (user_id, artist_id, artist_name, artist_permalink,
                    followers_count, track_count, genre, city, country)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (user_id, f.get("artist_id"), f.get("artist_name"),
                 f.get("artist_permalink"), f.get("followers_count"),
                 f.get("track_count"), f.get("genre"),
                 f.get("city"), f.get("country"))
            )


def save_soundcloud_reposts(user_id, reposts_list):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM soundcloud_reposts WHERE user_id = ?", (user_id,)
        )
        for r in reposts_list:
            conn.execute(
                """INSERT INTO soundcloud_reposts
                   (user_id, track_id, track_title, artist_name, artist_id,
                    genre, tag_list, reposted_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (user_id, r.get("track_id"), r.get("track_title"),
                 r.get("artist_name"), r.get("artist_id"),
                 r.get("genre"), r.get("tag_list"), r.get("reposted_at"))
            )


def save_soundcloud_playlists(user_id, playlists_list):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM soundcloud_playlists WHERE user_id = ?", (user_id,)
        )
        for p in playlists_list:
            conn.execute(
                """INSERT INTO soundcloud_playlists
                   (user_id, playlist_id, playlist_title, description,
                    genre, tag_list, track_count, is_public, created_at_sc)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (user_id, p.get("playlist_id"), p.get("playlist_title"),
                 p.get("description"), p.get("genre"), p.get("tag_list"),
                 p.get("track_count"), p.get("is_public"),
                 p.get("created_at_sc"))
            )


def save_soundcloud_user_tracks(user_id, tracks_list):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM soundcloud_user_tracks WHERE user_id = ?", (user_id,)
        )
        for t in tracks_list:
            conn.execute(
                """INSERT INTO soundcloud_user_tracks
                   (user_id, track_id, track_title, genre, tag_list,
                    bpm, key_signature, duration_ms, playback_count,
                    likes_count, created_at_sc)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (user_id, t.get("track_id"), t.get("track_title"),
                 t.get("genre"), t.get("tag_list"), t.get("bpm"),
                 t.get("key_signature"), t.get("duration_ms"),
                 t.get("playback_count"), t.get("likes_count"),
                 t.get("created_at_sc"))
            )


def get_soundcloud_likes(user_id):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM soundcloud_likes
               WHERE user_id = ? ORDER BY liked_at DESC""",
            (user_id,)
        ).fetchall()
        return _rows_to_dicts(rows)


def get_soundcloud_followings(user_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM soundcloud_followings WHERE user_id = ?",
            (user_id,)
        ).fetchall()
        return _rows_to_dicts(rows)


def get_soundcloud_reposts(user_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM soundcloud_reposts WHERE user_id = ? ORDER BY reposted_at DESC",
            (user_id,)
        ).fetchall()
        return _rows_to_dicts(rows)


def get_soundcloud_playlists(user_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM soundcloud_playlists WHERE user_id = ?",
            (user_id,)
        ).fetchall()
        return _rows_to_dicts(rows)


def get_soundcloud_user_tracks(user_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM soundcloud_user_tracks WHERE user_id = ?",
            (user_id,)
        ).fetchall()
        return _rows_to_dicts(rows)


def save_soundcloud_taste_profile(user_id, profile_dict):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT user_id FROM soundcloud_taste_profiles WHERE user_id = ?",
            (user_id,)
        ).fetchone()

        if existing:
            fields = {k: v for k, v in profile_dict.items() if k != "user_id"}
            fields["last_updated"] = datetime.utcnow().isoformat()
            set_clause = ", ".join(f'"{k}" = ?' for k in fields)
            values = list(fields.values()) + [user_id]
            conn.execute(
                f"UPDATE soundcloud_taste_profiles SET {set_clause} WHERE user_id = ?",
                values
            )
        else:
            profile_dict["user_id"] = user_id
            cols = ", ".join(f'"{k}"' for k in profile_dict)
            placeholders = ", ".join("?" * len(profile_dict))
            conn.execute(
                f"INSERT INTO soundcloud_taste_profiles ({cols}) VALUES ({placeholders})",
                list(profile_dict.values())
            )


def get_soundcloud_taste_profile(user_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM soundcloud_taste_profiles WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        return _row_to_dict(row)


def update_soundcloud_research_status(user_id, status):
    with get_connection() as conn:
        conn.execute(
            """UPDATE soundcloud_taste_profiles SET research_status = ?,
               last_updated = CURRENT_TIMESTAMP WHERE user_id = ?""",
            (status, user_id)
        )


def save_soundcloud_production_dna(user_id, dna_text):
    with get_connection() as conn:
        conn.execute(
            """UPDATE soundcloud_taste_profiles SET production_dna = ?,
               research_status = 'complete',
               last_updated = CURRENT_TIMESTAMP WHERE user_id = ?""",
            (dna_text, user_id)
        )


def clear_soundcloud_data(user_id):
    """Clear all SoundCloud listening data for a user (not artist_research_cache)."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM soundcloud_likes WHERE user_id = ?", (user_id,)
        )
        conn.execute(
            "DELETE FROM soundcloud_followings WHERE user_id = ?", (user_id,)
        )
        conn.execute(
            "DELETE FROM soundcloud_reposts WHERE user_id = ?", (user_id,)
        )
        conn.execute(
            "DELETE FROM soundcloud_playlists WHERE user_id = ?", (user_id,)
        )
        conn.execute(
            "DELETE FROM soundcloud_user_tracks WHERE user_id = ?", (user_id,)
        )


def disconnect_soundcloud(user_id):
    """Clear all SoundCloud data including tokens and taste profile."""
    clear_soundcloud_data(user_id)
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM soundcloud_taste_profiles WHERE user_id = ?", (user_id,)
        )
        conn.execute(
            "DELETE FROM soundcloud_tokens WHERE user_id = ?", (user_id,)
        )
        conn.execute(
            """UPDATE users SET soundcloud_id = NULL,
               updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (user_id,)
        )


# ─── Sessions ──────────────────────────────────────────────────

def create_session(user_id, name="Untitled Session", bpm=128, key="E",
                   scale="minor", genre="tech_house", skill_level="expert"):
    with get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET is_active = 0 WHERE user_id = ?", (user_id,)
        )
        cursor = conn.execute(
            """INSERT INTO sessions
               (user_id, session_name, bpm, key, scale, genre, skill_level,
                is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
            (user_id, name, bpm, key, scale, genre, skill_level)
        )
        return cursor.lastrowid


def get_active_session(user_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE user_id = ? AND is_active = 1",
            (user_id,)
        ).fetchone()
        return _row_to_dict(row)


def get_user_sessions(user_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,)
        ).fetchall()
        return _rows_to_dicts(rows)


def update_session(session_id, **fields):
    if not fields:
        return
    fields["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f'"{k}" = ?' for k in fields)
    values = list(fields.values()) + [session_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE sessions SET {set_clause} WHERE id = ?", values)


def set_active_session(user_id, session_id):
    with get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET is_active = 0 WHERE user_id = ?", (user_id,)
        )
        conn.execute(
            "UPDATE sessions SET is_active = 1 WHERE id = ? AND user_id = ?",
            (session_id, user_id)
        )


# ─── Session Elements ──────────────────────────────────────────

def save_element(session_id, element_name, category, status="empty",
                 summary=None, midi_note_data=None, output_metadata=None,
                 bars=None, note_count=None, velocity_range_low=None,
                 velocity_range_high=None, pitch_range_low=None,
                 pitch_range_high=None, rhythm_summary=None,
                 pitch_center=None, intervals_used=None):
    midi_json = json.dumps(midi_note_data) if midi_note_data else None
    meta_json = json.dumps(output_metadata) if output_metadata else None
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO session_elements
               (session_id, element_name, element_category, status, summary,
                midi_note_data, output_metadata, bars, note_count,
                velocity_range_low, velocity_range_high,
                pitch_range_low, pitch_range_high,
                rhythm_summary, pitch_center, intervals_used)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(session_id, element_name)
               DO UPDATE SET status=excluded.status, summary=excluded.summary,
                 midi_note_data=excluded.midi_note_data,
                 output_metadata=excluded.output_metadata,
                 bars=excluded.bars, note_count=excluded.note_count,
                 velocity_range_low=excluded.velocity_range_low,
                 velocity_range_high=excluded.velocity_range_high,
                 pitch_range_low=excluded.pitch_range_low,
                 pitch_range_high=excluded.pitch_range_high,
                 rhythm_summary=excluded.rhythm_summary,
                 pitch_center=excluded.pitch_center,
                 intervals_used=excluded.intervals_used,
                 updated_at=CURRENT_TIMESTAMP""",
            (session_id, element_name, category, status, summary,
             midi_json, meta_json, bars, note_count,
             velocity_range_low, velocity_range_high,
             pitch_range_low, pitch_range_high,
             rhythm_summary, pitch_center, intervals_used)
        )


def get_element(session_id, element_name):
    with get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM session_elements
               WHERE session_id = ? AND element_name = ?""",
            (session_id, element_name)
        ).fetchone()
        result = _row_to_dict(row)
        if result and result.get("midi_note_data"):
            result["midi_note_data"] = json.loads(result["midi_note_data"])
        if result and result.get("output_metadata"):
            result["output_metadata"] = json.loads(result["output_metadata"])
        return result


def get_all_elements(session_id):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM session_elements
               WHERE session_id = ? ORDER BY element_name""",
            (session_id,)
        ).fetchall()
        results = _rows_to_dicts(rows)
        for r in results:
            if r.get("midi_note_data"):
                r["midi_note_data"] = json.loads(r["midi_note_data"])
            if r.get("output_metadata"):
                r["output_metadata"] = json.loads(r["output_metadata"])
        return results


def get_elements_with_midi(session_id):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM session_elements
               WHERE session_id = ? AND midi_note_data IS NOT NULL
               AND status IN ('in_progress', 'complete')
               ORDER BY element_name""",
            (session_id,)
        ).fetchall()
        results = _rows_to_dicts(rows)
        for r in results:
            if r.get("midi_note_data"):
                r["midi_note_data"] = json.loads(r["midi_note_data"])
            if r.get("output_metadata"):
                r["output_metadata"] = json.loads(r["output_metadata"])
        return results


def update_element_status(session_id, element_name, status):
    with get_connection() as conn:
        conn.execute(
            """UPDATE session_elements SET status = ?,
               updated_at = CURRENT_TIMESTAMP
               WHERE session_id = ? AND element_name = ?""",
            (status, session_id, element_name)
        )


# ─── Chat History ──────────────────────────────────────────────

def save_message(session_id, element_name, role, content, has_output=False,
                 output_id=None, output_data=None, file_url=None):
    output_json = json.dumps(output_data) if output_data else None
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO chat_history
               (session_id, element_name, role, content, has_output,
                output_id, output_data, file_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, element_name, role, content, has_output,
             output_id, output_json, file_url)
        )
        return cursor.lastrowid


def get_chat_history(session_id, element_name):
    with get_connection() as conn:
        if element_name is None:
            rows = conn.execute(
                """SELECT * FROM chat_history
                   WHERE session_id = ? AND element_name IS NULL
                   ORDER BY id""",
                (session_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM chat_history
                   WHERE session_id = ? AND element_name = ?
                   ORDER BY id""",
                (session_id, element_name)
            ).fetchall()
        results = _rows_to_dicts(rows)
        for r in results:
            if r.get("output_data"):
                r["output_data"] = json.loads(r["output_data"])
        return results


def get_all_chat_history(session_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_history WHERE session_id = ? ORDER BY id",
            (session_id,)
        ).fetchall()
        results = _rows_to_dicts(rows)
        for r in results:
            if r.get("output_data"):
                r["output_data"] = json.loads(r["output_data"])
        return results


# ─── Generated Outputs ─────────────────────────────────────────

def save_output(session_id, user_id, element_name, output_type, output_name,
                prompt_text=None, midi_note_data=None, arrangement_data=None,
                signal_chain_data=None, bars=None, bpm=None, key=None,
                scale=None, genre=None, skill_level=None,
                system_prompt_hash=None, generation_time_ms=None,
                tokens_used=None):
    midi_json = json.dumps(midi_note_data) if midi_note_data else None
    arr_json = json.dumps(arrangement_data) if arrangement_data else None
    chain_json = json.dumps(signal_chain_data) if signal_chain_data else None
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO generated_outputs
               (session_id, user_id, element_name, output_type, output_name,
                midi_note_data, arrangement_data, signal_chain_data,
                bars, bpm, key, scale, genre, skill_level,
                prompt_text, system_prompt_hash,
                generation_time_ms, tokens_used)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (session_id, user_id, element_name, output_type, output_name,
             midi_json, arr_json, chain_json,
             bars, bpm, key, scale, genre, skill_level,
             prompt_text, system_prompt_hash,
             generation_time_ms, tokens_used)
        )
        return cursor.lastrowid


def get_session_outputs(session_id):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM generated_outputs
               WHERE session_id = ? ORDER BY created_at""",
            (session_id,)
        ).fetchall()
        results = _rows_to_dicts(rows)
        for r in results:
            if r.get("midi_note_data"):
                r["midi_note_data"] = json.loads(r["midi_note_data"])
            if r.get("arrangement_data"):
                r["arrangement_data"] = json.loads(r["arrangement_data"])
            if r.get("signal_chain_data"):
                r["signal_chain_data"] = json.loads(r["signal_chain_data"])
        return results


def get_user_outputs(user_id):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM generated_outputs
               WHERE user_id = ? ORDER BY created_at DESC""",
            (user_id,)
        ).fetchall()
        results = _rows_to_dicts(rows)
        for r in results:
            if r.get("midi_note_data"):
                r["midi_note_data"] = json.loads(r["midi_note_data"])
        return results


def mark_output_downloaded(output_id):
    with get_connection() as conn:
        conn.execute(
            "UPDATE generated_outputs SET was_downloaded = 1 WHERE id = ?",
            (output_id,)
        )


# ─── Feedback ──────────────────────────────────────────────────

def save_feedback(user_id, output_id, rating, text=None):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO user_feedback
               (user_id, output_id, rating, feedback_text)
               VALUES (?, ?, ?, ?)""",
            (user_id, output_id, rating, text)
        )


# ─── Analytics ─────────────────────────────────────────────────

def log_event(user_id, event_type, event_data=None, session_id=None):
    data_json = json.dumps(event_data) if event_data else None
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO app_analytics
               (user_id, event_type, event_data, session_id)
               VALUES (?, ?, ?, ?)""",
            (user_id, event_type, data_json, session_id)
        )


# ─── Music Theory Helpers ──────────────────────────────────────

def _midi_note_name(pitch):
    octave = pitch // 12 - 2
    return f"{NOTE_NAMES[pitch % 12]}{octave}"


def _note_position(start):
    zero_indexed = start - 1
    bar = int(zero_indexed // 4) + 1
    beat_in_bar = zero_indexed % 4
    beat = int(beat_in_bar) + 1
    frac = beat_in_bar - int(beat_in_bar)
    sub = round(frac / 0.25) + 1
    return f"{bar}.{beat}.{sub}"


def _build_rhythm_summary(notes):
    sub_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    velocities = []
    for n in notes:
        frac = (n.get("start", 1) - 1) % 1
        sub = round(frac / 0.25) + 1
        sub_counts[sub] = sub_counts.get(sub, 0) + 1
        velocities.append(n.get("velocity", 100))

    total = len(notes)
    parts = []
    if sub_counts[1] / total > 0.4:
        parts.append("Main hits on .1 positions (on-beat)")
    elif sub_counts[1] > 0:
        parts.append("some on-beat hits (.1)")
    if sub_counts[3] / total > 0.3:
        parts.append("strong .3 presence (offbeat)")
    elif sub_counts[3] > 0:
        parts.append("some .3 hits (offbeat)")
    sixteenth_count = sub_counts[2] + sub_counts[4]
    if sixteenth_count > 0:
        if sixteenth_count / total > 0.3:
            parts.append("16th note movement (.2/.4)")
        else:
            parts.append("occasional 16th fills")

    avg_vel = round(sum(velocities) / len(velocities))
    min_vel = min(velocities)
    max_vel = max(velocities)
    if max_vel - min_vel < 10:
        parts.append(f"flat velocity ~{avg_vel}")
    else:
        ghost_threshold = avg_vel * 0.7
        ghost_count = sum(1 for v in velocities if v < ghost_threshold)
        if ghost_count > 0:
            parts.append(
                f"ghost hits at ~{round(min_vel / max_vel * 100)}% velocity"
            )
        else:
            parts.append(f"velocity range {min_vel}-{max_vel}")
    return ", ".join(parts)


def _bars_from_notes(notes):
    if not notes:
        return 0
    max_beat = max(n.get("start", 1) + n.get("duration", 0.25) for n in notes)
    return int(math.ceil((max_beat - 1) / 4))


def _collapse_repeated_bars(notes, total_bars):
    if total_bars <= 2:
        return None
    bar_notes = {b: [] for b in range(1, total_bars + 1)}
    for n in notes:
        bar = int((n.get("start", 1) - 1) // 4) + 1
        if bar in bar_notes:
            bar_notes[bar].append(n)

    def bar_fingerprint(bar_num):
        b_notes = bar_notes.get(bar_num, [])
        fps = []
        for n in b_notes:
            rel_start = f"{(n.get('start', 1) - 1) % 4:.3f}"
            fps.append(f"{rel_start}:{n.get('pitch', 60)}:{n.get('velocity', 100)}")
        return "|".join(sorted(fps))

    fingerprints = {}
    repeats = {}
    for b in range(1, total_bars + 1):
        fp = bar_fingerprint(b)
        if fp in fingerprints:
            repeats[b] = fingerprints[fp]
        else:
            fingerprints[fp] = b
    return repeats if repeats else None


def _compute_element_analysis(notes, element_name):
    """Compute analysis fields from a MIDI note array."""
    if not notes:
        return {}
    pitches = [n.get("pitch", 60) for n in notes]
    velocities = [n.get("velocity", 100) for n in notes]
    analysis = {
        "bars": _bars_from_notes(notes),
        "note_count": len(notes),
        "velocity_range_low": min(velocities),
        "velocity_range_high": max(velocities),
        "pitch_range_low": min(pitches),
        "pitch_range_high": max(pitches),
        "rhythm_summary": _build_rhythm_summary(notes),
    }
    if element_name in MELODIC_ELEMENTS_SET and len(set(pitches)) > 1:
        pitch_counts = {}
        for p in pitches:
            pitch_counts[p] = pitch_counts.get(p, 0) + 1
        center = max(pitch_counts, key=pitch_counts.get)
        analysis["pitch_center"] = _midi_note_name(center)

        sorted_notes = sorted(notes, key=lambda n: n.get("start", 1))
        intervals = []
        for i in range(1, len(sorted_notes)):
            semi = abs(
                sorted_notes[i].get("pitch", 60)
                - sorted_notes[i - 1].get("pitch", 60)
            ) % 12
            name = INTERVAL_NAMES_MAP.get(semi)
            if name and name not in intervals:
                intervals.append(name)
        analysis["intervals_used"] = ", ".join(intervals) if intervals else None
    return analysis


# ─── Musical Context Builder ───────────────────────────────────

def build_musical_context_from_db(session_id, bpm, key, scale):
    """Build the MUSICAL CONTEXT string from database element data."""
    elements = get_elements_with_midi(session_id)
    if not elements:
        return ""

    blocks = []
    for elem in elements:
        elem_name = elem["element_name"]
        notes = elem.get("midi_note_data")
        if not notes or not isinstance(notes, list) or len(notes) == 0:
            continue

        is_drum = elem_name in DRUM_ELEMENTS
        is_melodic = elem_name in MELODIC_ELEMENTS_SET
        total_bars = _bars_from_notes(notes)

        pitch_set = sorted(set(n.get("pitch", 60) for n in notes))
        pitch_names = [f"{_midi_note_name(p)}({p})" for p in pitch_set]

        block = f"[ELEMENT: {elem_name}]\n"
        block += f"Bars: {total_bars} | BPM: {bpm}"
        if is_melodic:
            block += f" | Key: {key} {scale}"
        block += f" | Notes: {len(notes)}\n"
        block += f"Pitches{' used' if is_melodic else ''}: "
        block += f"{', '.join(pitch_names)}\n"

        sorted_notes = sorted(notes, key=lambda n: n.get("start", 1))
        pattern_notes = list(sorted_notes)

        repeats = (
            _collapse_repeated_bars(sorted_notes, total_bars) if is_drum else None
        )
        repeat_note = ""
        if repeats:
            repeated_bars = set(repeats.keys())
            pattern_notes = [
                n for n in sorted_notes
                if int((n.get("start", 1) - 1) // 4) + 1 not in repeated_bars
            ]
            by_source = {}
            for rep_bar, src_bar in repeats.items():
                by_source.setdefault(src_bar, []).append(str(rep_bar))
            repeat_parts = [
                f"bar {', '.join(reps)} = bar {src}"
                for src, reps in by_source.items()
            ]
            repeat_note = f"  (Repeats: {'; '.join(repeat_parts)})\n"

        if len(pattern_notes) > 32:
            first16 = pattern_notes[:16]
            last16 = pattern_notes[-16:]
            pattern_notes = first16 + [None] + last16

        block += "Pattern:\n"
        for n in pattern_notes:
            if n is None:
                block += "  ...\n"
            else:
                pos = _note_position(n.get("start", 1))
                name = _midi_note_name(n.get("pitch", 60))
                vel = n.get("velocity", 100)
                block += f"  {pos} → {name} @ {vel}\n"
        if repeat_note:
            block += repeat_note

        block += f"Rhythm summary: {_build_rhythm_summary(notes)}\n"

        freq_range = ELEMENT_FREQ_RANGES.get(elem_name)
        if freq_range:
            block += f"Frequency range: {freq_range}\n"

        if is_melodic and len(pitch_set) > 1:
            durations = [n.get("duration", 0.25) for n in notes]
            avg_dur = sum(durations) / len(durations)
            if avg_dur >= 0.9:
                dur_char = "legato"
            elif avg_dur >= 0.45:
                dur_char = "~85% grid (legato gapped)"
            elif avg_dur >= 0.2:
                dur_char = "staccato"
            else:
                dur_char = "very short"
            block += f"Note lengths: {dur_char}\n"

            pitch_counts = {}
            for n in notes:
                p = n.get("pitch", 60)
                pitch_counts[p] = pitch_counts.get(p, 0) + 1
            center = max(pitch_counts, key=pitch_counts.get)
            block += f"Pitch center: {_midi_note_name(center)} (gravity note)\n"

            intervals = []
            for i in range(1, len(sorted_notes)):
                semi = abs(
                    sorted_notes[i].get("pitch", 60)
                    - sorted_notes[i - 1].get("pitch", 60)
                ) % 12
                name = INTERVAL_NAMES_MAP.get(semi)
                if name and name not in intervals:
                    intervals.append(name)
            if intervals:
                block += f"Intervals used: {', '.join(intervals)}\n"

        blocks.append(block)

    return "\n".join(blocks) if blocks else ""


# ─── Full Session State Save/Load ──────────────────────────────

def save_full_session_state(user_id, state):
    """Save the complete frontend session state to the database.
    Uses a single connection/transaction for atomicity."""
    with get_connection() as conn:
        # Get or create active session
        row = conn.execute(
            "SELECT id FROM sessions WHERE user_id = ? AND is_active = 1",
            (user_id,)
        ).fetchone()

        if row:
            session_id = row["id"]
        else:
            cursor = conn.execute(
                """INSERT INTO sessions (user_id, is_active)
                   VALUES (?, 1)""",
                (user_id,)
            )
            session_id = cursor.lastrowid

        # Update session settings
        conn.execute(
            """UPDATE sessions SET bpm=?, key=?, scale=?, genre=?,
               skill_level=?, active_element=?, active_chat_tab=?,
               updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (state.get("bpm", 128), state.get("key", "E"),
             state.get("scale", "minor"), state.get("genre", "tech_house"),
             state.get("skillLevel", "expert"),
             state.get("activeElement"), state.get("activeChatTab", "element"),
             session_id)
        )

        # Save elements
        elements = state.get("elements", {})
        for elem_id, elem_data in elements.items():
            category = ELEMENT_CATEGORIES.get(elem_id, "other")
            status = elem_data.get("status", "empty")
            summary = elem_data.get("summary", "")

            # Extract latest MIDI notes from outputs
            midi_notes = None
            outputs = elem_data.get("outputs", [])
            for out in reversed(outputs):
                if (out.get("type") == "midi"
                        and isinstance(out.get("notes"), list)
                        and len(out["notes"]) > 0):
                    midi_notes = out["notes"]
                    break

            midi_json = json.dumps(midi_notes) if midi_notes else None
            outputs_json = json.dumps(outputs) if outputs else None

            # Compute analysis if we have MIDI data
            analysis = _compute_element_analysis(midi_notes, elem_id) \
                if midi_notes else {}

            conn.execute(
                """INSERT INTO session_elements
                   (session_id, element_name, element_category, status,
                    summary, midi_note_data, output_metadata,
                    bars, note_count, velocity_range_low, velocity_range_high,
                    pitch_range_low, pitch_range_high, rhythm_summary,
                    pitch_center, intervals_used)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(session_id, element_name)
                   DO UPDATE SET status=excluded.status,
                     summary=excluded.summary,
                     midi_note_data=excluded.midi_note_data,
                     output_metadata=excluded.output_metadata,
                     bars=excluded.bars, note_count=excluded.note_count,
                     velocity_range_low=excluded.velocity_range_low,
                     velocity_range_high=excluded.velocity_range_high,
                     pitch_range_low=excluded.pitch_range_low,
                     pitch_range_high=excluded.pitch_range_high,
                     rhythm_summary=excluded.rhythm_summary,
                     pitch_center=excluded.pitch_center,
                     intervals_used=excluded.intervals_used,
                     updated_at=CURRENT_TIMESTAMP""",
                (session_id, elem_id, category, status, summary,
                 midi_json, outputs_json,
                 analysis.get("bars"), analysis.get("note_count"),
                 analysis.get("velocity_range_low"),
                 analysis.get("velocity_range_high"),
                 analysis.get("pitch_range_low"),
                 analysis.get("pitch_range_high"),
                 analysis.get("rhythm_summary"),
                 analysis.get("pitch_center"),
                 analysis.get("intervals_used"))
            )

            # Save chat history for this element
            conn.execute(
                """DELETE FROM chat_history
                   WHERE session_id = ? AND element_name = ?""",
                (session_id, elem_id)
            )
            for msg in elem_data.get("chatHistory", []):
                out_data = msg.get("_outputData")
                out_json = json.dumps(out_data) if out_data else None
                conn.execute(
                    """INSERT INTO chat_history
                       (session_id, element_name, role, content,
                        has_output, output_data, file_url)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (session_id, elem_id, msg["role"], msg["content"],
                     1 if out_data else 0, out_json, msg.get("_fileUrl"))
                )

        # Save general chat
        conn.execute(
            """DELETE FROM chat_history
               WHERE session_id = ? AND element_name IS NULL""",
            (session_id,)
        )
        for msg in state.get("generalMessages", []):
            out_data = msg.get("_outputData")
            out_json = json.dumps(out_data) if out_data else None
            conn.execute(
                """INSERT INTO chat_history
                   (session_id, element_name, role, content,
                    has_output, output_data, file_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (session_id, None, msg["role"], msg["content"],
                 1 if out_data else 0, out_json, msg.get("_fileUrl"))
            )

        # Save general outputs as a virtual element "__general__"
        general_outputs = state.get("generalOutputs", [])
        general_outputs_json = json.dumps(general_outputs) if general_outputs \
            else None
        conn.execute(
            """INSERT INTO session_elements
               (session_id, element_name, element_category, status,
                output_metadata)
               VALUES (?, '__general__', 'system', 'empty', ?)
               ON CONFLICT(session_id, element_name)
               DO UPDATE SET output_metadata=excluded.output_metadata,
                 updated_at=CURRENT_TIMESTAMP""",
            (session_id, general_outputs_json)
        )

        return session_id


def load_full_session_state(user_id):
    """Load the complete session state from the database.
    Returns a dict in the same format the frontend expects, or None."""
    with get_connection() as conn:
        session = conn.execute(
            "SELECT * FROM sessions WHERE user_id = ? AND is_active = 1",
            (user_id,)
        ).fetchone()
        if not session:
            return None

        session_id = session["id"]

        state = {
            "sessionId": session_id,
            "bpm": session["bpm"],
            "key": session["key"],
            "scale": session["scale"],
            "genre": session["genre"],
            "skillLevel": session["skill_level"],
            "activeElement": session["active_element"],
            "activeChatTab": session["active_chat_tab"] or "element",
        }

        # Load elements
        elements = {}
        general_outputs = []

        elem_rows = conn.execute(
            "SELECT * FROM session_elements WHERE session_id = ?",
            (session_id,)
        ).fetchall()

        for row in elem_rows:
            elem_name = row["element_name"]

            if elem_name == "__general__":
                raw = row["output_metadata"]
                general_outputs = json.loads(raw) if raw else []
                continue

            # Load chat history for this element
            chat_rows = conn.execute(
                """SELECT * FROM chat_history
                   WHERE session_id = ? AND element_name = ?
                   ORDER BY id""",
                (session_id, elem_name)
            ).fetchall()

            chat_history = []
            for cr in chat_rows:
                msg = {"role": cr["role"], "content": cr["content"]}
                if cr["output_data"]:
                    msg["_outputData"] = json.loads(cr["output_data"])
                if cr["file_url"]:
                    msg["_fileUrl"] = cr["file_url"]
                chat_history.append(msg)

            raw_outputs = row["output_metadata"]
            outputs = json.loads(raw_outputs) if raw_outputs else []

            elements[elem_name] = {
                "status": row["status"] or "empty",
                "chatHistory": chat_history,
                "outputs": outputs,
                "summary": row["summary"] or "",
            }

        state["elements"] = elements

        # Load general chat
        general_chat_rows = conn.execute(
            """SELECT * FROM chat_history
               WHERE session_id = ? AND element_name IS NULL
               ORDER BY id""",
            (session_id,)
        ).fetchall()

        general_messages = []
        for cr in general_chat_rows:
            msg = {"role": cr["role"], "content": cr["content"]}
            if cr["output_data"]:
                msg["_outputData"] = json.loads(cr["output_data"])
            if cr["file_url"]:
                msg["_fileUrl"] = cr["file_url"]
            general_messages.append(msg)

        state["generalMessages"] = general_messages
        state["generalOutputs"] = general_outputs

        return state


# ─── Cleanup ───────────────────────────────────────────────────

def delete_user_data(user_id):
    """Delete all data for a user (account deletion / disconnect)."""
    with get_connection() as conn:
        conn.execute("DELETE FROM app_analytics WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM user_feedback WHERE user_id = ?", (user_id,))
        conn.execute(
            "DELETE FROM generated_outputs WHERE user_id = ?", (user_id,)
        )
        session_ids = [
            r["id"] for r in conn.execute(
                "SELECT id FROM sessions WHERE user_id = ?", (user_id,)
            ).fetchall()
        ]
        for sid in session_ids:
            conn.execute(
                "DELETE FROM chat_history WHERE session_id = ?", (sid,)
            )
            conn.execute(
                "DELETE FROM session_elements WHERE session_id = ?", (sid,)
            )
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.execute(
            "DELETE FROM spotify_saved_tracks WHERE user_id = ?", (user_id,)
        )
        conn.execute(
            "DELETE FROM spotify_recent_plays WHERE user_id = ?", (user_id,)
        )
        conn.execute(
            "DELETE FROM spotify_top_tracks WHERE user_id = ?", (user_id,)
        )
        conn.execute(
            "DELETE FROM spotify_top_artists WHERE user_id = ?", (user_id,)
        )
        conn.execute(
            "DELETE FROM spotify_taste_profiles WHERE user_id = ?", (user_id,)
        )
        conn.execute(
            "DELETE FROM spotify_tokens WHERE user_id = ?", (user_id,)
        )
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def clear_session(session_id):
    """Clear a session's elements, chat, and outputs."""
    with get_connection() as conn:
        # Delete feedback referencing outputs in this session
        conn.execute(
            """DELETE FROM user_feedback WHERE output_id IN
               (SELECT id FROM generated_outputs WHERE session_id = ?)""",
            (session_id,)
        )
        conn.execute(
            "DELETE FROM app_analytics WHERE session_id = ?", (session_id,)
        )
        conn.execute(
            "DELETE FROM chat_history WHERE session_id = ?", (session_id,)
        )
        conn.execute(
            "DELETE FROM session_elements WHERE session_id = ?", (session_id,)
        )
        conn.execute(
            "DELETE FROM generated_outputs WHERE session_id = ?", (session_id,)
        )
        conn.execute(
            """UPDATE sessions SET updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (session_id,)
        )


def delete_session(session_id):
    """Delete a session and all its data entirely."""
    clear_session(session_id)
    with get_connection() as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
