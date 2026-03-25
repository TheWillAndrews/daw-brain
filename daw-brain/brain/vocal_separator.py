import os
import subprocess

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'outputs', 'stems')


def separate_vocals(input_path):
    """
    Separate vocals from a track using Kim Vocal 2 model.
    Returns dict with paths to vocal and instrumental stems.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    filename = os.path.splitext(os.path.basename(input_path))[0]

    # Ensure common bin dirs are in PATH for ffmpeg/audio-separator
    env = os.environ.copy()
    path_dirs = env.get('PATH', '').split(os.pathsep)
    for d in ['/usr/local/bin', '/opt/homebrew/bin']:
        if d not in path_dirs:
            path_dirs.insert(0, d)
    env['PATH'] = os.pathsep.join(path_dirs)

    result = subprocess.run([
        'audio-separator',
        input_path,
        '--model_filename', 'Kim_Vocal_2.onnx',
        '--output_dir', OUTPUT_DIR,
        '--output_format', 'WAV'
    ], capture_output=True, text=True, timeout=900, env=env)

    if result.returncode != 0:
        raise Exception(f"Separation failed: {result.stderr}")

    # Single pass: find vocal stem, collect instrumentals for cleanup
    vocal_path = None
    to_delete = []

    for f in os.listdir(OUTPUT_DIR):
        if filename in f and f.endswith('.wav'):
            full = os.path.join(OUTPUT_DIR, f)
            if 'Instrumental' in f:
                to_delete.append(full)
            elif 'Vocal' in f:
                vocal_path = full
            elif not vocal_path:
                vocal_path = full  # fallback: first matching wav

    for path in to_delete:
        os.remove(path)

    return {'vocal': vocal_path}
