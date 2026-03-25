from brain.presets import tech_house, uk_bass, minimal_tech, bassline

PRESETS = {
    "tech_house": tech_house,
    "uk_bass": uk_bass,
    "minimal_tech": minimal_tech,
    "bassline": bassline,
}


def get_preset(name):
    return PRESETS.get(name, tech_house)


def list_presets():
    return [
        {
            "id": key,
            "label": mod.label,
            "bpm_range": mod.bpm_range,
            "description": mod.description,
        }
        for key, mod in PRESETS.items()
    ]
