"""
SoundCloud taste profile computation — builds a listener profile from
SoundCloud data using genre, tag, and activity analysis.
"""

import json
import logging
from collections import Counter

from brain.database import (
    get_soundcloud_likes, get_soundcloud_followings,
    get_soundcloud_reposts, get_soundcloud_playlists,
    get_soundcloud_user_tracks,
    save_soundcloud_taste_profile,
    update_soundcloud_research_status,
)

log = logging.getLogger("daw-brain")

# Genre-to-BPM lookup for inference when no BPM metadata is available
GENRE_BPM_MAP = {
    "tech house": 124, "house": 124, "deep house": 122, "minimal": 126,
    "techno": 130, "progressive house": 126, "electro": 128,
    "drum and bass": 174, "dnb": 174, "jungle": 170,
    "dubstep": 140, "trap": 140, "hip hop": 90, "hip-hop": 90,
    "ambient": 100, "downtempo": 100, "lo-fi": 85, "lofi": 85,
    "trance": 138, "psytrance": 145, "hard techno": 140,
    "garage": 130, "uk garage": 130, "breakbeat": 130,
    "disco": 120, "funk": 110, "afro house": 122,
    "melodic techno": 124, "acid": 130, "industrial": 135,
}

# Tags that indicate mood/energy/vocal character
MOOD_TAGS = {
    "dark": "dark", "deep": "dark", "melancholic": "dark", "noir": "dark",
    "sinister": "dark", "ominous": "dark",
    "bright": "uplifting", "euphoric": "uplifting", "uplifting": "uplifting",
    "happy": "uplifting", "sunshine": "uplifting",
    "groovy": "positive/groovy", "funky": "positive/groovy",
    "chill": "neutral", "mellow": "neutral", "smooth": "neutral",
    "melodic": "melodic", "emotional": "melodic",
    "acid": "hypnotic", "hypnotic": "hypnotic", "trippy": "hypnotic",
    "driving": "high-energy", "banging": "high-energy", "peak time": "high-energy",
    "peak": "high-energy", "hard": "high-energy",
}

ENERGY_TAGS = {
    "chill": "low", "ambient": "low", "downtempo": "low", "mellow": "low",
    "smooth": "medium", "groovy": "medium", "deep": "medium",
    "driving": "high", "banging": "high", "peak": "high", "hard": "high",
    "energetic": "high", "rave": "high", "festival": "high",
}

VOCAL_TAGS = {
    "vocal": "vocal-heavy", "vocals": "vocal-heavy", "singer": "vocal-heavy",
    "acapella": "vocal-heavy", "spoken word": "vocal-heavy",
    "instrumental": "instrumental-leaning", "no vocals": "instrumental-leaning",
    "dub": "balanced",
}


def _extract_tags(tag_list_str):
    """Split a SoundCloud tag_list string into individual tags."""
    if not tag_list_str:
        return []
    # SoundCloud tag_list can be space-separated with quoted multi-word tags
    tags = []
    in_quotes = False
    current = []
    for char in tag_list_str:
        if char == '"':
            in_quotes = not in_quotes
        elif char == ' ' and not in_quotes:
            if current:
                tags.append("".join(current).strip().lower())
                current = []
        else:
            current.append(char)
    if current:
        tags.append("".join(current).strip().lower())
    return [t for t in tags if t]


