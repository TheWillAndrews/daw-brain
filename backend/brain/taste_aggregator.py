"""
Taste profile aggregation engine — computes a weighted aggregate taste profile
from structured artist research profiles.

Aggregation rules:
- Floats (0-1): Weighted average, weight = 1/rank. Nulls skipped.
- Enums: Weighted mode. Each value gets a vote weighted by 1/rank.
- Integer ranges (BPM): Weighted average of primary, min/max for range envelope.
- Arrays: Frequency count weighted by 1/rank. Top N items surface.
- Strings (narrative): Not aggregated — individual narratives used for "style of" generation.
"""

import json
import logging
from collections import Counter
from datetime import datetime

from brain.database import (
    get_artist_profiles_for_aggregation,
    save_aggregated_taste_profile,
    update_research_status,
)

log = logging.getLogger("daw-brain")


# ─── Aggregation Primitives ──────────────────────────────────────────


def _weighted_avg(values_with_ranks):
    """Compute weighted average where weight = 1/rank. Skip None values."""
    numerator = 0.0
    denominator = 0.0
    for rank, value in values_with_ranks:
        if value is not None:
            w = 1.0 / rank
            numerator += value * w
            denominator += w
    if denominator == 0:
        return None
    return round(numerator / denominator, 3)


def _weighted_mode(values_with_ranks, top_n=1):
    """Compute weighted mode — enum value with highest total weight.

    Returns single value if top_n=1, else list of top N values.
    """
    votes = Counter()
    for rank, value in values_with_ranks:
        if value is not None:
            votes[value] += 1.0 / rank
    if not votes:
        return None if top_n == 1 else []
    if top_n == 1:
        return votes.most_common(1)[0][0]
    return [v for v, _ in votes.most_common(top_n)]


def _weighted_frequency(arrays_with_ranks, top_n=10):
    """Aggregate arrays by weighted frequency. Returns top N items."""
    counts = Counter()
    for rank, arr in arrays_with_ranks:
        if arr and isinstance(arr, list):
            for item in arr:
                if item is not None:
                    counts[item] += 1.0 / rank
    return [item for item, _ in counts.most_common(top_n)]


def _int_range_aggregate(lows_with_ranks, highs_with_ranks, primaries_with_ranks):
    """Aggregate integer ranges: weighted avg of primary, min of lows, max of highs."""
    primary = _weighted_avg(primaries_with_ranks)

    low_vals = [v for _, v in lows_with_ranks if v is not None]
    high_vals = [v for _, v in highs_with_ranks if v is not None]

    low = min(low_vals) if low_vals else None
    high = max(high_vals) if high_vals else None

    return primary, low, high


# ─── Field Extraction Helpers ─────────────────────────────────────────


def _extract_float(profiles, section, field):
    """Extract (rank, float_value) pairs from profiles."""
    return [
        (rank, profile.get(section, {}).get(field))
        for rank, profile in profiles
    ]


def _extract_enum(profiles, section, field):
    """Extract (rank, enum_value) pairs from profiles."""
    return [
        (rank, profile.get(section, {}).get(field))
        for rank, profile in profiles
    ]


def _extract_array(profiles, section, field):
    """Extract (rank, array_value) pairs from profiles."""
    return [
        (rank, profile.get(section, {}).get(field, []))
        for rank, profile in profiles
    ]


def _extract_int(profiles, section, field):
    """Extract (rank, int_value) pairs from profiles."""
    return [
        (rank, profile.get(section, {}).get(field))
        for rank, profile in profiles
    ]


# ─── Null Coverage Computation ────────────────────────────────────────


def _compute_null_coverage(profiles):
    """Compute percentage of non-null values per section across all profiles."""
    sections = [
        "classification", "tempo_and_rhythm", "drums", "bass",
        "harmony_and_melody", "sound_design", "vocals", "arrangement",
        "mix_and_production", "energy_and_mood", "context_and_influence",
    ]
    coverage = {}
    for section in sections:
        total_fields = 0
        non_null = 0
        for _, profile in profiles:
            sect_data = profile.get(section, {})
            for key, val in sect_data.items():
                total_fields += 1
                if val is not None and val != [] and val != "":
                    non_null += 1
        if total_fields > 0:
            coverage[section] = round(non_null / total_fields, 2)
        else:
            coverage[section] = 0.0
    return coverage


# ─── Main Aggregation ────────────────────────────────────────────────


