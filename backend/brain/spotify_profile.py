"""
Spotify taste profile computation — builds a quantitative listener profile
from collected Spotify data using genre-based attribute lookup.

NOTE: Audio features were deprecated by Spotify in November 2024.
This module uses genre tags from top/followed artists to infer
BPM, energy, mood, and other production attributes.
"""

import json
import logging
from collections import Counter

from brain.database import (
    get_connection, get_user_top_artists, get_all_genres_for_user,
    save_taste_profile,
)
from brain.genre_attributes import compute_taste_from_genres, compute_weighted_taste

log = logging.getLogger("daw-brain")

# Weight multipliers by time range
WEIGHTS = {
    "short_term": 3,
    "medium_term": 2,
    "long_term": 1,
}


def _analyze_genres(user_id):
    """Analyze genres from top artists across all time ranges.

    Returns (top_genres_list, evolving_taste_description).
    """
    genre_counts = Counter()
    short_genres = Counter()
    long_genres = Counter()

    for time_range in ["short_term", "medium_term", "long_term"]:
        artists = get_user_top_artists(user_id, time_range)
        weight = WEIGHTS.get(time_range, 1)
        for artist in artists:
            genres_raw = artist.get("genres", "[]")
            try:
                genres = json.loads(genres_raw) if isinstance(genres_raw, str) else genres_raw
            except (json.JSONDecodeError, TypeError):
                genres = []
            for genre in genres:
                genre_counts[genre] += weight
                if time_range == "short_term":
                    short_genres[genre] += 1
                elif time_range == "long_term":
                    long_genres[genre] += 1

    top_genres = [g for g, _ in genre_counts.most_common(15)]

    # Taste evolution: compare short_term vs long_term top genres
    evolving = ""
    if short_genres and long_genres:
        short_top = set(g for g, _ in short_genres.most_common(5))
        long_top = set(g for g, _ in long_genres.most_common(5))
        new_genres = short_top - long_top
        dropped_genres = long_top - short_top
        if new_genres and dropped_genres:
            evolving = f"Shifting from {', '.join(list(dropped_genres)[:3])} toward {', '.join(list(new_genres)[:3])}"
        elif new_genres:
            evolving = f"Recently exploring: {', '.join(list(new_genres)[:3])}"
        elif dropped_genres:
            evolving = f"Consistent taste, less: {', '.join(list(dropped_genres)[:3])}"
        else:
            evolving = "Consistent taste across time ranges"

    return top_genres, evolving


