#!/usr/bin/env python3
"""VII Two — Streaming TTS Daemon v2

Keeps Kokoro model loaded in memory. Accepts streaming text input
(sentence-by-sentence) and outputs audio chunks immediately.

Protocol (stdin/stdout, one JSON per line):

  Startup:    → {"ok": true, "status": "ready", "load_time": 0.3}

  Request:    ← {"text": "Hello world.", "voice": "am_onyx", "speed": 1.0, "stream": true}
  Chunk:      → {"type": "audio_chunk", "audio": "<base64>", "sample_rate": 24000, "mouth_sync": [...], "is_final": false}
  Done:       → {"type": "done", "duration": 1.2, "gen_time": 0.4}

  Interrupt:  ← {"type": "interrupt"}
              → {"type": "interrupted"}

  Quit:       ← {"cmd": "quit"}

Developed by The 747 Lab
"""
import sys
import os
import json
import time
import base64
import struct
import math
import numpy as np

# Add project root to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)


def preprocess_for_tts(text: str) -> str:
    """Clean text for natural TTS. Handles smart quotes, markdown, abbreviations."""
    import re

    # Smart quotes → straight (critical for Kokoro phonemization)
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')

    # Strip markdown
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'#{1,6}\s+', '', text)
    text = re.sub(r'[-*]\s+', '', text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)

    # Normalize whitespace
    text = re.sub(r'\n+', '. ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    # TTS pronunciation fixes
    text = text.replace('%', ' percent')
    text = text.replace('&', ' and ')
    text = text.replace('$', ' dollars ')
    text = re.sub(r'(\d+)k\b', r'\1 thousand', text, flags=re.IGNORECASE)

    return text


def compute_mouth_sync(samples: np.ndarray, sample_rate: int, fps: int = 20) -> list:
    """Compute RMS levels at given FPS for mouth animation sync."""
    chunk_size = sample_rate // fps
    levels = []
    for i in range(0, len(samples), chunk_size):
        chunk = samples[i:i + chunk_size]
        if len(chunk) == 0:
            continue
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        levels.append(round(min(rms * 3.0, 1.0), 3))  # amplify + clamp
    return levels


def samples_to_int16_bytes(samples: np.ndarray) -> bytes:
    """Convert float32 samples to int16 bytes for playback."""
    clipped = np.clip(samples, -1.0, 1.0)
    int16 = (clipped * 32767).astype(np.int16)
    return int16.tobytes()


def main():
    model_path = os.path.join(project_root, "models", "kokoro", "kokoro-v1.0.onnx")
    voices_path = os.path.join(project_root, "models", "kokoro", "voices-v1.0.bin")

    if not os.path.exists(model_path):
        print(json.dumps({"ok": False, "error": f"Model not found: {model_path}"}), flush=True)
        sys.exit(1)

    # Load model once — this is the expensive operation (~300ms)
    from kokoro_onnx import Kokoro
    start = time.time()
    kokoro = Kokoro(model_path, voices_path)
    load_time = time.time() - start

    print(json.dumps({
        "ok": True,
        "status": "ready",
        "load_time": round(load_time, 2),
        "version": 2,
    }), flush=True)

    interrupted = False

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            print(json.dumps({"ok": False, "error": "invalid JSON"}), flush=True)
            continue

        # Handle commands
        if req.get("cmd") == "quit":
            break

        if req.get("type") == "interrupt":
            interrupted = True
            print(json.dumps({"type": "interrupted"}), flush=True)
            continue

        # Reset interrupt flag on new request
        interrupted = False

        voice = req.get("voice", "af_heart")
        text = req.get("text", "")
        speed = req.get("speed", 1.0)
        stream = req.get("stream", False)

        if not text:
            print(json.dumps({"ok": False, "error": "empty text"}), flush=True)
            continue

        # Clean text
        processed = preprocess_for_tts(text)

        try:
            gen_start = time.time()

            # Generate audio
            samples, sample_rate = kokoro.create(
                processed, voice=voice, speed=speed, lang="en-us"
            )

            gen_time = time.time() - gen_start

            if interrupted:
                print(json.dumps({"type": "interrupted"}), flush=True)
                continue

            if stream:
                # Stream mode: send audio as base64 chunks
                # Split into ~250ms chunks for low-latency playback
                chunk_samples = sample_rate // 4  # 250ms chunks
                total_chunks = math.ceil(len(samples) / chunk_samples)

                for i in range(total_chunks):
                    if interrupted:
                        print(json.dumps({"type": "interrupted"}), flush=True)
                        break

                    start_idx = i * chunk_samples
                    end_idx = min(start_idx + chunk_samples, len(samples))
                    chunk = samples[start_idx:end_idx]

                    # Convert to int16 bytes and base64 encode
                    audio_bytes = samples_to_int16_bytes(chunk)
                    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")

                    # Compute mouth sync for this chunk
                    mouth_sync = compute_mouth_sync(chunk, sample_rate)

                    is_final = (i == total_chunks - 1)

                    print(json.dumps({
                        "type": "audio_chunk",
                        "audio": audio_b64,
                        "sample_rate": sample_rate,
                        "mouth_sync": mouth_sync,
                        "is_final": is_final,
                        "chunk_index": i,
                        "total_chunks": total_chunks,
                    }), flush=True)

                if not interrupted:
                    duration = len(samples) / sample_rate
                    print(json.dumps({
                        "type": "done",
                        "duration": round(duration, 2),
                        "gen_time": round(gen_time, 2),
                        "sample_rate": sample_rate,
                    }), flush=True)

            else:
                # Legacy mode: write to file (compatible with VII Zero)
                output = req.get("output", "/tmp/tts-output.wav")
                import soundfile as sf
                sf.write(output, samples, sample_rate)
                duration = len(samples) / sample_rate

                print(json.dumps({
                    "ok": True,
                    "duration": round(duration, 2),
                    "gen_time": round(gen_time, 2),
                    "sample_rate": sample_rate,
                    "samples": len(samples),
                }), flush=True)

        except Exception as e:
            print(json.dumps({"ok": False, "error": str(e)}), flush=True)


if __name__ == "__main__":
    main()
