"""Knowledge base loader with keyword-based routing.

Analyzes user messages and loads only the relevant knowledge base files
to keep API calls lean and cost-effective.
"""

import os
import re

KNOWLEDGE_DIR = os.path.dirname(__file__)

# Each entry: (filename, list of keyword groups)
# A keyword group is a set of words — if ANY word in the group matches, that KB is a candidate.
# The KB with the most keyword hits wins. Multiple KBs can be loaded if they both score above threshold.
KNOWLEDGE_MAP = {
    "tech_house_production.md": {
        "description": "Core genre knowledge: drums, bass, arrangement, mixing, mastering, genre identity",
        "keywords": [
            # Drums
            "kick", "snare", "clap", "hi-hat", "hihat", "hat", "percussion",
            "drum", "drums", "groove", "swing", "ghost note", "top loop",
            "four on the floor", "backbeat", "fill", "roll", "shaker", "ride",
            "cymbal", "bongo", "conga", "rimshot",
            # Bass
            "bass", "bassline", "sub", "sidechain", "lfo tool", "pumping",
            "offbeat", "glide", "legato",
            # Arrangement
            "arrangement", "arrange", "intro", "outro", "drop", "breakdown",
            "build", "buildup", "transition", "riser", "downlifter", "impact",
            "structure", "bars", "section", "176",
            # Genre
            "tech house", "genre", "bpm", "tempo", "energy", "vibe",
            "underground", "groovy",
            # Mixing basics
            "mix", "mixing", "gain staging", "headroom", "stereo width",
            "mono", "panning", "pan",
            # Mastering basics
            "master", "mastering", "limiter", "lufs", "loudness",
            # Synths/stabs (overview)
            "stab", "stabs", "lead", "synth pad",
            # Vocals (overview)
            "vocal", "vocals", "chop", "chops",
            # FX
            "riser", "sweep", "fx", "effects", "reverb", "delay",
            "saturation", "saturator", "auto filter",
            # Production philosophy
            "principle", "mistake", "tip", "advice", "help",
            "how do i", "how to", "what should",
        ],
        "always_load": True,  # This is the core KB — load for any production question
    },
    "ableton_workflows.md": {
        "description": "Ableton Live 12 shortcuts, routing, CPU optimization, racks, automation, browser",
        "keywords": [
            # Shortcuts
            "shortcut", "keyboard", "hotkey", "key command",
            "cmd", "ctrl", "option", "shift",
            # Navigation
            "session view", "arrangement view", "clip view", "device view",
            "browser", "search", "hot-swap", "collection",
            # Editing
            "consolidate", "split", "crop", "warp", "warping", "warp marker",
            "quantize", "grid", "draw mode", "snap",
            # Routing
            "routing", "route", "sidechain", "send", "return", "bus",
            "group track", "mid side", "m/s", "multiband",
            "parallel", "ny compression", "chain",
            # Racks
            "rack", "audio effect rack", "instrument rack", "macro",
            "chain selector", "zone",
            # Automation
            "automation", "automate", "envelope", "breakpoint", "curve",
            "clip automation", "modulation",
            # CPU / performance
            "cpu", "ram", "freeze", "flatten", "bounce", "buffer",
            "performance", "lag", "crackle", "dropout",
            "options.txt", "frame rate",
            # MIDI
            "midi", "midi effect", "arpeggiator", "chord effect",
            "scale effect", "note length", "velocity effect",
            "groove pool", "mpc",
            # Audio
            "complex pro", "beats mode", "texture mode", "re-pitch",
            "slice", "simpler", "sampler", "drum rack",
            # Session View
            "follow action", "scene", "clip launch", "capture midi",
            # Comping
            "comping", "take lane",
            # Devices
            "eq eight", "compressor", "glue compressor", "utility",
            "operator", "wavetable", "analog", "drift", "meld",
            "roar", "auto shift", "beat repeat",
            # Export
            "export", "render", "bounce",
            # Templates
            "template", "default preset", "user library",
            # Live 12 features
            "live 12", "stem separation", "similarity search",
            "midi generator", "midi transformation", "tags",
        ],
        "always_load": False,
    },
    "sampling_remixing.md": {
        "description": "Sampling philosophy, legal framework, stem separation, warping, chopping, remix workflow",
        "keywords": [
            "sample", "sampling", "remix", "remixing", "bootleg", "edit",
            "stem", "stems", "uvr5", "vocal remover", "stem separation",
            "separate stems",
            "chop", "chopping", "slice", "slicing", "rearrange",
            "warp", "warping", "time stretch", "pitch shift",
            "copyright", "clearance", "legal", "rights", "royalty",
            "cover", "bootleg",
            "distrokid", "landr", "distribute", "release",
            "rekordbox", "dj set", "dj edit",
            "vocoder", "formant",
            "resampling", "resample",
            "process sample", "processing sample",
            "hip-hop", "soul", "disco", "funk",
        ],
        "always_load": False,
    },
    "sound_design.md": {
        "description": "Synthesis fundamentals, Serum 2 patches, Operator, Wavetable, Drift, drum design, FX design",
        "keywords": [
            "sound design", "synthesis", "synthesizer", "synth",
            "oscillator", "osc", "waveform", "wavetable",
            "filter", "cutoff", "resonance", "envelope", "adsr",
            "lfo", "modulation", "mod matrix",
            "serum", "serum 2", "xfer",
            "operator", "fm synthesis", "fm",
            "analog", "ableton analog",
            "wavetable", "ableton wavetable",
            "drift", "ableton drift",
            "granulator", "granular",
            "patch", "preset", "init preset",
            "bass patch", "bass sound", "bass design",
            "pad", "pad sound", "pad patch",
            "pluck", "stab sound",
            "acid", "303",
            "reese", "reese bass",
            "kick design", "kick layer", "kick tuning",
            "snare design", "snare layer", "clap layer",
            "hi-hat design", "hat design",
            "noise riser", "white noise", "impact design",
            "downlifter design", "transition fx",
            "formant", "vocoder",
            "unison", "detune", "spread",
        ],
        "always_load": False,
    },
    "music_theory.md": {
        "description": "Scales, modes, chord progressions, bass theory, melody writing, rhythm theory",
        "keywords": [
            "theory", "music theory",
            "scale", "mode", "key", "minor", "major",
            "phrygian", "dorian", "mixolydian", "aeolian", "pentatonic",
            "chord", "chords", "progression", "chord progression",
            "voicing", "inversion", "voice leading",
            "melody", "melodic", "hook", "riff",
            "bass note", "bass line theory", "root", "fifth", "octave",
            "fourth", "interval", "semitone", "chromatic",
            "tension", "resolution", "dissonance", "consonance",
            "tritone", "dominant", "tonic",
            "rhythm", "syncopation", "polyrhythm",
            "time signature", "4/4", "16th note",
            "transpose", "transposing", "key of",
            "what key", "what scale", "which scale", "which key",
            "harmonic", "harmony",
            "call and response", "call-and-response",
            "swing", "shuffle", "groove", "groove template",
            "mpc", "ghost note", "ghost notes",
        ],
        "always_load": False,
    },
    "sample_sourcing.md": {
        "description": "Splice strategy, sample sources, file formats, library organization, Rekordbox, backups",
        "keywords": [
            "splice", "sample pack", "loopmasters", "beatport sounds",
            "cymatics", "sample source", "find samples", "get samples",
            "where to find",
            "credit", "credits",
            "qobuz", "flac", "wav", "mp3", "m4a", "aiff",
            "file format", "convert", "conversion", "ffmpeg",
            "bit depth", "sample rate", "44.1", "48k", "16-bit", "24-bit",
            "library", "organize", "organization", "folder",
            "naming convention", "tag", "tags", "collection",
            "places", "user library",
            "rekordbox", "cdj", "dj library", "hot cue", "memory cue",
            "playlist",
            "backup", "cloud", "ssd", "external drive",
            "collect all and save",
            "one-shot", "loop", "one shot",
            "field recording", "found sound",
        ],
        "always_load": False,
    },
    "mixing_mastering.md": {
        "description": "Gain staging, EQ techniques, compression, spatial processing, saturation, mastering chain",
        "keywords": [
            "mixing", "mix down", "mixdown",
            "gain staging", "gain stage", "headroom", "dbfs",
            "eq", "equalization", "frequency", "high-pass", "low-pass",
            "notch", "bell cut", "shelf",
            "compression", "compressor", "ratio", "threshold",
            "attack", "release", "knee", "gain reduction",
            "parallel compression", "ny compression", "multiband compression",
            "sidechain compression",
            "reverb", "delay", "spatial", "stereo width", "stereo image",
            "mono compatibility", "haas effect", "haas",
            "saturation", "harmonic", "tape saturation", "warmth",
            "distortion", "overdrive", "soft clip",
            "mastering", "master chain", "master bus",
            "limiter", "limiting", "lufs", "loudness",
            "true peak", "dither", "dithering",
            "export", "render", "bounce", "final mix",
            "reference track", "a/b", "a/b comparison",
            "dynamic range", "dynamics",
        ],
        "always_load": False,
    },
}


