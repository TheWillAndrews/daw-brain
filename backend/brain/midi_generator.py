import os
import mido

OUTPUTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")
PPQ = 480  # Ticks per quarter note


def sanitize_filename(name):
    """Sanitize a string for use as a filename (alphanumeric, hyphens, underscores)."""
    return "".join(c if c.isalnum() or c in "_-" else "_" for c in name)


def generate_midi(output_data, bpm=128):
    """Generate a .mid file from a parsed MIDI output object.

    Args:
        output_data: Dict with 'name', 'notes' (list of note dicts).
        bpm: Tempo in BPM.

    Returns:
        Filename of the generated MIDI file, or None on failure.
    """
    notes = output_data.get("notes", [])
    if not notes:
        return None

    name = output_data.get("name", "pattern")
    safe_name = sanitize_filename(name)
    filename = f"{safe_name}.mid"

    mid = mido.MidiFile(type=0, ticks_per_beat=PPQ)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # Set tempo
    tempo = mido.bpm2tempo(bpm)
    track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))

    # Build a list of (absolute_tick, event_type, pitch, velocity) events
    events = []
    for note in notes:
        pitch = int(note.get("pitch", 60))
        start = float(note.get("start", 1.0))
        duration = float(note.get("duration", 0.5))
        velocity = int(note.get("velocity", 100))

        pitch = max(0, min(127, pitch))
        velocity = max(1, min(127, velocity))

        start_tick = max(0, int((start - 1) * PPQ))
        dur_tick = max(1, int(duration * PPQ))

        events.append((start_tick, "note_on", pitch, velocity))
        events.append((start_tick + dur_tick, "note_off", pitch, 0))

    # Sort by tick, then note_off before note_on at the same tick
    events.sort(key=lambda e: (e[0], 0 if e[1] == "note_off" else 1))

    # Convert to delta times
    current_tick = 0
    for tick, event_type, pitch, velocity in events:
        delta = tick - current_tick
        if event_type == "note_on":
            track.append(mido.Message("note_on", note=pitch, velocity=velocity, time=delta))
        else:
            track.append(mido.Message("note_off", note=pitch, velocity=0, time=delta))
        current_tick = tick

    # End of track
    track.append(mido.MetaMessage("end_of_track", time=0))

    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUTS_DIR, filename)
    mid.save(filepath)

    return filename
