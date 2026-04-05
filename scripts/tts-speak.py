#!/usr/bin/env python3
"""TTS helper for Local Whisper — Generates speech via Kokoro-82M.

Usage: tts-speak.py <voice_id> <output_wav> <text>

Loads the model once (cached in memory if called via import),
generates speech, writes to WAV file. Exit code 0 on success.
"""
import sys
import os
import time
import soundfile as sf
from kokoro_onnx import Kokoro

def main():
    if len(sys.argv) < 4:
        print("Usage: tts-speak.py <voice_id> <output_wav> <text>", file=sys.stderr)
        sys.exit(1)

    voice_id = sys.argv[1]
    output_path = sys.argv[2]
    text = " ".join(sys.argv[3:])

    # Find model files relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    model_path = os.path.join(project_root, "models", "kokoro", "kokoro-v1.0.onnx")
    voices_path = os.path.join(project_root, "models", "kokoro", "voices-v1.0.bin")

    if not os.path.exists(model_path):
        print(f"Model not found: {model_path}", file=sys.stderr)
        sys.exit(2)

    start = time.time()
    kokoro = Kokoro(model_path, voices_path)
    load_time = time.time() - start

    start = time.time()
    samples, sample_rate = kokoro.create(text, voice=voice_id, speed=1.0, lang="en-us")
    gen_time = time.time() - start

    sf.write(output_path, samples, sample_rate)

    duration = len(samples) / sample_rate
    print(f"load={load_time:.2f}s gen={gen_time:.2f}s dur={duration:.2f}s rate={sample_rate}", file=sys.stderr)
    # Print sample_rate to stdout for Rust to parse
    print(sample_rate)

if __name__ == "__main__":
    main()
