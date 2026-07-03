"""
Genre-to-attributes lookup table.
Maps Spotify genre strings to estimated production attributes.
Used to compute taste profiles now that Spotify has deprecated audio features.
"""

from collections import Counter

GENRE_ATTRIBUTES = {
    # Tech House
    "tech house": {"bpm_range": (124, 130), "energy": 0.75, "mood": "neutral", "vocal_density": "minimal", "key_tendency": "minor"},
    "minimal tech house": {"bpm_range": (124, 128), "energy": 0.65, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},
    "deep tech house": {"bpm_range": (122, 128), "energy": 0.65, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},

    # House variants
    "house": {"bpm_range": (120, 130), "energy": 0.70, "mood": "neutral", "vocal_density": "moderate", "key_tendency": "minor"},
    "deep house": {"bpm_range": (118, 125), "energy": 0.55, "mood": "dark", "vocal_density": "moderate", "key_tendency": "minor"},
    "progressive house": {"bpm_range": (126, 132), "energy": 0.75, "mood": "neutral", "vocal_density": "moderate", "key_tendency": "minor"},
    "melodic house": {"bpm_range": (120, 128), "energy": 0.65, "mood": "neutral", "vocal_density": "moderate", "key_tendency": "minor"},
    "afro house": {"bpm_range": (120, 126), "energy": 0.70, "mood": "bright", "vocal_density": "prominent", "key_tendency": "minor"},
    "acid house": {"bpm_range": (120, 130), "energy": 0.80, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},
    "funky house": {"bpm_range": (124, 130), "energy": 0.75, "mood": "bright", "vocal_density": "prominent", "key_tendency": "major"},
    "electro house": {"bpm_range": (126, 132), "energy": 0.85, "mood": "neutral", "vocal_density": "moderate", "key_tendency": "minor"},
    "latin house": {"bpm_range": (122, 128), "energy": 0.75, "mood": "bright", "vocal_density": "moderate", "key_tendency": "minor"},
    "chicago house": {"bpm_range": (120, 128), "energy": 0.70, "mood": "neutral", "vocal_density": "prominent", "key_tendency": "minor"},
    "jackin house": {"bpm_range": (124, 130), "energy": 0.80, "mood": "neutral", "vocal_density": "prominent", "key_tendency": "minor"},
    "organic house": {"bpm_range": (118, 124), "energy": 0.55, "mood": "neutral", "vocal_density": "minimal", "key_tendency": "minor"},
    "vocal house": {"bpm_range": (122, 128), "energy": 0.70, "mood": "bright", "vocal_density": "prominent", "key_tendency": "minor"},
    "piano house": {"bpm_range": (122, 128), "energy": 0.70, "mood": "bright", "vocal_density": "prominent", "key_tendency": "major"},
    "soulful house": {"bpm_range": (120, 126), "energy": 0.65, "mood": "bright", "vocal_density": "prominent", "key_tendency": "minor"},
    "tribal house": {"bpm_range": (124, 130), "energy": 0.80, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},
    "microhouse": {"bpm_range": (118, 126), "energy": 0.50, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},
    "filter house": {"bpm_range": (120, 128), "energy": 0.70, "mood": "neutral", "vocal_density": "moderate", "key_tendency": "minor"},

    # Bass House / UK Bass
    "bass house": {"bpm_range": (126, 132), "energy": 0.85, "mood": "dark", "vocal_density": "moderate", "key_tendency": "minor"},
    "uk bass": {"bpm_range": (128, 135), "energy": 0.85, "mood": "dark", "vocal_density": "moderate", "key_tendency": "minor"},
    "bassline": {"bpm_range": (130, 140), "energy": 0.85, "mood": "dark", "vocal_density": "moderate", "key_tendency": "minor"},
    "bassline house": {"bpm_range": (130, 138), "energy": 0.85, "mood": "dark", "vocal_density": "moderate", "key_tendency": "minor"},
    "uk bassline": {"bpm_range": (130, 140), "energy": 0.85, "mood": "dark", "vocal_density": "moderate", "key_tendency": "minor"},
    "uk garage": {"bpm_range": (130, 138), "energy": 0.75, "mood": "neutral", "vocal_density": "prominent", "key_tendency": "minor"},
    "speed garage": {"bpm_range": (130, 138), "energy": 0.80, "mood": "dark", "vocal_density": "moderate", "key_tendency": "minor"},

    # Techno
    "techno": {"bpm_range": (128, 140), "energy": 0.80, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},
    "minimal techno": {"bpm_range": (126, 135), "energy": 0.65, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},
    "melodic techno": {"bpm_range": (124, 132), "energy": 0.75, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},
    "hard techno": {"bpm_range": (140, 155), "energy": 0.95, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},
    "industrial techno": {"bpm_range": (135, 150), "energy": 0.90, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},
    "dub techno": {"bpm_range": (120, 130), "energy": 0.55, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},
    "detroit techno": {"bpm_range": (128, 140), "energy": 0.80, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},
    "peak time techno": {"bpm_range": (132, 145), "energy": 0.90, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},
    "hypnotic techno": {"bpm_range": (130, 140), "energy": 0.75, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},
    "raw techno": {"bpm_range": (135, 148), "energy": 0.90, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},
    "acid techno": {"bpm_range": (130, 145), "energy": 0.85, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},

    # Minimal / Deep
    "minimal": {"bpm_range": (120, 132), "energy": 0.55, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},
    "minimal deep tech": {"bpm_range": (122, 128), "energy": 0.55, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},

    # Trance
    "trance": {"bpm_range": (136, 150), "energy": 0.85, "mood": "bright", "vocal_density": "moderate", "key_tendency": "minor"},
    "psytrance": {"bpm_range": (140, 150), "energy": 0.90, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},
    "progressive trance": {"bpm_range": (130, 138), "energy": 0.75, "mood": "neutral", "vocal_density": "moderate", "key_tendency": "minor"},
    "uplifting trance": {"bpm_range": (136, 142), "energy": 0.90, "mood": "bright", "vocal_density": "moderate", "key_tendency": "minor"},

    # D&B / Breaks
    "drum and bass": {"bpm_range": (170, 180), "energy": 0.90, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},
    "liquid dnb": {"bpm_range": (170, 178), "energy": 0.70, "mood": "neutral", "vocal_density": "moderate", "key_tendency": "minor"},
    "jungle": {"bpm_range": (160, 175), "energy": 0.85, "mood": "dark", "vocal_density": "moderate", "key_tendency": "minor"},
    "breakbeat": {"bpm_range": (120, 140), "energy": 0.80, "mood": "neutral", "vocal_density": "moderate", "key_tendency": "minor"},

    # Dubstep / Bass Music
    "dubstep": {"bpm_range": (138, 142), "energy": 0.90, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},
    "riddim": {"bpm_range": (140, 150), "energy": 0.95, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},
    "future bass": {"bpm_range": (140, 160), "energy": 0.80, "mood": "bright", "vocal_density": "moderate", "key_tendency": "major"},
    "trap": {"bpm_range": (130, 170), "energy": 0.85, "mood": "dark", "vocal_density": "moderate", "key_tendency": "minor"},
    "wave": {"bpm_range": (140, 160), "energy": 0.60, "mood": "dark", "vocal_density": "moderate", "key_tendency": "minor"},

    # Disco / Nu-Disco
    "disco": {"bpm_range": (110, 130), "energy": 0.80, "mood": "bright", "vocal_density": "prominent", "key_tendency": "major"},
    "nu disco": {"bpm_range": (115, 128), "energy": 0.75, "mood": "bright", "vocal_density": "prominent", "key_tendency": "major"},
    "disco house": {"bpm_range": (118, 126), "energy": 0.75, "mood": "bright", "vocal_density": "prominent", "key_tendency": "major"},
    "italo disco": {"bpm_range": (115, 130), "energy": 0.75, "mood": "bright", "vocal_density": "prominent", "key_tendency": "minor"},
    "cosmic disco": {"bpm_range": (110, 125), "energy": 0.65, "mood": "neutral", "vocal_density": "moderate", "key_tendency": "minor"},

    # Downtempo / Chill
    "downtempo": {"bpm_range": (80, 115), "energy": 0.40, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},
    "chillout": {"bpm_range": (85, 110), "energy": 0.35, "mood": "neutral", "vocal_density": "moderate", "key_tendency": "minor"},
    "ambient": {"bpm_range": (60, 100), "energy": 0.20, "mood": "dark", "vocal_density": "minimal", "key_tendency": "minor"},
    "lo-fi house": {"bpm_range": (115, 125), "energy": 0.55, "mood": "neutral", "vocal_density": "minimal", "key_tendency": "minor"},

    # EDM / Mainstage
    "edm": {"bpm_range": (126, 132), "energy": 0.90, "mood": "bright", "vocal_density": "prominent", "key_tendency": "minor"},
    "big room": {"bpm_range": (126, 132), "energy": 0.95, "mood": "bright", "vocal_density": "moderate", "key_tendency": "minor"},
    "future house": {"bpm_range": (124, 130), "energy": 0.80, "mood": "neutral", "vocal_density": "moderate", "key_tendency": "minor"},
    "slap house": {"bpm_range": (124, 128), "energy": 0.80, "mood": "neutral", "vocal_density": "moderate", "key_tendency": "minor"},

    # Catch-all electronic
    "electronic": {"bpm_range": (120, 130), "energy": 0.65, "mood": "neutral", "vocal_density": "moderate", "key_tendency": "minor"},
    "electronica": {"bpm_range": (110, 130), "energy": 0.60, "mood": "neutral", "vocal_density": "moderate", "key_tendency": "minor"},

    # Non-electronic (for users with mixed libraries)
    "hip hop": {"bpm_range": (80, 115), "energy": 0.70, "mood": "dark", "vocal_density": "prominent", "key_tendency": "minor"},
    "rap": {"bpm_range": (80, 115), "energy": 0.75, "mood": "dark", "vocal_density": "prominent", "key_tendency": "minor"},
    "r&b": {"bpm_range": (70, 110), "energy": 0.55, "mood": "neutral", "vocal_density": "prominent", "key_tendency": "minor"},
    "pop": {"bpm_range": (100, 130), "energy": 0.70, "mood": "bright", "vocal_density": "prominent", "key_tendency": "major"},
    "rock": {"bpm_range": (100, 140), "energy": 0.80, "mood": "neutral", "vocal_density": "prominent", "key_tendency": "minor"},
    "indie": {"bpm_range": (100, 135), "energy": 0.60, "mood": "neutral", "vocal_density": "prominent", "key_tendency": "minor"},
    "reggaeton": {"bpm_range": (88, 100), "energy": 0.80, "mood": "bright", "vocal_density": "prominent", "key_tendency": "minor"},
    "latin": {"bpm_range": (90, 130), "energy": 0.75, "mood": "bright", "vocal_density": "prominent", "key_tendency": "minor"},
}

