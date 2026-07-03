"""
AI artist production research — uses Claude to generate structured JSON profiles
following the DAW Brain Artist Profile Schema v1.0.0.

Each artist gets a comprehensive production profile with ~100+ structured fields
covering tempo, drums, bass, harmony, sound design, vocals, arrangement, mix,
energy/mood, and context. Profiles are stored as JSON blobs and used for taste
profile aggregation.

Runs in a background thread.
"""

import json
import time
import uuid
import logging
import threading
from datetime import datetime

import anthropic

from brain.database import (
    get_user_top_artists, get_artist_research, save_artist_research,
    get_unresearched_artists, get_stale_artist_research,
    update_research_status, save_production_dna,
)

log = logging.getLogger("daw-brain")

MODEL = "claude-sonnet-4-20250514"
SCHEMA_VERSION = "1.0.0"

# ─── Artist Profile Schema (injected into research prompt) ─────────────

PROFILE_SCHEMA = """{
  "schema_version": "1.0.0",

  "research_metadata": {
    "artist_id": "string — internal UUID (will be filled by system)",
    "spotify_id": "string | null",
    "soundcloud_id": "string | null",
    "apple_music_id": "string | null",
    "researched_at": "ISO 8601 timestamp (will be filled by system)",
    "researched_by_model": "string (will be filled by system)",
    "confidence_score": "float 0-1 — your overall confidence in this research",
    "sources_consulted": "int — number of distinct knowledge sources you drew from",
    "needs_review": "bool — set true if low confidence or contradictory information"
  },

  "identity": {
    "artist_name": "string — primary performing name",
    "real_name": "string | null",
    "aliases": ["string"],
    "origin_country": "string | null — ISO 3166 country code",
    "origin_city": "string | null",
    "origin_scene": "string | null — e.g. 'Bristol bass music', 'Berlin techno', 'Chicago house'",
    "active_since": "int | null — year",
    "active_until": "int | null — year, null if still active",
    "primary_labels": ["string"],
    "associated_artists": ["string"],
    "collective_or_crew": "string | null"
  },

  "classification": {
    "primary_genre": "string | null — most specific accurate label",
    "secondary_genres": ["string"],
    "genre_tags": ["string — all applicable tags, broad to narrow"],
    "scene_positioning": "ENUM: 'underground' | 'emerging' | 'established' | 'mainstream' | null",
    "era_association": "string | null — e.g. '2020s UK bass revival'",
    "dj_vs_producer": "ENUM: 'primarily_dj' | 'primarily_producer' | 'both_equal' | 'live_act' | null"
  },

  "tempo_and_rhythm": {
    "bpm_low": "int | null",
    "bpm_high": "int | null",
    "bpm_primary": "int | null — most common single BPM",
    "time_signature": "string | null — e.g. '4/4'",
    "swing_amount": "ENUM: 'none' | 'subtle' | 'moderate' | 'heavy' | null",
    "swing_character": "string | null — e.g. 'MPC shuffle', 'triplet feel'",
    "groove_type": "ENUM: 'straight' | 'shuffled' | 'syncopated' | 'broken' | 'polyrhythmic' | null",
    "rhythmic_complexity": "float 0-1 | null — 0=four-on-floor only, 1=extremely complex",
    "use_of_triplets": "bool | null",
    "ghost_note_density": "ENUM: 'none' | 'sparse' | 'moderate' | 'heavy' | null"
  },

  "drums": {
    "kick_character": "string | null — e.g. 'punchy 909', 'deep sub kick'",
    "kick_pattern": "ENUM: 'four_on_floor' | 'broken' | 'offbeat_heavy' | 'minimal' | 'polyrhythmic' | null",
    "kick_tuning": "ENUM: 'low' | 'mid' | 'high' | 'varies' | null",
    "snare_clap_character": "string | null",
    "snare_clap_placement": "ENUM: '2_and_4' | 'offbeat' | 'syncopated' | 'sparse' | 'none' | null",
    "hihat_style": "string | null — e.g. 'tight closed', 'open ride-like'",
    "hihat_pattern_complexity": "float 0-1 | null — 0=basic 8ths, 1=intricate 32nd note patterns",
    "percussion_layers": "ENUM: 'minimal' | 'moderate' | 'dense' | 'tribal' | null",
    "percussion_elements": ["string — e.g. 'congas', 'bongos', 'shakers', 'rim clicks'"],
    "drum_machine_aesthetic": "ENUM: '808' | '909' | '707' | 'linndrum' | 'acoustic' | 'hybrid' | 'processed_beyond_recognition' | null",
    "drum_processing": "string | null — e.g. 'heavy compression', 'saturated'",
    "use_of_drum_fills": "ENUM: 'none' | 'rare' | 'transitional' | 'frequent' | null",
    "use_of_drum_breaks": "bool | null"
  },

  "bass": {
    "bass_character": "string | null — e.g. 'deep sub', 'acid 303', 'reese'",
    "bass_frequency_focus": "ENUM: 'sub' | 'low_mid' | 'mid' | 'upper_mid' | 'full_range' | null",
    "bass_synthesis_method": "ENUM: 'analog_subtractive' | 'fm' | 'wavetable' | 'sampled' | 'acid_303' | 'resampled' | null",
    "bass_movement": "ENUM: 'static_root' | 'octave_jumps' | 'walking' | 'arpeggiated' | 'glide_heavy' | 'rhythmic_stabs' | null",
    "bass_sidechain_style": "ENUM: 'pumping' | 'subtle_duck' | 'volume_shaping' | 'none' | 'extreme' | null",
    "bass_distortion_amount": "ENUM: 'clean' | 'warm_saturation' | 'moderate_drive' | 'heavy_distortion' | 'destroyed' | null",
    "bass_filter_movement": "bool | null",
    "bass_note_length": "ENUM: 'staccato' | 'short' | 'medium' | 'legato' | 'sustained' | null",
    "bass_role": "ENUM: 'rhythmic_driver' | 'melodic_element' | 'textural_foundation' | 'lead_instrument' | null"
  },

  "harmony_and_melody": {
    "key_preference": "ENUM: 'major' | 'minor' | 'mixed' | 'atonal' | 'modal' | null",
    "common_keys": ["string — e.g. 'Am', 'Em', 'Cm'"],
    "chord_complexity": "ENUM: 'none' | 'simple_triads' | 'seventh_chords' | 'extended' | 'jazz_influenced' | 'atonal' | null",
    "common_progressions": ["string | null — e.g. 'i-VI-III-VII', 'single_chord_vamp'"],
    "melodic_presence": "ENUM: 'none' | 'minimal_hooks' | 'supporting' | 'prominent' | 'lead_focused' | null",
    "melodic_register": "ENUM: 'low' | 'mid' | 'high' | 'full_range' | null",
    "melodic_instruments": ["string — e.g. 'pluck synth', 'piano stabs', 'organ'"],
    "use_of_pads": "ENUM: 'none' | 'subtle_atmosphere' | 'harmonic_foundation' | 'prominent' | null",
    "pad_character": "string | null",
    "use_of_stabs": "ENUM: 'none' | 'rare_accents' | 'rhythmic_feature' | 'signature_element' | null",
    "stab_character": "string | null",
    "use_of_arpeggios": "ENUM: 'none' | 'subtle' | 'featured' | 'driving' | null",
    "tonal_vs_atonal": "float 0-1 | null — 0=fully tonal, 1=fully atonal",
    "harmonic_rhythm": "ENUM: 'static' | 'slow_changes' | 'every_bar' | 'every_beat' | 'rapid' | null"
  },

  "sound_design": {
    "primary_synth_textures": ["string — e.g. 'saw leads', 'square wave stabs'"],
    "synthesis_methods": ["ENUM values: 'subtractive' | 'fm' | 'wavetable' | 'granular' | 'additive' | 'sampling' | 'physical_modeling' | 'resynthesis'"],
    "likely_synths": ["string | null — e.g. 'Serum', 'Diva', 'Massive'"],
    "texture_density": "ENUM: 'minimal_sparse' | 'moderate' | 'dense_layered' | 'maximalist' | null",
    "use_of_noise": "ENUM: 'none' | 'subtle_texture' | 'rhythmic_element' | 'prominent' | null",
    "use_of_fx_risers": "ENUM: 'none' | 'minimal' | 'standard_transitions' | 'dramatic' | null",
    "use_of_impacts": "ENUM: 'none' | 'subtle' | 'standard' | 'heavy' | null",
    "reverb_depth": "ENUM: 'dry' | 'subtle' | 'moderate' | 'deep' | 'cavernous' | null",
    "delay_usage": "ENUM: 'none' | 'subtle_depth' | 'rhythmic_element' | 'prominent_dub' | 'ping_pong_feature' | null",
    "distortion_saturation_usage": "ENUM: 'clean' | 'warm_analog' | 'moderate_grit' | 'heavy' | 'extreme' | null",
    "filter_movement_prominence": "ENUM: 'static' | 'subtle_automation' | 'featured' | 'signature_element' | null",
    "use_of_sampling": "ENUM: 'none' | 'subtle_textures' | 'chopped_rearranged' | 'sample_heavy' | 'primarily_sample_based' | null",
    "sample_sources": ["string | null — e.g. 'disco records', 'film dialogue'"],
    "signature_sounds": ["string | null — description of instantly recognizable elements"],
    "sound_design_originality": "float 0-1 | null — 0=preset-based, 1=completely unique"
  },

  "vocals": {
    "vocal_presence": "ENUM: 'none' | 'minimal_chops' | 'hook_only' | 'verse_chorus' | 'full_vocal_track' | 'spoken_word' | null",
    "vocal_type": "ENUM: 'male' | 'female' | 'mixed' | 'pitched_unidentifiable' | 'spoken' | 'none' | null",
    "vocal_processing": ["string — e.g. 'clean', 'filtered', 'vocoded', 'pitched_up', 'chopped'"],
    "vocal_chop_style": "string | null — e.g. 'rhythmic 16ths', 'melodic phrases'",
    "vocal_source": "ENUM: 'original_recording' | 'sampled_classic' | 'sampled_acapella' | 'speech_sample' | 'synthesized' | 'unknown' | null",
    "vocal_role": "ENUM: 'lead_element' | 'supporting_texture' | 'rhythmic_percussion' | 'atmospheric_layer' | 'call_and_response' | null",
    "use_of_talk_box": "bool | null",
    "use_of_vocoder": "bool | null",
    "topline_writing": "bool | null"
  },

  "arrangement": {
    "typical_track_length_sec": "int | null",
    "arrangement_style": "ENUM: 'dj_tool' | 'song_form' | 'progressive_build' | 'loop_with_variations' | 'narrative_arc' | 'hybrid' | null",
    "intro_style": "ENUM: 'minimal_percussion' | 'ambient_texture' | 'full_groove_immediate' | 'melodic_tease' | 'spoken_intro' | null",
    "intro_length_bars": "int | null",
    "build_technique": "string | null — e.g. 'filter sweeps', 'additive layers'",
    "build_intensity": "float 0-1 | null — 0=subtle, 1=massive dramatic builds",
    "drop_style": "ENUM: 'full_elements_at_once' | 'staggered_entry' | 'bass_first' | 'groove_first' | 'impact_then_groove' | 'no_traditional_drop' | null",
    "drop_impact": "float 0-1 | null — 0=smooth continuous, 1=massive contrast",
    "breakdown_style": "ENUM: 'stripped_percussion' | 'melodic_interlude' | 'ambient_wash' | 'vocal_showcase' | 'tension_builder' | 'minimal' | null",
    "breakdown_length_bars": "int | null",
    "use_of_breakdowns": "ENUM: 'none' | 'one_main' | 'multiple' | 'extended' | null",
    "outro_style": "ENUM: 'mirror_intro' | 'stripped_loop' | 'fadeout' | 'abrupt_end' | 'ambient_tail' | null",
    "outro_length_bars": "int | null",
    "number_of_drops": "int | null",
    "arrangement_variation": "float 0-1 | null — 0=very repetitive/hypnotic, 1=constantly evolving",
    "use_of_silence": "ENUM: 'none' | 'brief_gaps' | 'dramatic_pauses' | 'featured_technique' | null",
    "transition_techniques": ["string — e.g. 'filter sweep', 'drum fill', 'reverse cymbal'"],
    "subtraction_vs_addition": "ENUM: 'primarily_additive' | 'primarily_subtractive' | 'balanced' | null"
  },

  "mix_and_production": {
    "mix_aesthetic": "ENUM: 'clean_polished' | 'warm_analog' | 'lo_fi_gritty' | 'hyper_compressed' | 'dynamic_open' | 'dark_murky' | null",
    "frequency_emphasis": "ENUM: 'sub_heavy' | 'bass_forward' | 'mid_focused' | 'bright_airy' | 'balanced' | 'scooped_mids' | null",
    "stereo_width": "ENUM: 'narrow_mono' | 'moderate' | 'wide' | 'hyper_wide' | null",
    "dynamic_range": "ENUM: 'crushed' | 'moderate_compression' | 'dynamic' | 'very_dynamic' | null",
    "sidechain_prominence": "ENUM: 'none' | 'subtle' | 'standard' | 'pumping' | 'extreme_ducking' | null",
    "low_end_treatment": "string | null — e.g. 'mono below 120Hz', 'layered sub + mid-bass'",
    "high_end_character": "ENUM: 'dark_rolled_off' | 'present' | 'bright' | 'airy_sparkle' | 'harsh' | null",
    "overall_loudness": "ENUM: 'quiet_dynamic' | 'moderate' | 'loud' | 'slammed' | null",
    "production_quality": "ENUM: 'lo_fi_intentional' | 'bedroom_producer' | 'professional' | 'pristine_studio' | null",
    "use_of_field_recordings": "bool | null",
    "use_of_foley": "bool | null",
    "analog_vs_digital": "ENUM: 'fully_digital' | 'mostly_digital_some_analog' | 'hybrid' | 'primarily_analog' | null"
  },

  "energy_and_mood": {
    "energy_level": "float 0-1 | null — 0=ambient, 1=peak time rager",
    "mood_primary": "ENUM: 'dark' | 'moody' | 'neutral' | 'groovy' | 'uplifting' | 'euphoric' | 'aggressive' | 'melancholic' | 'hypnotic' | 'playful' | null",
    "mood_secondary": "ENUM: same as mood_primary | null",
    "atmosphere": "ENUM: 'underground' | 'warehouse' | 'festival' | 'beach_pool' | 'afterhours' | 'intimate_club' | 'rave' | 'lounge' | null",
    "time_of_night": "ENUM: 'warmup' | 'opening' | 'peak_time' | 'late_night' | 'afterhours' | 'sunrise' | 'daytime' | null",
    "danceability": "float 0-1 | null — 0=head-nod only, 1=impossible to stand still",
    "emotional_arc": "ENUM: 'flat_consistent' | 'slow_build' | 'peaks_and_valleys' | 'tension_release' | 'narrative' | null",
    "darkness_brightness": "float 0-1 | null — 0=pitch black, 1=sun-drenched",
    "aggression": "float 0-1 | null — 0=smooth and gentle, 1=industrial assault",
    "hypnotic_quality": "float 0-1 | null — 0=constantly changing, 1=deeply repetitive"
  },

  "context_and_influence": {
    "influenced_by_artists": ["string | null"],
    "influenced_by_genres": ["string | null"],
    "influence_on": ["string | null"],
    "frequent_collaborators": ["string | null"],
    "remix_activity": "ENUM: 'never' | 'occasional' | 'frequent' | 'primarily_remixer' | null",
    "release_frequency": "ENUM: 'rare' | 'annual' | 'regular' | 'prolific' | null",
    "beatport_chart_presence": "ENUM: 'never' | 'occasional' | 'regular' | 'top_seller' | null",
    "spotify_monthly_listeners": "int | null",
    "notable_tracks": ["string | null"],
    "career_trajectory": "ENUM: 'emerging' | 'rising' | 'established' | 'legacy' | 'declining' | 'comeback' | null"
  },

  "production_dna_narrative": "string — 200-500 word rich production analysis. ALWAYS write this even if structured fields are null."
}"""

