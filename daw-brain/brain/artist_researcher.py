"""
AI artist production research — uses Claude to analyze the production style
of a user's top Spotify artists, then synthesizes a Production DNA profile.
Runs in a background thread.
"""

import json
import time
import logging
import threading
import anthropic

from brain.database import (
    get_user_top_artists, get_artist_research, save_artist_research,
    get_unresearched_artists, get_stale_artist_research,
    update_research_status, save_production_dna,
)

log = logging.getLogger("daw-brain")

MODEL = "claude-sonnet-4-20250514"

ARTIST_RESEARCH_PROMPT = """You are a music production analyst. Research the production style of {artist_name} who makes {genres}.

Provide a structured production profile covering:
1. BPM range they typically work in
2. Drum patterns and percussion style (kick character, hat patterns, groove, swing)
3. Bass design (sub behavior, mid-bass character, sidechain approach, movement)
4. Sound design signatures (synth types, textures, FX, vocal treatment)
5. Arrangement tendencies (song structure, build/drop style, breakdown approach, track length)
6. Mixing characteristics (frequency balance, stereo width, compression, loudness)
7. What makes their production instantly recognizable

Be specific. Use parameter-level detail where possible (e.g., "kicks around 50Hz fundamental, tight 30ms decay" not just "punchy kicks"). Keep the total response under 250 words."""

SYNTHESIS_PROMPT = """Based on these production profiles of a user's top favorite artists, synthesize a unified "Production DNA" profile. What are the common threads across these artists? What BPM range, drum approach, bass style, sound design palette, arrangement structure, and mixing character would best match this listener's taste as a producer?

Be specific and opinionated. Make decisions. This profile will be used to shape AI-generated MIDI patterns and production advice. Under 300 words.

{profiles}"""


def _get_top_unique_artists(user_id, limit=15):
    """Merge artists across all time ranges, rank by frequency, return top N."""
    all_artists = get_user_top_artists(user_id)
    if not all_artists:
        return []

    # Count appearances across time ranges and track best rank
    artist_scores = {}
    artist_data = {}
    for a in all_artists:
        name = a["artist_name"]
        if name not in artist_scores:
            artist_scores[name] = 0
            artist_data[name] = a
        # Artist in more time ranges = higher score
        artist_scores[name] += 1

    # Sort by frequency (desc), then by rank in their time range
    sorted_artists = sorted(
        artist_scores.keys(),
        key=lambda n: (-artist_scores[n], artist_data[n].get("rank", 50))
    )

    return [(name, artist_data[name]) for name in sorted_artists[:limit]]


def _research_single_artist(client, artist_name, genres):
    """Make a Claude API call to research one artist's production style."""
    genres_str = ", ".join(genres) if genres else "electronic music"
    prompt = ARTIST_RESEARCH_PROMPT.format(artist_name=artist_name, genres=genres_str)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception as e:
        log.error(f"Artist research failed for {artist_name}: {e}")
        return None


def _parse_research_fields(profile_text):
    """Extract structured fields from the profile text.

    Returns a dict with bpm_range, drum_style, bass_style, etc.
    This is best-effort extraction from free text.
    """
    fields = {
        "bpm_range": None,
        "drum_style": None,
        "bass_style": None,
        "sound_design_notes": None,
        "arrangement_style": None,
        "mixing_character": None,
        "signature_elements": None,
    }

    lines = profile_text.split("\n")
    current_section = None
    section_map = {
        "1": "bpm_range",
        "2": "drum_style",
        "3": "bass_style",
        "4": "sound_design_notes",
        "5": "arrangement_style",
        "6": "mixing_character",
        "7": "signature_elements",
    }

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Check if it starts with a section number
        for num, field in section_map.items():
            if stripped.startswith(f"{num}.") or stripped.startswith(f"{num})"):
                current_section = field
                content = stripped.split(".", 1)[-1].strip() if "." in stripped else stripped.split(")", 1)[-1].strip()
                # Remove leading label like "BPM range:" if present
                if ":" in content:
                    content = content.split(":", 1)[-1].strip()
                fields[field] = content
                break
        else:
            # Continuation of current section
            if current_section and fields[current_section]:
                fields[current_section] += " " + stripped

    return fields


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

        # Find which ones need research (not cached or stale)
        unresearched = get_unresearched_artists(artist_names)
        stale = get_stale_artist_research(artist_names, max_age_days=30)
        needs_research = list(set(unresearched + stale))

        log.info(f"Artist research: {len(top_artists)} total, {len(needs_research)} need research")

        if needs_research:
            client = anthropic.Anthropic()

            # Process in batches of 3 with 1s delay between batches
            for i in range(0, len(needs_research), 3):
                batch = needs_research[i:i + 3]
                for artist_name in batch:
                    # Find artist data
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

                    profile_text = _research_single_artist(client, artist_name, genres)
                    if not profile_text:
                        continue

                    fields = _parse_research_fields(profile_text)
                    research_data = {
                        "genres": genres,
                        "popularity": artist_info.get("popularity"),
                        "production_profile": profile_text,
                        "bpm_range": fields.get("bpm_range"),
                        "drum_style": fields.get("drum_style"),
                        "bass_style": fields.get("bass_style"),
                        "sound_design_notes": fields.get("sound_design_notes"),
                        "arrangement_style": fields.get("arrangement_style"),
                        "mixing_character": fields.get("mixing_character"),
                        "signature_elements": fields.get("signature_elements"),
                        "researched_by_model": MODEL,
                        "research_version": 1,
                    }
                    save_artist_research(
                        artist_name,
                        artist_info.get("artist_id"),
                        research_data,
                    )
                    log.info(f"Researched: {artist_name}")

                if i + 3 < len(needs_research):
                    time.sleep(1)

        # Synthesis: build Production DNA from all researched artists
        profiles_text = []
        for artist_name, _ in top_artists:
            cached = get_artist_research(artist_name)
            if cached and cached.get("production_profile"):
                profiles_text.append(f"**{artist_name}:**\n{cached['production_profile']}")

        if profiles_text:
            try:
                client = anthropic.Anthropic()
                synthesis_prompt = SYNTHESIS_PROMPT.format(
                    profiles="\n\n".join(profiles_text)
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
