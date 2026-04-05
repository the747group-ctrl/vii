#!/usr/bin/env python3
"""
VII — Voice Intelligence Interface
===================================

Hold SPACE to speak. Release to get a response. That's it.

Five agents, five voices. Say their name to dispatch:
  "Bob, what should we focus on?"
  "Falcon, research this market"
  "Pixi, design something beautiful"

Architecture: Mic → Whisper STT → Streaming Claude → Overlapped Kokoro TTS → Speaker

Run:  ./tts-venv/bin/python3 vii.py

Developed by The 747 Lab
"""

import asyncio
import base64
import json
import os
import re
import sys
import tempfile
import threading
import time
import queue
import numpy as np

# ─── Config ───────────────────────────────────────────────

SAMPLE_RATE = 16000
CHANNELS = 1
MODEL_SIZE = "small"
CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 250

AGENTS = {
    "bob":    {"voice": "am_onyx",    "speed": 1.0,  "role": "Lead strategist. Deep, authoritative."},
    "falcon": {"voice": "am_michael", "speed": 0.95, "role": "Intelligence analyst. Measured, precise."},
    "ace":    {"voice": "bf_emma",    "speed": 1.15, "role": "Operations specialist. British, efficient."},
    "pixi":   {"voice": "af_heart",   "speed": 1.25, "role": "Creative director. Expressive, enthusiastic."},
    "buzz":   {"voice": "am_puck",    "speed": 1.3,  "role": "Content strategist. Playful, energetic."},
    "claude": {"voice": "af_nicole",  "speed": 1.1,  "role": "General assistant. Warm, versatile."},
}

DEFAULT_AGENT = "bob"

# ─── Paths ────────────────────────────────────────────────

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")


def load_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    auth = os.path.expanduser("~/.openclaw/agents/main/agent/auth-profiles.json")
    if os.path.exists(auth):
        with open(auth) as f:
            data = json.load(f)
            key = data.get("profiles", {}).get("anthropic:manual", {}).get("token", "")
            if key.startswith("sk-"):
                return key
    return ""


# ─── STT: Whisper ─────────────────────────────────────────

_whisper_model = None

def load_whisper():
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model

    from faster_whisper import WhisperModel
    model_dir = os.path.join(MODELS_DIR, "models--Systran--faster-whisper-small", "snapshots")
    # Find the actual snapshot directory
    if os.path.exists(model_dir):
        snapshots = os.listdir(model_dir)
        if snapshots:
            model_path = os.path.join(model_dir, snapshots[0])
            print(f"  Loading Whisper from local cache...")
            _whisper_model = WhisperModel(model_path, device="cpu", compute_type="int8")
            return _whisper_model

    # Fallback: download
    print(f"  Loading Whisper {MODEL_SIZE} (may download)...")
    _whisper_model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    return _whisper_model


def transcribe(audio_data: np.ndarray) -> str:
    model = load_whisper()
    segments, _ = model.transcribe(audio_data, language="en", beam_size=3)
    text = " ".join(s.text.strip() for s in segments).strip()
    return text


# ─── TTS: Kokoro ──────────────────────────────────────────

_kokoro = None

def load_kokoro():
    global _kokoro
    if _kokoro is not None:
        return _kokoro

    from kokoro_onnx import Kokoro
    model_path = os.path.join(MODELS_DIR, "kokoro", "kokoro-v1.0.onnx")
    voices_path = os.path.join(MODELS_DIR, "kokoro", "voices-v1.0.bin")
    print(f"  Loading Kokoro TTS...")
    _kokoro = Kokoro(model_path, voices_path)
    return _kokoro


def tts_generate(text: str, voice: str, speed: float) -> tuple:
    """Generate TTS audio. Returns (samples_float32, sample_rate)."""
    kokoro = load_kokoro()
    # Clean for TTS
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'[`#*]', '', text)
    text = text.replace('%', ' percent').replace('&', ' and ')
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    samples, sr = kokoro.create(text, voice=voice, speed=speed, lang="en-us")
    return samples, sr


# ─── Audio I/O ────────────────────────────────────────────

def record_audio_hold(stop_event: threading.Event) -> np.ndarray:
    """Record audio until stop_event is set. Returns float32 array."""
    import sounddevice as sd

    audio_chunks = []

    def callback(indata, frames, time_info, status):
        if not stop_event.is_set():
            audio_chunks.append(indata.copy())

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE, channels=CHANNELS,
        dtype='float32', blocksize=1024, callback=callback,
    )
    stream.start()

    while not stop_event.is_set():
        time.sleep(0.05)

    stream.stop()
    stream.close()

    if not audio_chunks:
        return np.array([], dtype=np.float32)

    audio = np.concatenate(audio_chunks, axis=0).flatten()
    return audio


def play_audio(samples: np.ndarray, sample_rate: int):
    """Play audio samples through speakers. Blocks until done."""
    import sounddevice as sd
    sd.play(samples, sample_rate)
    sd.wait()


# ─── Agent Dispatch ───────────────────────────────────────

def detect_agent(text: str) -> tuple:
    lower = text.lower().strip()
    for name in AGENTS:
        for p in [name + ", ", name + " ", "hey " + name, "ask " + name]:
            if lower.startswith(p):
                return name, text[len(p):].strip()
    return None, text


# ─── Sentence Extraction ─────────────────────────────────

ABBREVS = {"Dr", "Mr", "Mrs", "Ms", "Prof", "Sr", "Jr", "vs", "etc", "Inc"}

