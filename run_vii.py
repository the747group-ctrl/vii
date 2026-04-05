#!/usr/bin/env python3
"""
VII Two — End-to-End Voice Pipeline Runner

Type a message, hear the agent respond. Proves the streaming pipeline works.

Usage:
    python run_vii.py                    # Interactive mode
    python run_vii.py --agent bob        # Start with specific agent
    python run_vii.py --test "Hello"     # Single test message

Developed by The 747 Lab
"""
import asyncio
import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.pipeline.text_cleaner import clean_text_for_tts, extract_complete_sentences

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("vii")

AGENT_PROMPTS = {
    "bob": "You are Bob, lead strategist of The 747 Lab. Deep, authoritative. 2-3 concise spoken sentences. No markdown. Sign off with your name.",
    "falcon": "You are Falcon, intelligence analyst of The 747 Lab. Measured, precise. 2-3 sentences. Cite confidence. No markdown. Sign off.",
    "ace": "You are Ace, operations specialist of The 747 Lab. British, efficient. 2-3 sentences. Checklists mindset. No markdown. Sign off.",
    "pixi": "You are Pixi, creative director of The 747 Lab. Expressive, enthusiastic. 2-3 sentences. Visual thinker. No markdown. Sign off.",
    "buzz": "You are Buzz, content strategist of The 747 Lab. Playful, energetic. 2-3 sentences. Story-driven. No markdown. Sign off.",
    "claude": "You are Claude, a helpful assistant. 2-3 concise spoken sentences. No markdown. Conversational.",
}
AGENT_VOICES = {"bob":"am_onyx","falcon":"am_michael","ace":"bf_emma","pixi":"af_heart","buzz":"am_puck","claude":"af_nicole"}
AGENT_SPEEDS = {"bob":1.0,"falcon":0.95,"ace":1.15,"pixi":1.25,"buzz":1.3,"claude":1.1}


def load_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    auth_path = os.path.expanduser("~/.openclaw/agents/main/agent/auth-profiles.json")
    if os.path.exists(auth_path):
        with open(auth_path) as f:
            data = json.load(f)
            key = data.get("profiles", {}).get("anthropic:manual", {}).get("token", "")
            if key.startswith("sk-"):
                return key
    return ""


def detect_agent(text):
    lower = text.lower().strip()
    for name in ["bob", "falcon", "ace", "pixi", "buzz", "claude"]:
        for p in [name + ", ", name + " ", "hey " + name, "ask " + name]:
            if lower.startswith(p):
                return name, text[len(p):].strip()
    return None, text


async def stream_llm(api_key, agent, text):
    import httpx
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    payload = {
        "model": "claude-sonnet-4-20250514", "max_tokens": 250,
        "system": AGENT_PROMPTS.get(agent, AGENT_PROMPTS["claude"]),
        "messages": [{"role": "user", "content": text}], "stream": True,
    }
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
                        yield chunk


async def generate_tts(text, voice, speed, daemon_proc):
    output_path = tempfile.mktemp(suffix=".wav")
    request = json.dumps({"text": text, "voice": voice, "speed": speed, "output": output_path}) + "\n"
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, daemon_proc.stdin.write, request.encode())
    await loop.run_in_executor(None, daemon_proc.stdin.flush)
    line = await loop.run_in_executor(None, daemon_proc.stdout.readline)
    if line:
        resp = json.loads(line.decode())
        if resp.get("ok"):
            return output_path
        else:
            logger.error("TTS error: %s", resp.get("error"))
    return ""


async def play_audio(wav_path):
    if not wav_path or not os.path.exists(wav_path):
        return
    proc = await asyncio.create_subprocess_exec(
        "afplay", wav_path,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
    os.unlink(wav_path)


def start_tts_daemon():
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "tts-daemon.py")
    venv_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts-venv", "bin", "python3")
    python = venv_py if os.path.exists(venv_py) else sys.executable

    logger.info("Starting TTS daemon...")
    proc = subprocess.Popen(
        [python, script],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    line = proc.stdout.readline()
    if line:
        resp = json.loads(line.decode())
        if resp.get("ok"):
            logger.info("TTS daemon ready (loaded in %ss)", resp.get("load_time", "?"))
            return proc
    logger.error("TTS daemon failed to start")
    return None


async def process_message(api_key, agent, text, tts_daemon):
    t_start = time.time()
    voice = AGENT_VOICES.get(agent, "af_nicole")
    speed = AGENT_SPEEDS.get(agent, 1.0)

    print("\n  [%s] " % agent.upper(), end="", flush=True)

    text_buffer = ""
    sentences_to_speak = []
    t_first_sentence = None

    async for chunk in stream_llm(api_key, agent, text):
        sys.stdout.write(chunk)
        sys.stdout.flush()
        cleaned = clean_text_for_tts(chunk)
        text_buffer += cleaned
        sentences, text_buffer = extract_complete_sentences(text_buffer)
        for s in sentences:
            if t_first_sentence is None:
                t_first_sentence = time.time()
            sentences_to_speak.append(s)

    if text_buffer.strip():
        sentences_to_speak.append(text_buffer.strip())

    print()

    if not sentences_to_speak:
        return

    t_tts_start = time.time()
    if tts_daemon and tts_daemon.poll() is None:
        for i, sentence in enumerate(sentences_to_speak):
            wav = await generate_tts(sentence, voice, speed, tts_daemon)
            if wav:
                if i == 0:
                    logger.info("First audio at %dms", (time.time() - t_start) * 1000)
                await play_audio(wav)
    else:
        logger.warning("TTS daemon not running. Text only.")

    logger.info("Total: %dms | Sentences: %d", (time.time() - t_start) * 1000, len(sentences_to_speak))


async def interactive_mode(api_key, default_agent):
    tts_daemon = start_tts_daemon()

    print("\n" + "=" * 50)
    print("  VII Two — Voice Intelligence Interface")
    print("  Developed by The 747 Lab")
    print("=" * 50)
    print("  Agent: %s" % default_agent.upper())
    print("  TTS: %s" % ("Ready" if tts_daemon else "Not available (text only)"))
    print("  Type a message or 'bob, ...' to dispatch")
    print("  Type 'quit' to exit")
    print("=" * 50 + "\n")

    agent = default_agent
    while True:
        try:
            user_input = input("  You > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            break
        detected, cleaned = detect_agent(user_input)
        if detected:
            agent = detected
            user_input = cleaned if cleaned else user_input
        await process_message(api_key, agent, user_input, tts_daemon)

    if tts_daemon:
        tts_daemon.stdin.write(b'{"cmd":"quit"}\n')
        tts_daemon.stdin.flush()
        tts_daemon.terminate()
    print("\n  VII Two stopped. Just speak.\n")


def main():
    parser = argparse.ArgumentParser(description="VII Two — Voice Pipeline Runner")
    parser.add_argument("--agent", default="bob", help="Default agent")
    parser.add_argument("--test", help="Single test message")
    args = parser.parse_args()

    api_key = load_api_key()
    if not api_key:
        print("ERROR: No Anthropic API key found.")
        sys.exit(1)

    if args.test:
        async def run_test():
            daemon = start_tts_daemon()
            await process_message(api_key, args.agent, args.test, daemon)
            if daemon:
                daemon.stdin.write(b'{"cmd":"quit"}\n')
                daemon.stdin.flush()
                daemon.terminate()
        asyncio.run(run_test())
    else:
        asyncio.run(interactive_mode(api_key, args.agent))


if __name__ == "__main__":
    main()