def _compute_underground_score(likes, followings):
    """Compute underground score (0-10) based on play counts and follower counts.

    Mostly <1k followers artists = 8-10
    Mix of small and large = 4-7
    Mostly >100k followers = 1-3
    """
    # From likes: look at playback_count distribution
    play_counts = [l.get("playback_count") or 0 for l in likes if l.get("playback_count")]
    under_1k = sum(1 for p in play_counts if p < 1000)
    under_10k = sum(1 for p in play_counts if p < 10000)
    under_100k = sum(1 for p in play_counts if p < 100000)
    total_tracks = len(play_counts) if play_counts else 1

    track_score = (under_1k / total_tracks * 4 +
                   under_10k / total_tracks * 3 +
                   under_100k / total_tracks * 2) if total_tracks > 0 else 5

    # From followings: look at followers_count distribution
    follower_counts = [f.get("followers_count") or 0 for f in followings
                       if f.get("followers_count") is not None]
    f_under_1k = sum(1 for f in follower_counts if f < 1000)
    f_under_10k = sum(1 for f in follower_counts if f < 10000)
    total_follows = len(follower_counts) if follower_counts else 1

    follow_score = (f_under_1k / total_follows * 5 +
                    f_under_10k / total_follows * 3) if total_follows > 0 else 5

    # Blend: weight followings slightly more (active choice)
    raw = track_score * 0.4 + follow_score * 0.6
    return round(min(10, max(0, raw)), 1)


