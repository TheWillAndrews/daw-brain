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
    get_user_top_artists, get_all_genres_for_user,
    save_taste_profile,
)
from brain.genre_attributes import compute_taste_from_genres

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


def compute_taste_profile(user_id):
    """Compute the quantitative taste profile from all stored Spotify data.

    Uses genre-based attribute lookup (genre_attributes.py) instead of
    deprecated Spotify audio features.
    """
    log.info(f"Computing taste profile for user {user_id}")

    # Gather all genre tags (weighted by time range + followed artists)
    all_genres = get_all_genres_for_user(user_id)

    if not all_genres:
        log.warning(f"No genre data found for user {user_id}")
        return None

    # Compute taste attributes from genres
    taste = compute_taste_from_genres(all_genres)

    # Genre analysis with evolution tracking
    top_genres, evolving_taste = _analyze_genres(user_id)

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
