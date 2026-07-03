import json
import logging

from brain.presets import get_preset
from brain.knowledge import load_knowledge, select_knowledge

log = logging.getLogger("daw-brain")

# Single source of truth for element display names
ELEMENT_NAMES = {
    "kick": "Kick", "clap": "Clap/Snare", "hats": "Hats",
    "perc": "Percussion", "toploop": "Top Loops",
    "sub": "Sub Bass", "midbass": "Mid Bass",
    "stabs": "Stabs", "lead": "Lead", "chords": "Chords", "pad": "Pad",
    "arps": "Arps", "plucks": "Plucks",
    "mainvox": "Main Vocal", "chops": "Chops", "hook": "Hook",
    "adlibs": "Ad-libs",
    "risers": "Risers", "downlifters": "Downlifters", "impacts": "Impacts",
    "sweeps": "Sweeps", "transitions": "Transitions", "textures": "Textures",
}


# Condensed core principles — always injected regardless of which KBs load.
# Extracted from tech_house_production.md section 13.
CORE_PRINCIPLES = """
CORE TECH HOUSE PRINCIPLES (ALWAYS APPLY):
1. The groove IS the track — kick, percussion, and top loops carry 70% of the energy
2. Less is more — one element processed well beats five competing ideas
3. Subtraction over accumulation — remove to create tension, add to release it
4. Waves not walls — stagger element entry, never drop everything at once
5. Sidechain everything to the kick — LFO Tool on bass, compressor on stabs/vocals/returns
6. Mono below 150 Hz — no exceptions
7. Two-bar minimum drum patterns — bar 2 varies from bar 1
8. Missing kicks create lift — the floor drops out at convergence points
9. Vocals are icing — lock instruments first, finalize vocals last
10. Commit groove last — keep flexibility until everything else is done
11. Less processing on the sample — use Auto Filter and EQ as arrangement automation tools, not permanent effects
12. Genre identity governs all decisions — this is groovy daytime beach energy, not dark 5am afterparty
""".strip()


# Map elements to their knowledge sections for targeted KB loading
ELEMENT_KB_HINTS = {
    "kick": "drums kick four-on-the-floor",
    "clap": "drums clap snare backbeat",
    "hats": "drums hats hihat swing groove",
    "perc": "drums percussion congas shaker",
    "toploop": "drums top loop audio filtering",
    "sub": "bass sub sidechain mono",
    "midbass": "bass serum analog filter envelope",
    "stabs": "synths stabs chords pluck",
    "lead": "synths lead melody arpeggio",
    "chords": "chords progression voicing music theory",
    "pad": "synths pad atmospheric texture",
    "arps": "synths arpeggio sequenced melodic sixteenth rolling hypnotic",
    "plucks": "synths pluck percussive single-note melodic counter-melody decay",
    "mainvox": "vocals arrangement processing chain",
    "chops": "vocals sampling chops simpler",
    "hook": "vocals hook one-shot phrase",
    "adlibs": "vocals ad-lib one-shot shouts breaths exclamations texture",
    "risers": "fx riser white noise sweep",
    "downlifters": "fx downlifter reverse",
    "impacts": "fx impact hit drop",
    "sweeps": "fx sweep filter noise",
    "transitions": "fx transition fill reverse cymbal",
    "textures": "fx ambient atmosphere vinyl noise room tone background wash reverb tail",
}


SKILL_LEVEL_PROMPTS = {
    "expert": """RESPONSE STYLE: Expert mode. Be terse and production-focused. When generating MIDI, describe exactly what the pattern contains — note values, rhythmic positions, velocity, pitch, bar count. No theory explanations, no definitions, no suggestions for next steps. Just the facts of what was generated and why it fits the session context. For non-MIDI responses, give direct parameter values and decisions without hand-holding.""",

    "intermediate": """RESPONSE STYLE: Intermediate mode. Describe what you generated and briefly explain the reasoning behind key decisions in the context of the genre and session. Don't define basic production terms (kick, snare, sidechain, BPM, etc.) but do explain genre-specific choices and why they work. Keep it concise but informative.""",

    "novice": """RESPONSE STYLE: Novice mode. Explain everything. When generating MIDI, describe what the pattern contains, explain why each choice matters, define any production terminology, and suggest what the user should do next. Assume the user is new to production and needs guidance at every step. Be encouraging and educational. Reference how to use the output in Ableton Live.""",
}