def _parse_genres_column(raw):
    """Safely parse a JSON genres column value into a list."""
    if not raw:
        return []
    try:
        genres = json.loads(raw) if isinstance(raw, str) else raw
        return genres if isinstance(genres, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def build_genre_sources(user_id):
    """Pull genre data from all Spotify sources, grouped by source type.

    Returns dict suitable for compute_weighted_taste().
    """
    sources = {}

    with get_connection() as conn:
        # TOP ARTISTS — genres stored directly on artist rows
        rows = conn.execute(
            "SELECT genres FROM spotify_top_artists "
            "WHERE user_id = ? AND genres IS NOT NULL AND genres != '' AND genres != '[]'",
            (user_id,),
        ).fetchall()
        sources["top_artists"] = []
        for row in rows:
            sources["top_artists"].extend(_parse_genres_column(row["genres"]))

        # TOP TRACKS — cross-reference artist_id against top_artists/followed_artists for genres
        track_artist_ids = [
            r["artist_id"] for r in conn.execute(
                "SELECT DISTINCT artist_id FROM spotify_top_tracks "
                "WHERE user_id = ? AND artist_id IS NOT NULL",
                (user_id,),
            ).fetchall()
        ]
        sources["top_tracks"] = []
        for aid in track_artist_ids:
            artist_row = conn.execute(
                "SELECT genres FROM spotify_top_artists WHERE artist_id = ? AND genres IS NOT NULL LIMIT 1",
                (aid,),
            ).fetchone()
            if not artist_row:
                artist_row = conn.execute(
                    "SELECT genres FROM followed_artists WHERE spotify_id = ? AND genres IS NOT NULL LIMIT 1",
                    (aid,),
                ).fetchone()
            if artist_row:
                sources["top_tracks"].extend(_parse_genres_column(artist_row["genres"]))

        # FOLLOWED ARTISTS — genres stored directly
        rows = conn.execute(
            "SELECT genres FROM followed_artists "
            "WHERE user_id = ? AND genres IS NOT NULL AND genres != '' AND genres != '[]'",
            (user_id,),
        ).fetchall()
        sources["followed_artists"] = []
        for row in rows:
            sources["followed_artists"].extend(_parse_genres_column(row["genres"]))

        # SAVED TRACKS — cross-reference artist_id
        saved_artist_ids = [
            r["artist_id"] for r in conn.execute(
                "SELECT DISTINCT artist_id FROM spotify_saved_tracks "
                "WHERE user_id = ? AND artist_id IS NOT NULL",
                (user_id,),
            ).fetchall()
        ]
        sources["saved_tracks"] = []
        for aid in saved_artist_ids:
            artist_row = conn.execute(
                "SELECT genres FROM spotify_top_artists WHERE artist_id = ? AND genres IS NOT NULL LIMIT 1",
                (aid,),
            ).fetchone()
            if not artist_row:
                artist_row = conn.execute(
                    "SELECT genres FROM followed_artists WHERE spotify_id = ? AND genres IS NOT NULL LIMIT 1",
                    (aid,),
                ).fetchone()
            if artist_row:
                sources["saved_tracks"].extend(_parse_genres_column(artist_row["genres"]))

        # RECENTLY PLAYED — no artist_id column, match by artist_name
        recent_names = [
            r["artist_name"] for r in conn.execute(
                "SELECT DISTINCT artist_name FROM spotify_recent_plays "
                "WHERE user_id = ? AND artist_name IS NOT NULL",
                (user_id,),
            ).fetchall()
        ]
        sources["recent_plays"] = []
        for name in recent_names:
            artist_row = conn.execute(
                "SELECT genres FROM spotify_top_artists WHERE artist_name = ? AND genres IS NOT NULL LIMIT 1",
                (name,),
            ).fetchone()
            if not artist_row:
                artist_row = conn.execute(
                    "SELECT genres FROM followed_artists WHERE name = ? AND genres IS NOT NULL LIMIT 1",
                    (name,),
                ).fetchone()
            if artist_row:
                sources["recent_plays"].extend(_parse_genres_column(artist_row["genres"]))

    return sources


def get_excluded_sources(user_id):
    """Read the user's excluded taste sources from the database."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT excluded_taste_sources FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row and row["excluded_taste_sources"]:
            try:
                return json.loads(row["excluded_taste_sources"])
            except (json.JSONDecodeError, TypeError):
                pass
    return []


def compute_taste_profile(user_id, excluded_sources=None):
    """Compute the quantitative taste profile from all stored Spotify data.

    Uses weighted multi-source genre lookup (genre_attributes.py) instead of
    deprecated Spotify audio features.
    """
    log.info(f"Computing taste profile for user {user_id}")

    # Load excluded sources from DB if not provided
    if excluded_sources is None:
        excluded_sources = get_excluded_sources(user_id)

    # Build genre sources from all Spotify data tables
    genre_sources = build_genre_sources(user_id)

    # Also gather flat genre list for evolution analysis (uses old path)
    all_genres = get_all_genres_for_user(user_id)

    # Compute weighted taste from grouped sources
    taste = compute_weighted_taste(genre_sources, excluded_sources=excluded_sources)

    # If weighted computation found no genres, fall back to flat list
    if taste["total_weighted_genres"] == 0 and all_genres:
        log.info("Weighted sources empty, falling back to flat genre list")
        taste = compute_taste_from_genres(all_genres)
        taste["sources_used"] = [{"source": "flat_fallback", "genre_count": len(all_genres), "weight": 1, "effective_count": len(all_genres)}]
        taste["total_weighted_genres"] = len(all_genres)
        taste["excluded_sources"] = excluded_sources

    if taste.get("genre_count", 0) == 0 and taste.get("total_weighted_genres", 0) == 0:
        log.warning(f"No genre data found for user {user_id}")
        return None

    # Genre analysis with evolution tracking
    top_genres, evolving_taste = _analyze_genres(user_id)
    # Use top_genres from weighted result if it has them
    if taste.get("top_genres"):
        top_genres = taste["top_genres"]

    # Build profile dict matching the DB schema
    profile = {
        "avg_bpm": taste["avg_bpm"],
        "bpm_range_low": taste["bpm_range"][0],
        "bpm_range_high": taste["bpm_range"][1],
        "preferred_bpm": taste["avg_bpm"],
        "preferred_keys": None,  # no key data without audio features
        "avg_energy": taste["energy_raw"],
        "avg_danceability": None,
        "avg_valence": None,
        "avg_instrumentalness": None,
        "avg_acousticness": None,
        "avg_speechiness": None,
        "avg_liveness": None,
        "avg_loudness": None,
        "avg_tempo": taste["avg_bpm"],
        "mood": taste["mood"],
        "energy_level": taste["energy"],
        "vocal_preference": taste["vocal_density"],
        "danceability_level": None,
        "top_genres": json.dumps(top_genres),
        "evolving_taste": evolving_taste,
        "research_status": "pending",
    }

    save_taste_profile(user_id, profile)
    log.info(f"Taste profile saved for user {user_id}: "
             f"BPM={taste['avg_bpm']}, mood={taste['mood']}, "
             f"energy={taste['energy']}, genres={len(top_genres)}")
    return profile
