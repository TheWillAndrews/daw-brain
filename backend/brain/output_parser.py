import json
import re


def parse_response(text):
    """Parse Claude's response to extract structured output blocks.

    Returns (cleaned_text, output_data) where output_data is the parsed
    JSON object or None if no output block was found.
    """
    pattern = r"\[OUTPUT\]\s*(.*?)\s*\[/OUTPUT\]"
    match = re.search(pattern, text, re.DOTALL)

    if not match:
        return text, None

    json_str = match.group(1).strip()

    # Clean the text by removing the output block
    cleaned_text = text[: match.start()].rstrip()
    after = text[match.end() :].strip()
    if after:
        cleaned_text += "\n\n" + after

    try:
        output = json.loads(json_str)
    except json.JSONDecodeError:
        return cleaned_text, None

    output_type = output.get("type")
    if output_type not in ("midi", "arrangement", "parameters"):
        return cleaned_text, None

    if output_type == "midi" and "notes" not in output:
        return cleaned_text, None

    if output_type == "arrangement" and "sections" not in output:
        return cleaned_text, None

    if output_type == "parameters" and "chain" not in output:
        return cleaned_text, None

    return cleaned_text, output