def extract_sentences(text: str) -> tuple:
    """Returns (complete_sentences, remaining_text)."""
    sentences = []
    last = 0
    for i, ch in enumerate(text):
        if ch in '.!?':
            rest = text[i+1:]
            if rest and rest[0] == ' ' and len(rest) > 1 and (rest[1].isupper() or rest[1] in '"\''):
                before = text[last:i].strip()
                last_word = before.split()[-1] if before.split() else ""
                if last_word in ABBREVS:
                    continue
                if before and before[-1].isdigit():
                    continue
                sentence = text[last:i+1].strip()
                if sentence and len(sentence) > 5:
                    sentences.append(sentence)
                last = i + 1
    remaining = text[last:].strip()
    return sentences, remaining


# ─── Streaming Pipeline ──────────────────────────────────

async def stream_and_speak(api_key: str, agent: str, text: str):
    """
    THE core pipeline. Streams Claude, extracts sentences, generates TTS
    per-sentence with overlapped playback.

    Timeline:
      0ms:    Start streaming Claude API
      ~900ms: First token arrives
      ~1400ms: First complete sentence extracted
      ~1800ms: First audio generated, START PLAYING
      ~2000ms: User hears first words while Claude still streaming
    """
    import httpx

    agent_cfg = AGENTS.get(agent, AGENTS["bob"])
    voice = agent_cfg["voice"]
    speed = agent_cfg["speed"]
    role = agent_cfg["role"]

    system = (
        f"You are {agent.title()}, {role} Part of The 747 Lab. "
        f"Respond in 2-3 concise spoken sentences. "
        f"No markdown, no lists, no formatting. Speak naturally. "
        f"Sign off with your name."
    )

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": CLAUDE_MODEL, "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": text}],
        "stream": True,
    }

    t_start = time.time()

    # Queue for sentences ready for TTS
    sentence_queue = queue.Queue()

    # TTS + playback thread — runs in parallel with LLM streaming
    def tts_worker():
        while True:
            item = sentence_queue.get()
            if item is None:
                break
            idx, sentence_text = item
            try:
                t_gen = time.time()
                samples, sr = tts_generate(sentence_text, voice, speed)
                gen_ms = (time.time() - t_gen) * 1000
                if idx == 0:
                    first_audio_ms = (time.time() - t_start) * 1000
                    print(f"  [first audio: {first_audio_ms:.0f}ms | tts: {gen_ms:.0f}ms]")
                play_audio(samples, sr)
            except Exception as e:
                print(f"  [tts error: {e}]")

    tts_thread = threading.Thread(target=tts_worker, daemon=True)
    tts_thread.start()

    # Stream LLM and extract sentences
    text_buffer = ""
    sentence_idx = 0
    full_response = ""

    print(f"\n  {agent.upper()}: ", end="", flush=True)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", "https://api.anthropic.com/v1/messages",
                                      headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "content_block_delta":
                        chunk = event.get("delta", {}).get("text", "")
                        if chunk:
                            full_response += chunk
                            sys.stdout.write(chunk)
                            sys.stdout.flush()
                            text_buffer += chunk

                            sentences, text_buffer = extract_sentences(text_buffer)
                            for s in sentences:
                                sentence_queue.put((sentence_idx, s))
                                sentence_idx += 1
    except Exception as e:
        print(f"\n  [api error: {e}]")

    # Flush remaining text as final sentence
    remaining = text_buffer.strip()
    if remaining and len(remaining) > 3:
        sentence_queue.put((sentence_idx, remaining))

    # Signal TTS thread to finish
    sentence_queue.put(None)
    tts_thread.join()

    total_ms = (time.time() - t_start) * 1000
    print(f"\n  [{total_ms:.0f}ms total | {sentence_idx + (1 if remaining else 0)} sentences]\n")


# ─── Main Loop ────────────────────────────────────────────

def main():
    api_key = load_api_key()
    if not api_key:
        print("ERROR: No Anthropic API key. Set ANTHROPIC_API_KEY.")
        sys.exit(1)

    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║     VII — Just Speak.                ║")
    print("  ║     Developed by The 747 Lab         ║")
    print("  ╚══════════════════════════════════════╝")
    print()

    # Load models
    t = time.time()
    load_whisper()
    print(f"  Whisper ready ({time.time()-t:.1f}s)")

    t = time.time()
    load_kokoro()
    print(f"  Kokoro ready ({time.time()-t:.1f}s)")

    agent = DEFAULT_AGENT
    print(f"\n  Agent: {agent.upper()} ({AGENTS[agent]['role']})")
    print(f"  Hold SPACE to speak. Release to get a response.")
    print(f"  Say an agent name to switch: Bob, Falcon, Ace, Pixi, Buzz")
    print(f"  Type 'q' to quit.\n")

    # Keyboard listener for SPACE hold-to-talk
    try:
        import sounddevice as sd  # verify it works
    except Exception as e:
        print(f"  Audio error: {e}")
        print(f"  Falling back to text input mode.\n")
        text_mode(api_key, agent)
        return

    # Use text mode for now — keyboard hold detection needs pynput or similar
    # TODO: Add pynput for SPACE hold-to-talk
    print("  [Voice mode requires pynput — using text input for now]")
    print("  Type your message, or 'bob, ...' to dispatch.\n")
    text_mode(api_key, agent)


def text_mode(api_key: str, agent: str):
    """Text input fallback — type messages, hear responses."""
    while True:
        try:
            user_input = input("  You > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input:
            continue
        if user_input.lower() in ("q", "quit", "exit"):
            break

        detected, cleaned = detect_agent(user_input)
        if detected:
            agent = detected
            user_input = cleaned if cleaned else user_input
            print(f"  [switched to {agent.upper()}]")

        asyncio.run(stream_and_speak(api_key, agent, user_input))

    print("\n  VII stopped. Just speak.\n")


if __name__ == "__main__":
    main()