def compute_soundcloud_taste_profile(user_id):
    """Compute taste profile from all stored SoundCloud data.

    Weights: reposts x3, user_tracks x3, likes x2, playlists x1.
    """
    log.info(f"Computing SoundCloud taste profile for user {user_id}")

    likes = get_soundcloud_likes(user_id)
    followings = get_soundcloud_followings(user_id)
    reposts = get_soundcloud_reposts(user_id)
    playlists = get_soundcloud_playlists(user_id)
    user_tracks = get_soundcloud_user_tracks(user_id)

    # ── Genre Analysis ────────────────────────────────────────
    genre_counts = Counter()
    tag_counts = Counter()

    # Reposts x3 (public endorsement)
    for r in reposts:
        g = (r.get("genre") or "").strip().lower()
        if g:
            genre_counts[g] += 3
        for tag in _extract_tags(r.get("tag_list", "")):
            tag_counts[tag] += 3

    # User's own tracks x3 (what they actually produce)
    for t in user_tracks:
        g = (t.get("genre") or "").strip().lower()
        if g:
            genre_counts[g] += 3
        for tag in _extract_tags(t.get("tag_list", "")):
            tag_counts[tag] += 3

    # Likes x2
    for l in likes:
        g = (l.get("genre") or "").strip().lower()
        if g:
            genre_counts[g] += 2
        for tag in _extract_tags(l.get("tag_list", "")):
            tag_counts[tag] += 2

    # Playlists x1
    for p in playlists:
        g = (p.get("genre") or "").strip().lower()
        if g:
            genre_counts[g] += 1
        for tag in _extract_tags(p.get("tag_list", "")):
            tag_counts[tag] += 1

    top_genres = [g for g, _ in genre_counts.most_common(15)]
    top_tags = [t for t, _ in tag_counts.most_common(20)]

    # ── Top Artists ───────────────────────────────────────────
    artist_counts = Counter()
    for l in likes:
        name = l.get("artist_name", "").strip()
        if name and name != "Unknown":
            artist_counts[name] += 2
    for r in reposts:
        name = r.get("artist_name", "").strip()
        if name and name != "Unknown":
            artist_counts[name] += 3
    # Followings by order (first followed = higher rank)
    for i, f in enumerate(followings):
        name = f.get("artist_name", "").strip()
        if name and name != "Unknown":
            artist_counts[name] += max(1, 5 - i // 20)

    top_artists = [a for a, _ in artist_counts.most_common(15)]

    # ── Underground Score ─────────────────────────────────────
    underground_score = _compute_underground_score(likes, followings)

    # ── BPM Estimation ────────────────────────────────────────
    bpm_values = []

    # Strongest signal: user's own tracks with BPM metadata
    for t in user_tracks:
        bpm = t.get("bpm")
        if bpm and 60 < float(bpm) < 220:
            bpm_values.extend([float(bpm)] * 3)  # weight x3

    # Liked tracks with BPM
    for l in likes:
        bpm = l.get("bpm")
        if bpm and 60 < float(bpm) < 220:
            bpm_values.append(float(bpm))

    # If not enough BPM data, infer from top genres
    if len(bpm_values) < 5:
        for genre in top_genres[:5]:
            for key, bpm in GENRE_BPM_MAP.items():
                if key in genre:
                    bpm_values.append(float(bpm))
                    break

    avg_bpm = round(sum(bpm_values) / len(bpm_values), 1) if bpm_values else None

    # ── Key Signatures ────────────────────────────────────────
    key_counts = Counter()
    for t in user_tracks:
        k = (t.get("key_signature") or "").strip()
        if k:
            key_counts[k] += 3
    preferred_keys = [k for k, _ in key_counts.most_common(3)] if key_counts else []

    # ── Mood / Energy / Vocal Preference (from tags) ──────────
    mood_votes = Counter()
    energy_votes = Counter()
    vocal_votes = Counter()

    all_tags = top_tags + [g for g in top_genres]
    for tag in all_tags:
        for keyword, mood in MOOD_TAGS.items():
            if keyword in tag:
                mood_votes[mood] += 1
        for keyword, energy in ENERGY_TAGS.items():
            if keyword in tag:
                energy_votes[energy] += 1
        for keyword, vocal in VOCAL_TAGS.items():
            if keyword in tag:
                vocal_votes[vocal] += 1

    mood = mood_votes.most_common(1)[0][0] if mood_votes else "neutral"
    energy_level = energy_votes.most_common(1)[0][0] if energy_votes else "medium"
    vocal_preference = vocal_votes.most_common(1)[0][0] if vocal_votes else "balanced"

    # ── Taste Evolution ───────────────────────────────────────
    evolving_taste = ""
    if likes:
        # Compare recent likes vs older likes by genre
        sorted_likes = sorted(likes, key=lambda x: x.get("liked_at", ""), reverse=True)
        mid = len(sorted_likes) // 2
        if mid > 5:
            recent_genres = Counter()
            older_genres = Counter()
            for l in sorted_likes[:mid]:
                g = (l.get("genre") or "").strip().lower()
                if g:
                    recent_genres[g] += 1
            for l in sorted_likes[mid:]:
                g = (l.get("genre") or "").strip().lower()
                if g:
                    older_genres[g] += 1

            recent_top = set(g for g, _ in recent_genres.most_common(5))
            older_top = set(g for g, _ in older_genres.most_common(5))
            new_genres = recent_top - older_top
            dropped = older_top - recent_top

            if new_genres and dropped:
                evolving_taste = f"Shifting from {', '.join(list(dropped)[:3])} toward {', '.join(list(new_genres)[:3])}"
            elif new_genres:
                evolving_taste = f"Recently exploring: {', '.join(list(new_genres)[:3])}"
            elif dropped:
                evolving_taste = f"Consistent taste, less: {', '.join(list(dropped)[:3])}"
            else:
                evolving_taste = "Consistent taste across recent activity"

    # ── Save Profile ──────────────────────────────────────────
    profile = {
        "top_genres": json.dumps(top_genres),
        "top_tags": json.dumps(top_tags),
        "top_artists": json.dumps(top_artists),
        "underground_score": underground_score,
        "avg_bpm": avg_bpm,
        "preferred_keys": json.dumps(preferred_keys),
        "mood": mood,
        "energy_level": energy_level,
        "vocal_preference": vocal_preference,
        "research_status": "pending",
        "evolving_taste": evolving_taste,
        "raw_data": json.dumps({
            "genre_counts": dict(genre_counts.most_common(30)),
            "tag_counts": dict(tag_counts.most_common(40)),
            "artist_counts": dict(artist_counts.most_common(20)),
            "likes_count": len(likes),
            "followings_count": len(followings),
            "reposts_count": len(reposts),
            "user_tracks_count": len(user_tracks),
        }),
    }

    save_soundcloud_taste_profile(user_id, profile)
    log.info(f"SoundCloud taste profile saved for user {user_id}: "
             f"BPM={avg_bpm}, underground={underground_score}, mood={mood}")
    return profile