def _parse_json_field(raw, default=None):
    """Safely parse a JSON field that might be a string or already parsed."""
    if default is None:
        default = []
    if not raw:
        return default
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return default


def build_taste_context(user_id):
    """Build the LISTENER PROFILE section from Spotify and/or SoundCloud data.

    Uses the rich aggregated taste profile (from structured artist research)
    when available, falling back to the genre-based profile for backward
    compatibility. Returns a formatted string for system prompt injection.
    """
    try:
        from brain.database import (
            get_taste_profile, get_user_top_artists,
            get_soundcloud_taste_profile, get_soundcloud_tokens,
            get_spotify_tokens, get_aggregated_taste_profile,
        )
    except ImportError:
        return ""

    spotify_profile = get_taste_profile(user_id)
    sc_profile = get_soundcloud_taste_profile(user_id)

    has_spotify = spotify_profile is not None and get_spotify_tokens(user_id) is not None
    has_sc = sc_profile is not None and get_soundcloud_tokens(user_id) is not None

    if not has_spotify and not has_sc:
        return ""

    # ── Try rich aggregated profile first ─────────────────────
    aggregated = get_aggregated_taste_profile(user_id)
    if aggregated:
        return _build_rich_taste_context(
            aggregated, user_id, spotify_profile, sc_profile,
            has_spotify, has_sc
        )

    # ── Fallback: genre-based profile ─────────────────────────
    return _build_legacy_taste_context(
        user_id, spotify_profile, sc_profile, has_spotify, has_sc
    )


