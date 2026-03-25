"""
Spotify taste profile computation — builds a quantitative listener profile
from collected Spotify data using weighted averages.
"""

import json
import logging
from collections import Counter

from brain.database import (
    get_user_top_tracks, get_user_top_artists,
    get_user_saved_tracks, get_user_recent_plays,
    save_taste_profile,
)

log = logging.getLogger("daw-brain")

# Spotify key numbers to note names
KEY_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

# Weight multipliers by source
WEIGHTS = {
    "short_term": 3,
    "medium_term": 2,
    "long_term": 1,
    "saved": 2,
    "recent": 1.5,
}

# Audio feature fields to average
FEATURE_FIELDS = [
    "bpm", "energy", "danceability", "valence",
    "instrumentalness", "acousticness", "speechiness", "liveness", "loudness",
]


def _weighted_feature_avg(tracks_with_weights):
    """Compute weighted averages of audio features.

    tracks_with_weights: list of (track_dict, weight)
    Returns dict of field -> weighted average.
    """
    sums = {f: 0.0 for f in FEATURE_FIELDS}
    total_weight = {f: 0.0 for f in FEATURE_FIELDS}

    for track, weight in tracks_with_weights:
        for field in FEATURE_FIELDS:
            val = track.get(field)
            if val is not None:
                sums[field] += float(val) * weight
                total_weight[field] += weight

    avgs = {}
    for field in FEATURE_FIELDS:
        if total_weight[field] > 0:
            avgs[field] = round(sums[field] / total_weight[field], 4)
        else:
            avgs[field] = None
    return avgs


def _find_preferred_bpm(tracks_with_weights):
    """Find preferred BPM by rounding all tempos to nearest 2 and finding mode."""
    bpm_counts = Counter()
    all_bpms = []
    for track, weight in tracks_with_weights:
        bpm = track.get("bpm")
        if bpm and 60 < float(bpm) < 220:
            rounded = round(float(bpm) / 2) * 2
            bpm_counts[rounded] += weight
            all_bpms.append(float(bpm))

    if not bpm_counts:
        return None, None, None

    preferred = bpm_counts.most_common(1)[0][0]
    return preferred, round(min(all_bpms)), round(max(all_bpms))


def _find_preferred_keys(tracks_with_weights):
    """Find top 3 key+mode combinations."""
    key_counts = Counter()
    for track, weight in tracks_with_weights:
        k = track.get("key")
        mode = track.get("mode")
        if k is not None and mode is not None:
            key_name = KEY_NAMES[int(k)] if 0 <= int(k) < 12 else "?"
            mode_name = "major" if int(mode) == 1 else "minor"
            key_counts[f"{key_name} {mode_name}"] += weight

    top3 = key_counts.most_common(3)
    return ", ".join(f"{k}" for k, _ in top3) if top3 else None


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


def _derive_levels(avgs):
    """Derive qualitative levels from average features."""
    energy = avgs.get("energy")
    danceability = avgs.get("danceability")
    valence = avgs.get("valence")
    instrumentalness = avgs.get("instrumentalness")

    # Energy level
    if energy is not None:
        if energy > 0.75:
            energy_level = "high"
        elif energy > 0.5:
            energy_level = "medium-high"
        elif energy > 0.3:
            energy_level = "medium"
        else:
            energy_level = "low"
    else:
        energy_level = "unknown"

    # Danceability level
    if danceability is not None:
        if danceability > 0.75:
            danceability_level = "very danceable"
        elif danceability > 0.55:
            danceability_level = "danceable"
        elif danceability > 0.35:
            danceability_level = "moderate"
        else:
            danceability_level = "low"
    else:
        danceability_level = "unknown"

    # Mood from valence
    if valence is not None:
        if valence > 0.7:
            mood = "uplifting/euphoric"
        elif valence > 0.5:
            mood = "positive/groovy"
        elif valence > 0.3:
            mood = "neutral/moody"
        else:
            mood = "dark/melancholic"
    else:
        mood = "unknown"

    # Vocal preference from instrumentalness
    if instrumentalness is not None:
        if instrumentalness > 0.6:
            vocal_pref = "instrumental-leaning"
        elif instrumentalness > 0.3:
            vocal_pref = "balanced"
        else:
            vocal_pref = "vocal-heavy"
    else:
        vocal_pref = "unknown"

    return energy_level, danceability_level, mood, vocal_pref


def compute_taste_profile(user_id):
    """Compute the quantitative taste profile from all stored Spotify data.

    Weights: short_term x3, medium_term x2, long_term x1, saved x2, recent x1.5
    """
    log.info(f"Computing taste profile for user {user_id}")

    # Gather all tracks with weights
    tracks_weighted = []

    for time_range in ["short_term", "medium_term", "long_term"]:
        weight = WEIGHTS[time_range]
        tracks = get_user_top_tracks(user_id, time_range)
        for t in tracks:
            tracks_weighted.append((t, weight))

    saved = get_user_saved_tracks(user_id)
    for t in saved:
        tracks_weighted.append((t, WEIGHTS["saved"]))

    if not tracks_weighted:
        log.warning(f"No tracks with features for user {user_id}")
        return

    # Weighted averages
    avgs = _weighted_feature_avg(tracks_weighted)

    # Preferred BPM
    preferred_bpm, bpm_low, bpm_high = _find_preferred_bpm(tracks_weighted)

    # Preferred keys
    preferred_keys = _find_preferred_keys(tracks_weighted)

    # Genre analysis
    top_genres, evolving_taste = _analyze_genres(user_id)

    # Qualitative levels
    energy_level, danceability_level, mood, vocal_pref = _derive_levels(avgs)

    profile = {
        "avg_bpm": avgs.get("bpm"),
        "bpm_range_low": bpm_low,
        "bpm_range_high": bpm_high,
        "preferred_bpm": preferred_bpm,
        "preferred_keys": preferred_keys,
        "avg_energy": avgs.get("energy"),
        "avg_danceability": avgs.get("danceability"),
        "avg_valence": avgs.get("valence"),
        "avg_instrumentalness": avgs.get("instrumentalness"),
        "avg_acousticness": avgs.get("acousticness"),
        "avg_speechiness": avgs.get("speechiness"),
        "avg_liveness": avgs.get("liveness"),
        "avg_loudness": avgs.get("loudness"),
        "avg_tempo": avgs.get("bpm"),
        "mood": mood,
        "energy_level": energy_level,
        "vocal_preference": vocal_pref,
        "danceability_level": danceability_level,
        "top_genres": json.dumps(top_genres),
        "evolving_taste": evolving_taste,
        "research_status": "pending",
    }

    save_taste_profile(user_id, profile)
    log.info(f"Taste profile saved for user {user_id}: BPM={preferred_bpm}, mood={mood}, energy={energy_level}")
    return profile