# Fallback for unknown genres
DEFAULT_ATTRIBUTES = {"bpm_range": (120, 130), "energy": 0.65, "mood": "neutral", "vocal_density": "moderate", "key_tendency": "minor"}


def get_genre_attributes(genre_string):
    """Look up attributes for a Spotify genre string. Case-insensitive, tries partial matches."""
    genre_lower = genre_string.lower().strip()

    # Exact match
    if genre_lower in GENRE_ATTRIBUTES:
        return GENRE_ATTRIBUTES[genre_lower]

    # Partial match — check if any known genre is contained in the string
    for known_genre, attrs in GENRE_ATTRIBUTES.items():
        if known_genre in genre_lower or genre_lower in known_genre:
            return attrs

    return DEFAULT_ATTRIBUTES


def compute_taste_from_genres(genre_list):
    """
    Given a list of Spotify genre strings (from user's top artists),
    compute aggregated taste profile attributes.

    Returns dict with: avg_bpm, bpm_range, energy, mood, vocal_density, key_tendency, top_genres
    """
    if not genre_list:
        return {
            "avg_bpm": 128,
            "bpm_range": (120, 135),
            "energy": "medium",
            "energy_raw": 0.65,
            "mood": "neutral",
            "vocal_density": "moderate",
            "key_tendency": "minor",
            "top_genres": [],
            "genre_count": 0,
        }

    bpm_lows = []
    bpm_highs = []
    energies = []
    moods = {"dark": 0, "neutral": 0, "bright": 0}
    vocals = {"minimal": 0, "moderate": 0, "prominent": 0}
    keys = {"minor": 0, "major": 0}

    for genre in genre_list:
        attrs = get_genre_attributes(genre)
        bpm_lows.append(attrs["bpm_range"][0])
        bpm_highs.append(attrs["bpm_range"][1])
        energies.append(attrs["energy"])
        moods[attrs["mood"]] += 1
        vocals[attrs["vocal_density"]] += 1
        keys[attrs["key_tendency"]] += 1

    avg_bpm_low = sum(bpm_lows) / len(bpm_lows)
    avg_bpm_high = sum(bpm_highs) / len(bpm_highs)
    avg_bpm = round((avg_bpm_low + avg_bpm_high) / 2)
    avg_energy = sum(energies) / len(energies)

    # Determine dominant mood, vocal density, key
    dominant_mood = max(moods, key=moods.get)
    dominant_vocal = max(vocals, key=vocals.get)
    dominant_key = max(keys, key=keys.get)

    # Energy level label
    if avg_energy >= 0.80:
        energy_label = "high"
    elif avg_energy >= 0.60:
        energy_label = "medium-high"
    elif avg_energy >= 0.40:
        energy_label = "medium"
    else:
        energy_label = "low"

    # Count genre occurrences for top genres
    genre_counts = Counter(genre_list)
    top_genres = [g for g, _ in genre_counts.most_common(8)]

    return {
        "avg_bpm": avg_bpm,
        "bpm_range": (round(avg_bpm_low), round(avg_bpm_high)),
        "energy": energy_label,
        "energy_raw": round(avg_energy, 2),
        "mood": dominant_mood,
        "vocal_density": dominant_vocal,
        "key_tendency": dominant_key,
        "top_genres": top_genres,
        "genre_count": len(genre_list),
    }