ARTIST_RESEARCH_PROMPT = """You have web search available. For any artist you are not highly confident about from training data, search for them on Beatport, Resident Advisor, SoundCloud, Discogs, and their label pages before filling in the profile. Use search results to verify BPM ranges, label affiliations, genre classification, and release history. If search returns minimal results, set confidence_score lower and use null for fields you cannot verify.

Research the electronic music artist "{artist_name}" and return a structured JSON profile following the DAW Brain Artist Profile Schema v1.0.0.

Known genre context: {genres}

CRITICAL RULES:
- Use null for any field you cannot determine with reasonable confidence
- Use empty arrays [] for array fields where you've confirmed nothing applies
- Pick from the provided ENUM values exactly — do not invent new ones
- The production_dna_narrative MUST always be written (200-500 words)
- Focus on PRODUCTION characteristics, not biography
- Base your analysis on their released music, not interviews or press materials
- If the artist has evolved significantly over time, prioritize their most recent 2-3 years
- Float fields use 0-1 scale with the anchors noted in the schema
- For research_metadata: set confidence_score (0-1), sources_consulted (int), and needs_review (bool). Leave artist_id, researched_at, and researched_by_model as null (system fills these).

SCHEMA (fill this structure with real data):

{schema}

Return ONLY valid JSON. No markdown, no commentary, no backticks."""