def compute_aggregated_taste_profile(user_id):
    """Compute the full aggregated taste profile from a user's top artists.

    Returns the aggregated profile dict, or None if insufficient data.
    """
    profiles = get_artist_profiles_for_aggregation(user_id)
    if not profiles:
        log.warning(f"No artist profiles available for aggregation (user {user_id})")
        return None

    log.info(f"Aggregating taste profile from {len(profiles)} artist profiles")

    # ── Tempo ─────────────────────────────────────────────────
    bpm_primary, bpm_low, bpm_high = _int_range_aggregate(
        _extract_int(profiles, "tempo_and_rhythm", "bpm_low"),
        _extract_int(profiles, "tempo_and_rhythm", "bpm_high"),
        _extract_int(profiles, "tempo_and_rhythm", "bpm_primary"),
    )

    # ── Genre ─────────────────────────────────────────────────
    primary_genres = _extract_enum(profiles, "classification", "primary_genre")
    primary_genre = _weighted_mode(primary_genres)
    secondary_genres = _weighted_frequency(
        _extract_array(profiles, "classification", "secondary_genres"), top_n=4
    )
    all_genre_tags = _weighted_frequency(
        _extract_array(profiles, "classification", "genre_tags"), top_n=20
    )

    # ── Sound Palette ─────────────────────────────────────────
    bass_character = _weighted_mode(_extract_enum(profiles, "bass", "bass_character"))
    drum_aesthetic = _weighted_mode(
        _extract_enum(profiles, "drums", "drum_machine_aesthetic")
    )
    common_instruments = _weighted_frequency(
        _extract_array(profiles, "harmony_and_melody", "melodic_instruments"), top_n=10
    )
    synth_methods = _weighted_frequency(
        _extract_array(profiles, "sound_design", "synthesis_methods"), top_n=5
    )
    texture_density = _weighted_mode(
        _extract_enum(profiles, "sound_design", "texture_density")
    )
    vocal_preference = _weighted_mode(
        _extract_enum(profiles, "vocals", "vocal_presence")
    )

    # ── Drums Detail ──────────────────────────────────────────
    kick_pattern = _weighted_mode(_extract_enum(profiles, "drums", "kick_pattern"))
    kick_character = _weighted_mode(_extract_enum(profiles, "drums", "kick_character"))
    percussion_layers = _weighted_mode(
        _extract_enum(profiles, "drums", "percussion_layers")
    )
    common_percussion = _weighted_frequency(
        _extract_array(profiles, "drums", "percussion_elements"), top_n=8
    )
    hihat_complexity = _weighted_avg(
        _extract_float(profiles, "drums", "hihat_pattern_complexity")
    )

    # ── Bass Detail ───────────────────────────────────────────
    bass_movement = _weighted_mode(_extract_enum(profiles, "bass", "bass_movement"))
    bass_sidechain = _weighted_mode(
        _extract_enum(profiles, "bass", "bass_sidechain_style")
    )
    bass_synth_method = _weighted_mode(
        _extract_enum(profiles, "bass", "bass_synthesis_method")
    )

    # ── Harmony ───────────────────────────────────────────────
    key_preference = _weighted_mode(
        _extract_enum(profiles, "harmony_and_melody", "key_preference")
    )
    chord_complexity = _weighted_mode(
        _extract_enum(profiles, "harmony_and_melody", "chord_complexity")
    )
    melodic_presence = _weighted_mode(
        _extract_enum(profiles, "harmony_and_melody", "melodic_presence")
    )

    # ── Arrangement ───────────────────────────────────────────
    structure_style = _weighted_mode(
        _extract_enum(profiles, "arrangement", "arrangement_style")
    )
    build_intensity = _weighted_avg(
        _extract_float(profiles, "arrangement", "build_intensity")
    )
    drop_impact = _weighted_avg(
        _extract_float(profiles, "arrangement", "drop_impact")
    )
    variation_level = _weighted_avg(
        _extract_float(profiles, "arrangement", "arrangement_variation")
    )
    preferred_transitions = _weighted_frequency(
        _extract_array(profiles, "arrangement", "transition_techniques"), top_n=5
    )

    # ── Mix Character ─────────────────────────────────────────
    mix_aesthetic = _weighted_mode(
        _extract_enum(profiles, "mix_and_production", "mix_aesthetic")
    )
    frequency_emphasis = _weighted_mode(
        _extract_enum(profiles, "mix_and_production", "frequency_emphasis")
    )
    sidechain_style = _weighted_mode(
        _extract_enum(profiles, "mix_and_production", "sidechain_prominence")
    )
    dynamic_range = _weighted_mode(
        _extract_enum(profiles, "mix_and_production", "dynamic_range")
    )

    # ── Mood & Energy ─────────────────────────────────────────
    energy = _weighted_avg(_extract_float(profiles, "energy_and_mood", "energy_level"))
    danceability = _weighted_avg(
        _extract_float(profiles, "energy_and_mood", "danceability")
    )
    darkness_brightness = _weighted_avg(
        _extract_float(profiles, "energy_and_mood", "darkness_brightness")
    )
    primary_mood = _weighted_mode(
        _extract_enum(profiles, "energy_and_mood", "mood_primary")
    )
    atmosphere = _weighted_mode(
        _extract_enum(profiles, "energy_and_mood", "atmosphere")
    )
    time_of_night = _weighted_mode(
        _extract_enum(profiles, "energy_and_mood", "time_of_night")
    )
    hypnotic_quality = _weighted_avg(
        _extract_float(profiles, "energy_and_mood", "hypnotic_quality")
    )
    aggression = _weighted_avg(
        _extract_float(profiles, "energy_and_mood", "aggression")
    )

    # ── Artist Summary ────────────────────────────────────────
    top_artist_names = [
        p.get("identity", {}).get("artist_name", "Unknown")
        for _, p in profiles[:10]
    ]
    underground_count = sum(
        1 for _, p in profiles
        if p.get("classification", {}).get("scene_positioning")
        in ("underground", "emerging")
    )
    underground_ratio = round(underground_count / len(profiles), 2) if profiles else 0

    unique_genres = set()
    for _, p in profiles:
        tags = p.get("classification", {}).get("genre_tags", [])
        unique_genres.update(tags)
    genre_diversity = min(1.0, round(len(unique_genres) / max(len(profiles) * 3, 1), 2))

    # ── Rhythm Detail ─────────────────────────────────────────
    groove_tendency = _weighted_mode(
        _extract_enum(profiles, "tempo_and_rhythm", "groove_type")
    )
    swing_tendency = _weighted_mode(
        _extract_enum(profiles, "tempo_and_rhythm", "swing_amount")
    )
    rhythmic_complexity = _weighted_avg(
        _extract_float(profiles, "tempo_and_rhythm", "rhythmic_complexity")
    )

    # ── Build Aggregated Profile ──────────────────────────────

    aggregated = {
        "user_id": user_id,
        "computed_at": datetime.utcnow().isoformat(),
        "artist_count": len(profiles),
        "null_coverage": _compute_null_coverage(profiles),

        "tempo": {
            "center_bpm": round(bpm_primary) if bpm_primary else None,
            "bpm_range": [round(bpm_low) if bpm_low else None,
                          round(bpm_high) if bpm_high else None],
            "groove_tendency": groove_tendency,
            "swing_tendency": swing_tendency,
            "rhythmic_complexity": rhythmic_complexity,
        },

        "genre": {
            "primary": primary_genre,
            "secondary": secondary_genres,
            "all_tags": all_genre_tags,
        },

        "sound_palette": {
            "bass_character": bass_character,
            "bass_movement": bass_movement,
            "bass_sidechain": bass_sidechain,
            "bass_synth_method": bass_synth_method,
            "drum_aesthetic": drum_aesthetic,
            "kick_pattern": kick_pattern,
            "kick_character": kick_character,
            "percussion_layers": percussion_layers,
            "common_percussion": common_percussion,
            "hihat_complexity": hihat_complexity,
            "common_instruments": common_instruments,
            "synthesis_methods": synth_methods,
            "texture_density": texture_density,
            "vocal_preference": vocal_preference,
        },

        "harmony": {
            "key_preference": key_preference,
            "chord_complexity": chord_complexity,
            "melodic_presence": melodic_presence,
        },

        "arrangement": {
            "structure_style": structure_style,
            "build_intensity": build_intensity,
            "drop_impact": drop_impact,
            "variation_level": variation_level,
            "preferred_transitions": preferred_transitions,
        },

        "mix_character": {
            "aesthetic": mix_aesthetic,
            "frequency_emphasis": frequency_emphasis,
            "sidechain_style": sidechain_style,
            "dynamic_range": dynamic_range,
        },

        "mood_and_energy": {
            "energy": energy,
            "danceability": danceability,
            "darkness_brightness": darkness_brightness,
            "primary_mood": primary_mood,
            "atmosphere": atmosphere,
            "time_of_night": time_of_night,
            "hypnotic_quality": hypnotic_quality,
            "aggression": aggression,
        },

        "artist_summary": {
            "top_artists": top_artist_names,
            "underground_ratio": underground_ratio,
            "genre_diversity_score": genre_diversity,
        },
    }

    # Save to database
    save_aggregated_taste_profile(user_id, aggregated)
    log.info(
        f"Aggregated taste profile computed for user {user_id}: "
        f"{len(profiles)} artists, center BPM={aggregated['tempo']['center_bpm']}, "
        f"primary genre={primary_genre}, mood={primary_mood}"
    )

    return aggregated