def _build_rich_taste_context(aggregated, user_id, spotify_profile, sc_profile,
                               has_spotify, has_sc):
    """Build taste context from the structured aggregated profile."""
    sources = []
    if has_spotify:
        sources.append("Spotify")
    if has_sc:
        sources.append("SoundCloud")
    sources_str = " + ".join(sources)

    ctx = f"LISTENER PROFILE (from {sources_str} — {aggregated.get('artist_count', 0)} artists analyzed):\n\n"

    # Genre & Scene
    genre = aggregated.get("genre", {})
    if genre.get("primary"):
        ctx += f"Primary genre: {genre['primary']}\n"
    if genre.get("secondary"):
        ctx += f"Secondary genres: {', '.join(genre['secondary'])}\n"
    if genre.get("all_tags"):
        ctx += f"Genre tags: {', '.join(genre['all_tags'][:10])}\n"

    # Tempo & Rhythm
    tempo = aggregated.get("tempo", {})
    if tempo.get("center_bpm"):
        bpm_range = tempo.get("bpm_range", [None, None])
        range_str = ""
        if bpm_range[0] and bpm_range[1]:
            range_str = f" (range: {bpm_range[0]}-{bpm_range[1]})"
        ctx += f"BPM: {tempo['center_bpm']}{range_str}\n"
    if tempo.get("groove_tendency"):
        ctx += f"Groove: {tempo['groove_tendency']}"
        if tempo.get("swing_tendency"):
            ctx += f", swing: {tempo['swing_tendency']}"
        ctx += "\n"
    if tempo.get("rhythmic_complexity") is not None:
        ctx += f"Rhythmic complexity: {tempo['rhythmic_complexity']:.1f}/1.0\n"

    ctx += "\n"

    # Sound Palette
    palette = aggregated.get("sound_palette", {})
    ctx += "SOUND PALETTE:\n"
    if palette.get("drum_aesthetic"):
        ctx += f"  Drum aesthetic: {palette['drum_aesthetic']}\n"
    if palette.get("kick_pattern"):
        ctx += f"  Kick: {palette.get('kick_character', '?')} ({palette['kick_pattern']})\n"
    if palette.get("percussion_layers"):
        ctx += f"  Percussion: {palette['percussion_layers']}"
        if palette.get("common_percussion"):
            ctx += f" — {', '.join(palette['common_percussion'][:5])}"
        ctx += "\n"
    if palette.get("hihat_complexity") is not None:
        ctx += f"  Hi-hat complexity: {palette['hihat_complexity']:.1f}/1.0\n"
    if palette.get("bass_character"):
        bass_detail = palette['bass_character']
        if palette.get("bass_movement"):
            bass_detail += f", {palette['bass_movement']}"
        if palette.get("bass_sidechain"):
            bass_detail += f", sidechain: {palette['bass_sidechain']}"
        ctx += f"  Bass: {bass_detail}\n"
    if palette.get("bass_synth_method"):
        ctx += f"  Bass synthesis: {palette['bass_synth_method']}\n"
    if palette.get("texture_density"):
        ctx += f"  Texture density: {palette['texture_density']}\n"
    if palette.get("vocal_preference"):
        ctx += f"  Vocals: {palette['vocal_preference']}\n"
    if palette.get("common_instruments"):
        ctx += f"  Common melodic instruments: {', '.join(palette['common_instruments'][:6])}\n"
    if palette.get("synthesis_methods"):
        ctx += f"  Synthesis: {', '.join(palette['synthesis_methods'])}\n"

    # Harmony
    harmony = aggregated.get("harmony", {})
    if harmony.get("key_preference") or harmony.get("chord_complexity"):
        ctx += "\nHARMONY:\n"
        if harmony.get("key_preference"):
            ctx += f"  Key preference: {harmony['key_preference']}\n"
        if harmony.get("chord_complexity"):
            ctx += f"  Chord complexity: {harmony['chord_complexity']}\n"
        if harmony.get("melodic_presence"):
            ctx += f"  Melodic presence: {harmony['melodic_presence']}\n"

    # Arrangement
    arr = aggregated.get("arrangement", {})
    if arr.get("structure_style"):
        ctx += "\nARRANGEMENT:\n"
        ctx += f"  Structure: {arr['structure_style']}\n"
        if arr.get("build_intensity") is not None:
            ctx += f"  Build intensity: {arr['build_intensity']:.1f}/1.0\n"
        if arr.get("drop_impact") is not None:
            ctx += f"  Drop impact: {arr['drop_impact']:.1f}/1.0\n"
        if arr.get("variation_level") is not None:
            ctx += f"  Variation: {arr['variation_level']:.1f}/1.0\n"
        if arr.get("preferred_transitions"):
            ctx += f"  Transitions: {', '.join(arr['preferred_transitions'])}\n"

    # Mix Character
    mix = aggregated.get("mix_character", {})
    if mix.get("aesthetic"):
        ctx += "\nMIX CHARACTER:\n"
        ctx += f"  Aesthetic: {mix['aesthetic']}\n"
        if mix.get("frequency_emphasis"):
            ctx += f"  Frequency emphasis: {mix['frequency_emphasis']}\n"
        if mix.get("sidechain_style"):
            ctx += f"  Sidechain: {mix['sidechain_style']}\n"
        if mix.get("dynamic_range"):
            ctx += f"  Dynamic range: {mix['dynamic_range']}\n"

    # Mood & Energy
    mood = aggregated.get("mood_and_energy", {})
    ctx += "\nMOOD & ENERGY:\n"
    if mood.get("primary_mood"):
        ctx += f"  Mood: {mood['primary_mood']}\n"
    if mood.get("energy") is not None:
        ctx += f"  Energy: {mood['energy']:.1f}/1.0\n"
    if mood.get("danceability") is not None:
        ctx += f"  Danceability: {mood['danceability']:.1f}/1.0\n"
    if mood.get("darkness_brightness") is not None:
        ctx += f"  Brightness: {mood['darkness_brightness']:.1f}/1.0 (0=dark, 1=bright)\n"
    if mood.get("hypnotic_quality") is not None:
        ctx += f"  Hypnotic quality: {mood['hypnotic_quality']:.1f}/1.0\n"
    if mood.get("aggression") is not None:
        ctx += f"  Aggression: {mood['aggression']:.1f}/1.0\n"
    if mood.get("atmosphere"):
        ctx += f"  Atmosphere: {mood['atmosphere']}\n"
    if mood.get("time_of_night"):
        ctx += f"  Time of night: {mood['time_of_night']}\n"

    # Artist Summary
    summary = aggregated.get("artist_summary", {})
    if summary.get("top_artists"):
        ctx += f"\nTop artists: {', '.join(summary['top_artists'][:8])}\n"
    if summary.get("underground_ratio") is not None:
        ctx += f"Underground ratio: {summary['underground_ratio']:.0%}\n"

    # Production DNA narrative (from legacy synthesis, if available)
    dna_parts = []
    if has_spotify and spotify_profile:
        sp_dna = spotify_profile.get("production_dna")
        if sp_dna and spotify_profile.get("research_status") == "complete":
            dna_parts.append(sp_dna)
    if has_sc and sc_profile:
        sc_dna = sc_profile.get("production_dna")
        if sc_dna and sc_profile.get("research_status") == "complete":
            dna_parts.append(sc_dna)

    if dna_parts:
        ctx += f"\nPRODUCTION DNA SYNTHESIS:\n"
        ctx += "\n\n".join(dna_parts)
        ctx += "\n"

    # Taste evolution
    evolutions = []
    if has_spotify and spotify_profile and spotify_profile.get("evolving_taste"):
        evolutions.append(spotify_profile["evolving_taste"])
    if has_sc and sc_profile and sc_profile.get("evolving_taste"):
        evolutions.append(sc_profile["evolving_taste"])
    if evolutions:
        ctx += f"\nTaste evolution: {'; '.join(evolutions)}\n"

    ctx += """
Use this profile to passively shape all suggestions. Don't mention the profile, Spotify, or SoundCloud explicitly unless asked. Let it influence your decisions about tempo, key, mood, energy, drum patterns, bass design, sound palette, and arrangement style. When the user asks for something generic like "give me a bass pattern," use this DNA to make opinionated choices that match their taste.
"""
    return ctx


