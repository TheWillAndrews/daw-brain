import os
import sys
import json
import time
import logging
import tempfile
import subprocess
import traceback
import threading
from flask import Flask, request, jsonify, send_from_directory
import anthropic

from brain.system_prompts import build_system_prompt
from brain.output_parser import parse_response
from brain.midi_generator import generate_midi
from brain.presets import list_presets
from brain.vocal_separator import separate_vocals, OUTPUT_DIR as STEMS_DIR

app = Flask(__name__, static_folder="static")
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB upload limit

# Logging setup — prints to terminal with timestamps
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("daw-brain")

OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "outputs")
ALLOWED_AUDIO_EXTENSIONS = {'.wav', '.mp3', '.flac', '.m4a'}

client = anthropic.Anthropic()

# Heartbeat: browser pings every 3s, server shuts down after 10s of silence
last_heartbeat = time.time()
HEARTBEAT_TIMEOUT = 10


@app.route("/api/heartbeat", methods=["POST"])
def heartbeat():
    global last_heartbeat
    last_heartbeat = time.time()
    return "", 204


def watchdog():
    """Shuts down the server when the browser stops sending heartbeats."""
    # Give the browser 15s to load initially
    time.sleep(15)
    while True:
        if time.time() - last_heartbeat > HEARTBEAT_TIMEOUT:
            pidfile = os.path.join(os.path.dirname(__file__), ".server.pid")
            if os.path.exists(pidfile):
                os.remove(pidfile)
            os._exit(0)
        time.sleep(2)


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/static/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)


@app.route("/api/presets")
def get_presets():
    return jsonify(list_presets())


@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        messages = data.get("messages", [])
        session = data.get("session", {})
        genre = data.get("genre", "tech_house")
        active_element = data.get("activeElement", None)
        element_history = data.get("elementHistory", None)
        skill_level = data.get("skillLevel", "expert")

        if not messages:
            return jsonify({"error": "No messages provided"}), 400

        # Extract the latest user message for knowledge routing
        latest_user_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                latest_user_msg = msg.get("content", "")
                break

        log.info(f"Chat request — element: {active_element}, genre: {genre}, msg: {latest_user_msg[:80]}")

        system_prompt = build_system_prompt(
            session, genre, user_message=latest_user_msg,
            active_element=active_element, element_history=element_history,
            skill_level=skill_level
        )

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
            )
        except Exception as e:
            log.error(f"Anthropic API error: {e}")
            return jsonify({"error": f"API error: {str(e)}"}), 500

        raw_text = response.content[0].text
        cleaned_text, output_data = parse_response(raw_text)

        result = {"text": cleaned_text, "output": output_data, "file_url": None}

        if output_data and output_data.get("type") == "midi":
            bpm = session.get("bpm", 128)
            filename = generate_midi(output_data, bpm=bpm)
            if filename:
                result["file_url"] = f"/outputs/{filename}"
                log.info(f"Generated MIDI: {filename}")

        # For arrangement and parameters, save as JSON
        if output_data and output_data.get("type") in ("arrangement", "parameters"):
            name = output_data.get("name", "output")
            safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in name)
            filename = f"{safe_name}.json"
            os.makedirs(OUTPUTS_DIR, exist_ok=True)
            filepath = os.path.join(OUTPUTS_DIR, filename)
            with open(filepath, "w") as f:
                json.dump(output_data, f, indent=2)
            result["file_url"] = f"/outputs/{filename}"
            log.info(f"Generated JSON: {filename}")

        return jsonify(result)

    except Exception as e:
        log.error(f"Chat route crashed:\n{traceback.format_exc()}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route("/outputs/stems/<path:filename>")
def serve_stem(filename):
    return send_from_directory(STEMS_DIR, filename, as_attachment=False)


@app.route("/outputs/<path:filename>")
def serve_output(filename):
    return send_from_directory(OUTPUTS_DIR, filename, as_attachment=True)


@app.route("/api/vocals/separate", methods=["POST"])
def vocal_separate():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files['file']
        if not file.filename:
            return jsonify({"error": "No file selected"}), 400

        # Check file extension
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_AUDIO_EXTENSIONS:
            return jsonify({"error": "Unsupported format. Use WAV, MP3, FLAC, or M4A."}), 400

        log.info(f"Vocal separation started: {file.filename}")

        # Save to temp file
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        try:
            file.save(tmp.name)
            tmp.close()

            result = separate_vocals(tmp.name)

            if not result['vocal']:
                log.error("Separation produced no output files")
                return jsonify({"error": "Separation produced no output files"}), 500

            vocal_filename = os.path.basename(result['vocal'])
            vocal_size = os.path.getsize(result['vocal'])

            log.info(f"Vocal separation complete: {vocal_filename} ({vocal_size} bytes)")

            return jsonify({
                "status": "complete",
                "vocal_url": f"/outputs/stems/{vocal_filename}",
                "vocal_size": vocal_size,
            })
        except subprocess.TimeoutExpired:
            log.error("Vocal separation timed out (15 min limit)")
            return jsonify({"error": "Separation timed out (15 min limit). Try a shorter file."}), 500
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    except Exception as e:
        log.error(f"Vocal separator crashed:\n{traceback.format_exc()}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.errorhandler(Exception)
def handle_exception(e):
    log.error(f"Unhandled exception:\n{traceback.format_exc()}")
    return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.errorhandler(413)
def handle_too_large(e):
    log.warning("Upload rejected: file exceeds 50MB limit")
    return jsonify({"error": "File too large. Max 50MB."}), 413


if __name__ == "__main__":
    debug = "--debug" in sys.argv
    log.info("DAW Brain starting on http://127.0.0.1:5050")
    # Start watchdog thread (only when launched normally, not in debug)
    if not debug:
        t = threading.Thread(target=watchdog, daemon=True)
        t.start()
    app.run(debug=debug, port=5050, use_reloader=False)