SYNTHESIS_PROMPT = """Based on these structured production profiles of a user's top favorite artists, synthesize a unified "Production DNA" profile.

What are the common threads across these artists? What BPM range, drum approach, bass style, sound design palette, arrangement structure, and mixing character would best match this listener's taste as a producer?

Be specific and opinionated. Make decisions. This profile will be used to shape AI-generated MIDI patterns and production advice. Under 300 words.

Artist profiles (showing key production attributes):

{profiles}"""


# ─── Research Logic ───────────────────────────────────────────────────


def _research_single_artist(client, artist_name, genres):
    """Call Claude to research one artist and return a structured JSON profile."""
    genres_str = ", ".join(genres) if genres else "electronic music (specific genre unknown)"
    prompt = ARTIST_RESEARCH_PROMPT.format(
        artist_name=artist_name,
        genres=genres_str,
        schema=PROFILE_SCHEMA,
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text content from response (skip search result blocks)
        text_blocks = [block.text for block in response.content if block.type == "text"]
        raw_text = "\n".join(text_blocks)

        # Strip markdown code fences if present
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            # Remove first line (```json or ```) and last line (```)
            lines = cleaned.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        profile = json.loads(cleaned)
        profile = _fill_system_fields(profile, artist_name)
        profile = _validate_profile(profile)
        return profile

    except json.JSONDecodeError as e:
        log.error(f"JSON parse failed for {artist_name}: {e}")
        log.debug(f"Raw response: {raw_text[:500]}")
        return None
    except Exception as e:
        log.error(f"Artist research failed for {artist_name}: {e}")
        return None


def _fill_system_fields(profile, artist_name):
    """Fill in system-managed metadata fields."""
    meta = profile.get("research_metadata", {})
    meta["artist_id"] = str(uuid.uuid4())
    meta["researched_at"] = datetime.utcnow().isoformat()
    meta["researched_by_model"] = MODEL
    profile["research_metadata"] = meta
    profile["schema_version"] = SCHEMA_VERSION

    # Ensure identity.artist_name matches
    identity = profile.get("identity", {})
    if not identity.get("artist_name"):
        identity["artist_name"] = artist_name
    profile["identity"] = identity

    return profile


def _validate_profile(profile):
    """Validate and clean the profile, compute confidence if not set."""
    meta = profile.get("research_metadata", {})

    # Compute confidence from field coverage if not already set by the model
    if meta.get("confidence_score") is None:
        meta["confidence_score"] = _compute_confidence(profile)

    # Ensure arrays are arrays (not null)
    _ensure_arrays(profile)

    # Ensure production_dna_narrative exists
    if not profile.get("production_dna_narrative"):
        meta["needs_review"] = True
        profile["production_dna_narrative"] = (
            f"Insufficient data to generate a detailed production analysis for "
            f"{profile.get('identity', {}).get('artist_name', 'this artist')}."
        )

    profile["research_metadata"] = meta
    return profile


def _compute_confidence(profile):
    """Compute a confidence score based on how many key fields are populated."""
    key_fields = [
        ("classification", "primary_genre"),
        ("tempo_and_rhythm", "bpm_primary"),
        ("drums", "kick_character"),
        ("drums", "kick_pattern"),
        ("bass", "bass_character"),
        ("harmony_and_melody", "key_preference"),
        ("sound_design", "texture_density"),
        ("arrangement", "arrangement_style"),
        ("mix_and_production", "mix_aesthetic"),
        ("energy_and_mood", "energy_level"),
        ("energy_and_mood", "mood_primary"),
    ]

    populated = 0
    for section, field in key_fields:
        val = profile.get(section, {}).get(field)
        if val is not None:
            populated += 1

    base = populated / len(key_fields)

    # Boost for narrative
    if profile.get("production_dna_narrative") and len(
        profile.get("production_dna_narrative", "")
    ) > 100:
        base = min(1.0, base + 0.1)

    return round(base, 2)


def _ensure_arrays(profile):
    """Ensure all array fields are lists, not null."""
    array_paths = [
        ("identity", "aliases"),
        ("identity", "primary_labels"),
        ("identity", "associated_artists"),
        ("classification", "secondary_genres"),
        ("classification", "genre_tags"),
        ("drums", "percussion_elements"),
        ("harmony_and_melody", "common_keys"),
        ("harmony_and_melody", "common_progressions"),
        ("harmony_and_melody", "melodic_instruments"),
        ("sound_design", "primary_synth_textures"),
        ("sound_design", "synthesis_methods"),
        ("sound_design", "likely_synths"),
        ("sound_design", "sample_sources"),
        ("sound_design", "signature_sounds"),
        ("vocals", "vocal_processing"),
        ("arrangement", "transition_techniques"),
        ("context_and_influence", "influenced_by_artists"),
        ("context_and_influence", "influenced_by_genres"),
        ("context_and_influence", "influence_on"),
        ("context_and_influence", "frequent_collaborators"),
        ("context_and_influence", "notable_tracks"),
    ]
    for section, field in array_paths:
        sect = profile.get(section, {})
        if not isinstance(sect.get(field), list):
            sect[field] = []
        profile[section] = sect


def _format_profile_summary(profile):
    """Format a compact summary of a profile for the synthesis prompt."""
    lines = []
    identity = profile.get("identity", {})
    name = identity.get("artist_name", "Unknown")
    lines.append(f"**{name}**")

    classification = profile.get("classification", {})
    if classification.get("primary_genre"):
        lines.append(f"  Genre: {classification['primary_genre']}")
    if classification.get("scene_positioning"):
        lines.append(f"  Scene: {classification['scene_positioning']}")

    tempo = profile.get("tempo_and_rhythm", {})
    if tempo.get("bpm_primary"):
        bpm_str = str(tempo["bpm_primary"])
        if tempo.get("bpm_low") and tempo.get("bpm_high"):
            bpm_str = f"{tempo['bpm_low']}-{tempo['bpm_high']} (primary: {tempo['bpm_primary']})"
        lines.append(f"  BPM: {bpm_str}")
    if tempo.get("groove_type"):
        lines.append(f"  Groove: {tempo['groove_type']}, swing: {tempo.get('swing_amount', 'unknown')}")

    drums = profile.get("drums", {})
    if drums.get("kick_character"):
        lines.append(f"  Kick: {drums['kick_character']} ({drums.get('kick_pattern', '?')})")
    if drums.get("drum_machine_aesthetic"):
        lines.append(f"  Drum aesthetic: {drums['drum_machine_aesthetic']}")

    bass = profile.get("bass", {})
    if bass.get("bass_character"):
        lines.append(f"  Bass: {bass['bass_character']} ({bass.get('bass_movement', '?')})")

    sound = profile.get("sound_design", {})
    if sound.get("texture_density"):
        lines.append(f"  Texture: {sound['texture_density']}")
    if sound.get("signature_sounds"):
        lines.append(f"  Signatures: {', '.join(sound['signature_sounds'][:3])}")

    arrangement = profile.get("arrangement", {})
    if arrangement.get("arrangement_style"):
        lines.append(f"  Arrangement: {arrangement['arrangement_style']}")

    mix = profile.get("mix_and_production", {})
    if mix.get("mix_aesthetic"):
        lines.append(f"  Mix: {mix['mix_aesthetic']}")
    if mix.get("frequency_emphasis"):
        lines.append(f"  Freq emphasis: {mix['frequency_emphasis']}")

    energy = profile.get("energy_and_mood", {})
    if energy.get("mood_primary"):
        lines.append(f"  Mood: {energy['mood_primary']}, energy: {energy.get('energy_level', '?')}")
    if energy.get("atmosphere"):
        lines.append(f"  Atmosphere: {energy['atmosphere']}")

    return "\n".join(lines)


# ─── Top Artists Extraction ──────────────────────────────────────────


def _get_top_unique_artists(user_id, limit=15):
    """Merge artists across all time ranges, rank by frequency, return top N."""
    all_artists = get_user_top_artists(user_id)
    if not all_artists:
        return []

    artist_scores = {}
    artist_data = {}
    for a in all_artists:
        name = a["artist_name"]
        if name not in artist_scores:
            artist_scores[name] = 0
            artist_data[name] = a
        artist_scores[name] += 1

    sorted_artists = sorted(
        artist_scores.keys(),
        key=lambda n: (-artist_scores[n], artist_data[n].get("rank", 50))
    )

    return [(name, artist_data[name]) for name in sorted_artists[:limit]]


# ─── Main Research Pipeline ──────────────────────────────────────────


def research_user_artists(user_id):
    """Research the user's top artists' production styles.

    This is the main entry point — call from a background thread.
    """
    update_research_status(user_id, "in_progress")

    try:
        top_artists = _get_top_unique_artists(user_id, limit=15)
        if not top_artists:
            log.warning(f"No top artists found for user {user_id}")
            update_research_status(user_id, "complete")
            return

        artist_names = [name for name, _ in top_artists]

        # Find which ones need research (not cached or expired)
        unresearched = get_unresearched_artists(artist_names)
        stale = get_stale_artist_research(artist_names, max_age_days=90)
        needs_research = list(set(unresearched + stale))

        log.info(f"Artist research: {len(top_artists)} total, "
                 f"{len(needs_research)} need research")

        if needs_research:
            client = anthropic.Anthropic()

            for i in range(0, len(needs_research), 3):
                batch = needs_research[i:i + 3]
                for artist_name in batch:
                    artist_info = next(
                        (data for name, data in top_artists if name == artist_name),
                        None
                    )
                    if not artist_info:
                        continue

                    genres_raw = artist_info.get("genres", "[]")
                    try:
                        genres = json.loads(genres_raw) if isinstance(genres_raw, str) else genres_raw
                    except (json.JSONDecodeError, TypeError):
                        genres = []

                    profile = _research_single_artist(client, artist_name, genres)
                    if not profile:
                        continue

                    # Set spotify_id in metadata
                    spotify_id = artist_info.get("artist_id")
                    if spotify_id:
                        profile["research_metadata"]["spotify_id"] = spotify_id

                    save_artist_research(
                        artist_name, profile, spotify_id=spotify_id
                    )
                    log.info(
                        f"Researched: {artist_name} "
                        f"(confidence: {profile.get('research_metadata', {}).get('confidence_score', '?')})"
                    )

                if i + 3 < len(needs_research):
                    time.sleep(1)

        # Synthesis: build Production DNA from all researched structured profiles
        profile_summaries = []
        for artist_name, _ in top_artists:
            cached = get_artist_research(artist_name)
            if cached and cached.get("profile"):
                summary = _format_profile_summary(cached["profile"])
                profile_summaries.append(summary)

        if profile_summaries:
            try:
                client = anthropic.Anthropic()
                synthesis_prompt = SYNTHESIS_PROMPT.format(
                    profiles="\n\n".join(profile_summaries)
                )
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=600,
                    messages=[{"role": "user", "content": synthesis_prompt}],
                )
                dna = response.content[0].text
                save_production_dna(user_id, dna)
                log.info(f"Production DNA synthesized for user {user_id}")
            except Exception as e:
                log.error(f"Production DNA synthesis failed: {e}")
                update_research_status(user_id, "complete")
        else:
            update_research_status(user_id, "complete")

        # Compute aggregated taste profile from structured artist profiles
        try:
            from brain.taste_aggregator import compute_aggregated_taste_profile
            aggregated = compute_aggregated_taste_profile(user_id)
            if aggregated:
                log.info(f"Aggregated taste profile computed for user {user_id}")
        except Exception as e:
            log.error(f"Taste aggregation failed for user {user_id}: {e}")

    except Exception as e:
        log.error(f"Artist research failed for user {user_id}: {e}")
        update_research_status(user_id, "complete")


def start_background_research(user_id):
    """Launch artist research in a background thread."""
    thread = threading.Thread(
        target=research_user_artists,
        args=(user_id,),
        daemon=True,
        name=f"artist-research-{user_id}",
    )
    thread.start()
    log.info(f"Background artist research started for user {user_id}")
    return thread