def _build_legacy_taste_context(user_id, spotify_profile, sc_profile,
                                 has_spotify, has_sc):
    """Build taste context from the genre-based profile (backward compatibility)."""
    try:
        from brain.database import get_user_top_artists
    except ImportError:
        return ""

    sources = []
    if has_spotify:
        sources.append("Spotify")
    if has_sc:
        sources.append("SoundCloud")
    sources_str = " + ".join(sources)

    # ── BPM ───────────────────────────────────────────────────
    bpm_parts = []
    if has_spotify and spotify_profile.get("preferred_bpm"):
        bpm_parts.append(float(spotify_profile["preferred_bpm"]))
    if has_sc and sc_profile.get("avg_bpm"):
        bpm_parts.append(float(sc_profile["avg_bpm"]))
    preferred_bpm = round(sum(bpm_parts) / len(bpm_parts), 1) if bpm_parts else "N/A"

    bpm_range = ""
    if has_spotify:
        bpm_range = f" (range: {spotify_profile.get('bpm_range_low', '?')}-{spotify_profile.get('bpm_range_high', '?')})"

    # ── Keys ──────────────────────────────────────────────────
    keys = spotify_profile.get("preferred_keys", "N/A") if has_spotify else "N/A"
    if has_sc:
        sc_keys = _parse_json_field(sc_profile.get("preferred_keys"))
        if sc_keys:
            keys = ", ".join(sc_keys) if keys == "N/A" else f"{keys}, {', '.join(sc_keys)}"

    # ── Energy / Mood / Vocal ─────────────────────────────────
    def _merge_quality(sp_val, sc_val):
        if sp_val and sc_val:
            if sp_val == sc_val:
                return sp_val
            return f"{sp_val} (Spotify) / {sc_val} (SoundCloud)"
        return sp_val or sc_val or "N/A"

    sp_energy = spotify_profile.get("energy_level") if has_spotify else None
    sc_energy = sc_profile.get("energy_level") if has_sc else None
    energy = _merge_quality(sp_energy, sc_energy)

    sp_mood = spotify_profile.get("mood") if has_spotify else None
    sc_mood = sc_profile.get("mood") if has_sc else None
    mood = _merge_quality(sp_mood, sc_mood)

    sp_vocal = spotify_profile.get("vocal_preference") if has_spotify else None
    sc_vocal = sc_profile.get("vocal_preference") if has_sc else None
    vocal = _merge_quality(sp_vocal, sc_vocal)

    # ── Genres (merged, deduplicated) ─────────────────────────
    all_genres = []
    if has_spotify:
        all_genres.extend(_parse_json_field(spotify_profile.get("top_genres")))
    if has_sc:
        all_genres.extend(_parse_json_field(sc_profile.get("top_genres")))
    seen = set()
    merged_genres = []
    for g in all_genres:
        gl = g.lower()
        if gl not in seen:
            seen.add(gl)
            merged_genres.append(g)

    # ── Artists ────────────────────────────────────────────────
    artist_names = []
    if has_spotify:
        short_artists = get_user_top_artists(user_id, "short_term")
        artist_names.extend(a["artist_name"] for a in short_artists[:5])
    if has_sc:
        sc_artists = _parse_json_field(sc_profile.get("top_artists"))
        artist_names.extend(sc_artists[:5])
    seen_artists = set()
    unique_artists = []
    for a in artist_names:
        al = a.lower()
        if al not in seen_artists:
            seen_artists.add(al)
            unique_artists.append(a)

    # ── Build Context String ──────────────────────────────────
    ctx = f"LISTENER PROFILE (from {sources_str}):\n"
    ctx += f"This producer's listening is centered on: {', '.join(merged_genres[:6]) if merged_genres else 'N/A'}\n"
    ctx += f"Estimated BPM preference: {preferred_bpm}{bpm_range}\n"

    if keys and keys != "N/A":
        ctx += f"Preferred keys: {keys}\n"

    ctx += f"Energy level: {energy}\n"
    ctx += f"Mood tendency: {mood}\n"
    ctx += f"Vocal preference: {vocal}\n"

    ctx += f"Top genres: {', '.join(merged_genres[:10]) if merged_genres else 'N/A'}\n"

    # SoundCloud-specific fields
    if has_sc:
        sc_tags = _parse_json_field(sc_profile.get("top_tags"))
        if sc_tags:
            ctx += f"Top tags: {', '.join(sc_tags[:10])} (SoundCloud)\n"
        if sc_profile.get("underground_score") is not None:
            ctx += f"Underground score: {sc_profile['underground_score']}/10 (SoundCloud)\n"

    ctx += f"Recent favorites: {', '.join(unique_artists[:8]) if unique_artists else 'N/A'}\n"

    if has_spotify:
        long_artists = get_user_top_artists(user_id, "long_term")
        long_names = ", ".join(a["artist_name"] for a in long_artists[:5]) if long_artists else "N/A"
        ctx += f"All-time favorites: {long_names}\n"

    # Taste evolution
    evolutions = []
    if has_spotify and spotify_profile.get("evolving_taste"):
        evolutions.append(spotify_profile["evolving_taste"])
    if has_sc and sc_profile.get("evolving_taste"):
        evolutions.append(sc_profile["evolving_taste"])
    if evolutions:
        ctx += f"Taste evolution: {'; '.join(evolutions)}\n"

    # Production DNA
    dna_parts = []
    if has_spotify:
        sp_dna = spotify_profile.get("production_dna")
        if sp_dna and spotify_profile.get("research_status") == "complete":
            dna_parts.append(f"From Spotify artists:\n{sp_dna}")
    if has_sc:
        sc_dna = sc_profile.get("production_dna")
        if sc_dna and sc_profile.get("research_status") == "complete":
            dna_parts.append(f"From SoundCloud artists:\n{sc_dna}")

    if dna_parts:
        ctx += f"\nPRODUCTION DNA (researched from favorite artists):\n"
        ctx += "\n\n".join(dna_parts)
        ctx += "\n"

    ctx += """
Use this profile to passively shape all suggestions. Don't mention the profile, Spotify, or SoundCloud explicitly unless asked. Let it influence your decisions about tempo, key, mood, energy, drum patterns, bass design, sound palette, and arrangement style. When the user asks for something generic like "give me a bass pattern," use this DNA to make opinionated choices that match their taste.
"""
    return ctx


