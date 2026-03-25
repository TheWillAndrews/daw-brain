import os
import subprocess
from pathlib import Path

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'outputs', 'stems')


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def separate_vocals(input_path):
    """
    Separate vocals from a track using Kim Vocal 2 model.
    Returns dict with paths to vocal and instrumental stems.
    """
    ensure_output_dir()

    filename = Path(input_path).stem

    # Ensure /usr/local/bin is in PATH for ffmpeg
    env = os.environ.copy()
    path_dirs = env.get('PATH', '').split(':')
    for d in ['/usr/local/bin', '/opt/homebrew/bin']:
        if d not in path_dirs:
            env['PATH'] = d + ':' + env['PATH']

    # Run audio-separator with Kim Vocal 2 model
    result = subprocess.run([
        'audio-separator',
        input_path,
        '--model_filename', 'Kim_Vocal_2.onnx',
        '--output_dir', OUTPUT_DIR,
        '--output_format', 'WAV'
    ], capture_output=True, text=True, timeout=900, env=env)

    if result.returncode != 0:
        raise Exception(f"Separation failed: {result.stderr}")

    # Find the vocal stem and discard the instrumental
    vocal_path = None

    for f in os.listdir(OUTPUT_DIR):
        if filename in f and f.endswith('.wav'):
            if 'Vocal' in f and 'Instrumental' not in f:
                vocal_path = os.path.join(OUTPUT_DIR, f)
            elif 'Instrumental' in f:
                # Delete instrumental to save disk space
                os.remove(os.path.join(OUTPUT_DIR, f))

    # Fallback: if naming didn't match, take the first file
    if not vocal_path:
        for f in os.listdir(OUTPUT_DIR):
            if filename in f and f.endswith('.wav'):
                vocal_path = os.path.join(OUTPUT_DIR, f)
                break

    return {'vocal': vocal_path}
