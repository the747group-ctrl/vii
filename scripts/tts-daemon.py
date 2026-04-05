#!/usr/bin/env python3
"""TTS Daemon for Local Whisper — Keeps Kokoro model loaded in memory.

Protocol (stdin/stdout, one JSON per line):
  Request:  {"voice": "am_adam", "text": "Hello world", "output": "/tmp/tts.wav"}
  Response: {"ok": true, "duration": 2.1, "gen_time": 0.8, "sample_rate": 24000}
  Error:    {"ok": false, "error": "message"}

Stays alive until stdin closes or receives {"cmd": "quit"}.
"""
import sys
import os
import json
import time
import re
import soundfile as sf


def preprocess_for_tts(text: str, max_chars: int = 350) -> str:
    """Clean and optimize text for natural-sounding TTS output.

    - Strips markdown formatting
    - Converts abbreviations to spoken form
    - Limits length for snappy responses
    - Adds natural pauses via punctuation
    """
    # Strip markdown
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # bold
    text = re.sub(r'\*(.+?)\*', r'\1', text)        # italic
    text = re.sub(r'`(.+?)`', r'\1', text)          # code
    text = re.sub(r'#{1,6}\s+', '', text)            # headers
    text = re.sub(r'[-*]\s+', '', text)              # bullet points
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)  # links

    # Strip emoji
    text = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F900-\U0001F9FF\U00002702-\U000027B0]', '', text)

    # Normalize whitespace
    text = re.sub(r'\n+', '. ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    # Fix common TTS pronunciation issues
    text = text.replace('%', ' percent')
    text = text.replace('&', ' and ')
    text = text.replace('$', ' dollars ')
    text = text.replace('@', ' at ')
    text = re.sub(r'(\d+)k\b', r'\1 thousand', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d+)M\b', r'\1 million', text)

    # Truncate to max chars at a sentence boundary
    if len(text) > max_chars:
        # Find the last sentence end before max_chars
        truncated = text[:max_chars]
        last_period = max(truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?'))
        if last_period > max_chars * 0.5:
            text = truncated[:last_period + 1]
        else:
            text = truncated.rsplit(' ', 1)[0] + '.'

    # Ensure text ends with punctuation (helps TTS produce natural ending)
    if text and text[-1] not in '.!?':
        text += '.'

    return text


def main():
    # Find model files
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    model_path = os.path.join(project_root, "models", "kokoro", "kokoro-v1.0.onnx")
    voices_path = os.path.join(project_root, "models", "kokoro", "voices-v1.0.bin")

    if not os.path.exists(model_path):
        resp = json.dumps({"ok": False, "error": f"Model not found: {model_path}"})
        print(resp, flush=True)
        sys.exit(1)

    # Load model once
    from kokoro_onnx import Kokoro
    start = time.time()
    kokoro = Kokoro(model_path, voices_path)
    load_time = time.time() - start
    print(json.dumps({"ok": True, "status": "ready", "load_time": round(load_time, 2)}), flush=True)

    # Process requests
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            print(json.dumps({"ok": False, "error": "invalid JSON"}), flush=True)
            continue

        if req.get("cmd") == "quit":
            break

        voice = req.get("voice", "af_heart")
        text = req.get("text", "")
        output = req.get("output", "/tmp/tts-output.wav")
        speed = req.get("speed", 1.0)

        if not text:
            print(json.dumps({"ok": False, "error": "empty text"}), flush=True)
            continue

        # Preprocess text for better TTS output
        processed = preprocess_for_tts(text)

        try:
            start = time.time()
            samples, sample_rate = kokoro.create(processed, voice=voice, speed=speed, lang="en-us")
            gen_time = time.time() - start

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