# ── Weighted multi-source computation ──────────────────────────

# Data source weights — higher = stronger taste signal
SOURCE_WEIGHTS = {
    "top_artists": 5,       # Algorithmic, listening-based — strongest
    "top_tracks": 4,        # Artist genres from most-played tracks
    "followed_artists": 3,  # Intentional curation
    "saved_tracks": 2,      # Intentional saves
    "recent_plays": 1,      # Small sample, current behavior
}


def compute_weighted_taste(genre_sources, excluded_sources=None):
    """Compute a taste profile from multiple genre sources with priority weighting.

    Args:
        genre_sources: dict mapping source name to list of genre strings.
        excluded_sources: list of source names to skip.

    Returns:
        Same format as compute_taste_from_genres, plus sources_used,
        total_weighted_genres, and excluded_sources.
    """
    if excluded_sources is None:
        excluded_sources = []

    weighted_genres = []
    sources_used = []

    for source, genres in genre_sources.items():
        if source in excluded_sources or not genres:
            continue

        weight = SOURCE_WEIGHTS.get(source, 1)
        weighted_genres.extend([g for g in genres for _ in range(weight)])

        sources_used.append({
            "source": source,
            "genre_count": len(genres),
            "weight": weight,
            "effective_count": len(genres) * weight,
        })

    if not weighted_genres:
        result = compute_taste_from_genres([])
        result["sources_used"] = []
        result["total_weighted_genres"] = 0
        result["excluded_sources"] = excluded_sources
        return result

    result = compute_taste_from_genres(weighted_genres)
    result["sources_used"] = sources_used
    result["total_weighted_genres"] = len(weighted_genres)
    result["excluded_sources"] = excluded_sources
    return result