def _normalize(text):
    """Lowercase and strip punctuation for matching."""
    return re.sub(r"[^\w\s/]", " ", text.lower())


def _score_kb(kb_key, message_normalized):
    """Score how relevant a knowledge base is to the user's message."""
    info = KNOWLEDGE_MAP[kb_key]
    score = 0
    for kw in info["keywords"]:
        kw_lower = kw.lower()
        # Exact word boundary match for single words, substring for multi-word phrases
        if " " in kw_lower:
            if kw_lower in message_normalized:
                score += 2  # Multi-word matches are worth more
        else:
            # Word boundary match
            if re.search(r"\b" + re.escape(kw_lower) + r"\b", message_normalized):
                score += 1
    return score


def select_knowledge(user_message, max_kbs=3):
    """Select which knowledge bases to load based on user message content.

    Returns a list of (filename, score) tuples, sorted by relevance.
    Always includes tech_house_production.md as the base.
    Loads at most max_kbs knowledge bases to control token usage.
    """
    normalized = _normalize(user_message)

    scores = []
    for kb_key in KNOWLEDGE_MAP:
        filepath = os.path.join(KNOWLEDGE_DIR, kb_key)
        if not os.path.exists(filepath):
            continue
        score = _score_kb(kb_key, normalized)
        info = KNOWLEDGE_MAP[kb_key]
        if info.get("always_load"):
            score = max(score, 1)  # Ensure it's always selected
        if score > 0:
            scores.append((kb_key, score))

    # Sort by score descending
    scores.sort(key=lambda x: x[1], reverse=True)

    # Cap at max_kbs
    return scores[:max_kbs]


def load_knowledge(user_message, max_kbs=3):
    """Load and concatenate relevant knowledge base content.

    Returns a single string with all relevant knowledge, separated by markers.
    """
    selected = select_knowledge(user_message, max_kbs=max_kbs)

    if not selected:
        # Fallback: load core KB if it exists
        core_path = os.path.join(KNOWLEDGE_DIR, "tech_house_production.md")
        if os.path.exists(core_path):
            with open(core_path, "r") as f:
                return f.read()
        return ""

    parts = []
    for kb_key, score in selected:
        filepath = os.path.join(KNOWLEDGE_DIR, kb_key)
        try:
            with open(filepath, "r") as f:
                content = f.read()
            parts.append(content)
        except (FileNotFoundError, IOError):
            continue

    return "\n\n---\n\n".join(parts)