def build_system_prompt(session, genre_id="tech_house", user_message="",
                        active_element=None, element_history=None,
                        skill_level="expert", musical_context="",
                        session_id=None, user_id=None):
    preset = get_preset(genre_id)

    bpm = session.get("bpm", 128)
    key = session.get("key", "C")
    scale = session.get("scale", "minor")

    # Build knowledge routing hint: combine user message with element context
    kb_hint = user_message
    if active_element and active_element in ELEMENT_KB_HINTS:
        kb_hint = f"{ELEMENT_KB_HINTS[active_element]} {user_message}"

    # Load only the 1-2 most relevant knowledge bases per call (token budget)
    knowledge_content, selected = load_knowledge(kb_hint, max_kbs=2)
    kb_names = ", ".join(f"{name} (score:{score})" for name, score in selected)

    prompt = f"""You are DAW Brain, an expert electronic music production AI for Ableton Live.

You provide EXACT parameter values, SPECIFIC MIDI data, and PRECISE production decisions — never vague advice. When a producer asks for a bass pattern, you give them the actual notes. When they ask for a signal chain, you give them exact device settings.

CURRENT SESSION STATE:
- BPM: {bpm}
- Key: {key} {scale}
- Genre: {preset.label}
- BPM Range for Genre: {preset.bpm_range[0]}–{preset.bpm_range[1]}

RESPONSE BEHAVIOR RULES (ALWAYS FOLLOW):

1. COMMANDS vs QUESTIONS — Recognize the difference.
   - A COMMAND is when the user tells you exactly what to generate: "4 bar kick pattern, four on the floor, quarter notes on C1" or "bass line in E minor, offbeat 8th notes, 2 bars." Execute these LITERALLY. Do not add ghost notes, variations, missing beats, velocity changes, or creative flourishes unless the user asked for them. Give them exactly what they described.
   - A QUESTION is when the user asks for advice, opinions, or suggestions: "what should my hi-hat pattern be?" or "how do I make my bass groove better?" or "give me a groovy kick pattern." Respond with production knowledge, creative suggestions, and generate output that reflects your genre expertise.
   - A REQUEST is somewhere in between: "give me a kick pattern" without specifics. Use your genre knowledge to make good creative decisions, but keep it straightforward. Don't over-complicate.

2. DON'T GENERATE MIDI ON EVERY RESPONSE.
   - Only generate a MIDI [OUTPUT] block when the user is clearly asking for a pattern, a file, or something to download.
   - If the user asks a question about production technique, mixing, theory, or workflow, just answer the question. No MIDI output needed.
   - If the user says "tell me about" or "explain" or "what is" or "how do I" — that's a knowledge request, not a generation request.
   - If the user asks "what should I do for the bass?" — give advice first. Only generate MIDI if they then say "yeah do that" or "generate it" or "let's hear it."

3. ASK FOLLOW-UP QUESTIONS WHEN THE REQUEST IS UNCLEAR — but minimize them.
   - If you genuinely cannot determine what the user wants, ask ONE clear follow-up question. Not two, not three. One.
   - Before asking, try your hardest to interpret the request using context: the session state (BPM, key, genre), the active element, previous conversation, and common sense.
   - Examples of when to ask: "make it bouncier" (bouncier how — more swing? more ghost notes? shorter note lengths? — pick the most likely interpretation based on genre and context, but if truly ambiguous, ask)
   - Examples of when NOT to ask: "4 bar bass pattern" — you have the key, BPM, and genre. Just generate it. Don't ask "what style of bass?" if the genre is already set to tech house.
   - NEVER ask follow-up questions about information you already have in the session state. If the BPM is 128 and the user says "make a kick pattern," don't ask what BPM.
   - If the user's request has one ambiguous part but the rest is clear, make your best decision on the ambiguous part and mention what you assumed: "I went with offbeat 8th notes for the bass rhythm — let me know if you want a different pattern."

4. MATCH THE ENERGY OF THE REQUEST.
   - Short request = short response. "kick pattern, 4 bars" → generate it with a brief 1-2 sentence description. Don't write a paragraph about kick drum philosophy.
   - Detailed request = detailed response. "I want a kick pattern that has ghost kicks on the .3 positions of beats 1 and 3, missing kicks on 2 and 4 of bar 2, velocity alternation 110/100" → execute precisely, confirm what you did.
   - Conversational message = conversational response. "this sounds flat, what's wrong?" → diagnose and suggest fixes, no MIDI needed.

"""

    # Element focus section
    if active_element and active_element in ELEMENT_KB_HINTS:
        element_label = active_element.replace("_", " ").upper()
        element_descriptions = {
            "arps": "Arpeggiated synth patterns. Sequenced melodic movement, typically 16th notes. Key element in tech house for hypnotic, rolling energy. Think CHASEWEST, SLAMM.",
            "plucks": "Short, percussive single-note melodic hits. Distinct from stabs (which are chordal). Tight decay, used for counter-melodies and call-and-response with bass or vocals.",
            "adlibs": "One-shot vocal hits, shouts, breaths, exclamations, spoken phrases. Not the main vocal, not melodic chops, not hooks. These are texture and energy — the vocal seasoning.",
            "textures": "Ambient atmospheres, vinyl noise, room tone, background washes, reverb tails. Sits behind everything in the mix. Adds depth and space without drawing attention.",
        }
        label = ELEMENT_NAMES.get(active_element, element_label).upper()
        desc = element_descriptions.get(active_element, "")
        desc_line = f" {desc}" if desc else ""
        prompt += f"ELEMENT FOCUS: The user is working on {label}.{desc_line} Focus your responses on this element — patterns, samples, processing, and how it fits the track.\n\n"

    # Cross-element awareness
    if element_history:
        built_elements = {k: v for k, v in element_history.items()
                         if v.get("status") in ("complete", "locked") and v.get("summary")}
        if built_elements:
            prompt += "ELEMENTS ALREADY BUILT:\n"
            for elem_id, info in built_elements.items():
                name = ELEMENT_NAMES.get(elem_id, elem_id)
                prompt += f"- {name}: {info['summary']}\n"
            prompt += "\nConsider the existing elements when generating. New elements should complement what's already built — avoid rhythmic clashes, fill frequency gaps, and create call-and-response relationships.\n\n"

    # Deep musical context — actual MIDI note data from generated elements
    # If no frontend-provided context, try building from DB
    if not musical_context and session_id:
        try:
            from brain.database import build_musical_context_from_db
            musical_context = build_musical_context_from_db(
                session_id, bpm, key, scale
            )
        except Exception:
            pass

    if musical_context:
        prompt += """MUSICAL CONTEXT:
The following elements have been generated in this session. Use this data to make musically informed decisions. Specifically:
- Avoid rhythmic conflicts (don't place accents where another element already fills the space, unless layering is intentional)
- Reinforce groove convergence points (if multiple elements accent the same position, that's a signature moment — preserve it)
- Respect frequency ranges (don't generate content that competes in the same frequency band as existing elements)
- Use complementary rhythms (if the kick is sparse at bar 2 beat 1, consider whether this element should fill or preserve that space)
- Reference specific notes and positions from existing elements when explaining your decisions
- Check the CROSS-ELEMENT ANALYSIS section (if present) for occupied/open beat positions, frequency gaps, and groove character — use this to find your lane

"""
        prompt += musical_context + "\n"

    # Spotify taste profile integration
    if user_id:
        try:
            taste_ctx = build_taste_context(user_id)
            if taste_ctx:
                prompt += taste_ctx + "\n"
        except Exception as e:
            log.warning(f"Failed to build taste context: {e}")

    prompt += f"""{CORE_PRINCIPLES}

GENRE & PRODUCTION KNOWLEDGE (loaded: {kb_names}):
{knowledge_content}

OUTPUT FORMAT INSTRUCTIONS:

When the user asks you to generate MIDI patterns, arrangements, or signal chains, include a structured output block in your response wrapped in [OUTPUT] and [/OUTPUT] markers. The block must contain valid JSON matching one of these schemas:

MIDI Pattern:
{{
  "type": "midi",
  "name": "descriptive_snake_case_name",
  "description": "what this pattern does",
  "musical_summary": "2-bar four-on-floor kick at C1, straight 8ths, vel 90-110, accents on 1 and 3",
  "specs": "4 bars | Quarter notes | C2 (Kick) | 128 BPM | 16 notes | Vel 90-110",
  "notes": [
    {{"pitch": 40, "start": 1.0, "duration": 0.5, "velocity": 100}}
  ]
}}

The "musical_summary" field is a compact, plain-language description of the musical content — what pitches, rhythmic positions, groove feel, velocity dynamics, and musical role this element plays. This summary is used by the system to provide context to subsequent element generation. Write it as if briefing another producer: "offbeat 16th hat pattern, open hats on &-of-2 and &-of-4, ghost closed hats at vel 40, swing feel." Be specific about positions and character.

The "specs" field is a SHORT one-line summary shown in the download card. Format: "[bars] | [note values] | [pitch/instrument] | [BPM] | [note count] | [velocity range or detail]". Keep it scannable — no sentences, just pipe-separated specs. Include ghost notes or swing if present (e.g. "Vel 80-110, ghost kicks on &").

Pitch reference: C1=24, E1=28, A1=33, C2=36 (kick), D2=38 (snare), E2=40, F#2=42 (closed hat), A2=45, Bb2=46 (open hat), C3=48, E3=52, C4=60 (middle C).
Start: Beat position, 1-indexed. 1.0 = beat 1, 1.5 = "and" of 1, 1.25 = first 16th after beat 1, 2.75 = last 16th of beat 2. For a 4-bar pattern in 4/4, range is 1.0–16.99.
Duration (THIS IS CRITICAL — get it right):
  - 0.25 = SIXTEENTH note (quarter of a beat)
  - 0.5  = EIGHTH note (half a beat)
  - 1.0  = QUARTER note (one full beat)
  - 2.0  = HALF note (two beats)
  - 4.0  = WHOLE note (four beats)
When the user says "quarter notes" they mean duration 1.0. When they say "eighth notes" they mean duration 0.5. When they say "sixteenth notes" they mean duration 0.25. Do not confuse these. A four-on-the-floor kick pattern using quarter notes means 4 notes per bar, each with duration 1.0, placed at beats 1.0, 2.0, 3.0, 4.0.
Velocity: 1–127.

MIDI EXAMPLE — "2 bar four on the floor kick, quarter notes, C1":
notes: [
  {{"pitch":36, "start":1.0, "duration":1.0, "velocity":100}},
  {{"pitch":36, "start":2.0, "duration":1.0, "velocity":100}},
  {{"pitch":36, "start":3.0, "duration":1.0, "velocity":100}},
  {{"pitch":36, "start":4.0, "duration":1.0, "velocity":100}},
  {{"pitch":36, "start":5.0, "duration":1.0, "velocity":100}},
  {{"pitch":36, "start":6.0, "duration":1.0, "velocity":100}},
  {{"pitch":36, "start":7.0, "duration":1.0, "velocity":100}},
  {{"pitch":36, "start":8.0, "duration":1.0, "velocity":100}}
]
That is 8 notes across 2 bars. NOT 32 notes. NOT sixteenth notes.

Arrangement Template:
{{
  "type": "arrangement",
  "name": "arrangement_name",
  "totalBars": 176,
  "sections": [
    {{"name": "Intro", "startBar": 1, "endBar": 32, "description": "what happens", "elements": ["kick", "hats"]}}
  ],
  "notes": "overall arrangement philosophy"
}}

Signal Chain / Parameters:
{{
  "type": "parameters",
  "name": "chain_name",
  "description": "what this chain does",
  "chain": [
    {{"device": "EQ Eight", "position": 1, "settings": {{"Band 1 Freq": "80 Hz", "Band 1 Gain": "-3 dB"}}, "notes": "why this setting"}}
  ]
}}

RULES:
1. Always include EXACTLY ONE [OUTPUT] block when generating patterns, arrangements, or signal chains.
2. Include production reasoning in your text BEFORE the output block — explain WHY you made the choices you did.
3. Use velocity variation to create groove and dynamics. Never use flat velocity across all notes.
4. Respect the current key and scale. All pitched notes must be in {key} {scale}.
5. Respect the genre identity. Every choice should serve the genre's production philosophy.
6. Reference existing elements in the session when relevant — the pattern should fit the context.
7. Be specific. "Add some reverb" is wrong. "Reverb: decay 1.8s, pre-delay 20ms, dry/wet 25%, high-cut at 6kHz" is right.

"""

    # Append skill level response style
    level_key = skill_level if skill_level in SKILL_LEVEL_PROMPTS else "expert"
    prompt += SKILL_LEVEL_PROMPTS[level_key] + "\n"

    return prompt
