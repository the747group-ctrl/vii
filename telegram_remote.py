#!/usr/bin/env python3
"""
VII Telegram Remote — Control your Mac from your phone.

Setup:
  1. Message @BotFather on Telegram: /newbot → get token
  2. Run: VII_TELEGRAM_TOKEN=<token> ./tts-venv/bin/python3 telegram_remote.py
  3. Message the bot /start — it shows your chat ID
  4. Restart with: VII_TELEGRAM_CHAT_ID=<id> for security lock

Commands: /screen /click /type /key /agent /ask + voice messages
Developed by The 747 Lab
"""

import asyncio
import io
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [VII] %(message)s")
logger = logging.getLogger("vii.telegram")

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
CLAUDE_MODEL = "claude-sonnet-4-20250514"

AGENTS = {
    "vii": {"voice": "af_heart", "speed": 1.1, "role": "Your voice AI. Warm, insightful."},
    "bob": {"voice": "am_onyx", "speed": 1.0, "role": "Lead strategist."},
    "falcon": {"voice": "am_michael", "speed": 0.95, "role": "Intelligence analyst."},
    "pixi": {"voice": "af_heart", "speed": 1.25, "role": "Creative director."},
}

current_agent = "vii"


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


API_KEY = load_api_key()

_whisper = None
_kokoro = None


def get_whisper():
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        model_dir = os.path.join(MODELS_DIR, "models--Systran--faster-whisper-small", "snapshots")
        if os.path.exists(model_dir):
            snaps = os.listdir(model_dir)
            if snaps:
                _whisper = WhisperModel(os.path.join(model_dir, snaps[0]), device="cpu", compute_type="int8")
                return _whisper
        _whisper = WhisperModel("small", device="cpu", compute_type="int8")
    return _whisper


def get_kokoro():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        _kokoro = Kokoro(
            os.path.join(MODELS_DIR, "kokoro", "kokoro-v1.0.onnx"),
            os.path.join(MODELS_DIR, "kokoro", "voices-v1.0.bin"),
        )
    return _kokoro


async def ask_claude(text, agent="vii"):
    import httpx
    cfg = AGENTS.get(agent, AGENTS["vii"])
    system = (
        f"You are VII, a voice AI by The 747 Lab. {cfg['role']} "
        f"Respond in 2-3 concise spoken sentences. No markdown. Speak naturally."
    )
    headers = {"x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    payload = {"model": CLAUDE_MODEL, "max_tokens": 250, "system": system,
               "messages": [{"role": "user", "content": text}]}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("content", [{}])[0].get("text", "No response.")


def generate_tts_ogg(text, voice, speed):
    kokoro = get_kokoro()
    clean = re.sub(r'[`#*]', '', text).replace('%', ' percent').replace('&', ' and ')
    clean = clean.replace('\u2019', "'").replace('\u2018', "'")
    samples, sr = kokoro.create(clean, voice=voice, speed=speed, lang="en-us")
    import soundfile as sf
    wav_path = tempfile.mktemp(suffix=".wav")
    sf.write(wav_path, samples, sr)
    ogg_path = tempfile.mktemp(suffix=".ogg")
    subprocess.run(["ffmpeg", "-y", "-i", wav_path, "-c:a", "libopus", "-b:a", "64k", ogg_path],
                   capture_output=True)
    os.unlink(wav_path)
    return ogg_path if os.path.exists(ogg_path) else ""


async def capture_screenshot():
    png = tempfile.mktemp(suffix=".png")
    proc = await asyncio.create_subprocess_exec("screencapture", "-x", "-C", png,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    await proc.wait()
    if not os.path.exists(png):
        return None
    from PIL import Image
    img = Image.open(png)
    if img.width > 1920:
        ratio = 1920 / img.width
        img = img.resize((1920, int(img.height * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=70)
    buf.seek(0)
    os.unlink(png)
    return buf


async def run_bot():
    from telegram import Update
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

    token = os.environ.get("VII_TELEGRAM_TOKEN", "")
    auth_chat = os.environ.get("VII_TELEGRAM_CHAT_ID", "")

    if not token:
        print("Set VII_TELEGRAM_TOKEN. Get from @BotFather: /newbot")
        sys.exit(1)

    def is_auth(update):
        if not auth_chat:
            return True
        return str(update.effective_chat.id) == auth_chat

    async def cmd_start(update, ctx):
        cid = update.effective_chat.id
        await update.message.reply_text(
            f"VII Remote Control\n\nYour Chat ID: {cid}\n\n"
            f"/screen - Screenshot\n/click x,y - Click\n/type text - Type\n"
            f"/key cmd+c - Key combo\n/ask text - Ask VII\n/agent name - Switch\n\n"
            f"Send voice message for voice response.\nThe 747 Lab")

    async def cmd_screen(update, ctx):
        if not is_auth(update): return
        await update.message.reply_text("Capturing...")
        img = await capture_screenshot()
        if img:
            await update.message.reply_photo(photo=img, caption=f"Screen @ {time.strftime('%H:%M:%S')}")

    async def cmd_click(update, ctx):
        if not is_auth(update): return
        try:
            parts = ctx.args[0].split(",")
            x, y = int(parts[0]), int(parts[1])
        except (IndexError, ValueError):
            await update.message.reply_text("Usage: /click x,y")
            return
        proc = await asyncio.create_subprocess_exec("osascript", "-e",
            f'tell application "System Events" to click at {{{x}, {y}}}',
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await proc.wait()
        await asyncio.sleep(0.3)
        img = await capture_screenshot()
        if img:
            await update.message.reply_photo(photo=img, caption=f"Clicked ({x},{y})")

    async def cmd_type(update, ctx):
        if not is_auth(update): return
        text = " ".join(ctx.args) if ctx.args else ""
        if not text:
            await update.message.reply_text("Usage: /type Hello")
            return
        safe = "".join(c for c in text if 32 <= ord(c) <= 126 and c not in ('"', '\\'))
        proc = await asyncio.create_subprocess_exec("osascript", "-e",
            f'tell application "System Events" to keystroke "{safe}"',
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await proc.wait()
        await update.message.reply_text(f"Typed: {text[:50]}")

    async def cmd_key(update, ctx):
        if not is_auth(update): return
        combo = " ".join(ctx.args) if ctx.args else ""
        if not combo:
            await update.message.reply_text("Usage: /key cmd+c")
            return
        parts = combo.lower().split("+")
        key = parts[-1].strip()
        mod_map = {"cmd": "command down", "ctrl": "control down", "alt": "option down", "shift": "shift down"}
        key_codes = {"space": 49, "return": 36, "tab": 48, "escape": 53, "delete": 51}
        mods = [mod_map[p.strip()] for p in parts[:-1] if p.strip() in mod_map]
        using = f" using {{{', '.join(mods)}}}" if mods else ""
        if key in key_codes:
            script = f'tell application "System Events" to key code {key_codes[key]}{using}'
        elif len(key) == 1:
            script = f'tell application "System Events" to keystroke "{key}"{using}'
        else:
            await update.message.reply_text(f"Unknown key: {key}")
            return
        proc = await asyncio.create_subprocess_exec("osascript", "-e", script,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await proc.wait()
        await update.message.reply_text(f"Pressed: {combo}")

    async def cmd_agent(update, ctx):
        if not is_auth(update): return
        global current_agent
        name = ctx.args[0].lower() if ctx.args else ""
        if name not in AGENTS:
            await update.message.reply_text(f"Agents: {', '.join(AGENTS.keys())}")
            return
        current_agent = name
        await update.message.reply_text(f"Agent: {name.upper()}")

    async def cmd_ask(update, ctx):
        if not is_auth(update): return
        text = " ".join(ctx.args) if ctx.args else ""
        if not text:
            await update.message.reply_text("Usage: /ask What should I focus on?")
            return
        await update.message.reply_chat_action("typing")
        response = await ask_claude(text, current_agent)
        await update.message.reply_text(f"{current_agent.upper()}: {response}")
        cfg = AGENTS.get(current_agent, AGENTS["vii"])
        await update.message.reply_chat_action("record_voice")
        ogg = generate_tts_ogg(response, cfg["voice"], cfg["speed"])
        if ogg:
            with open(ogg, "rb") as f:
                await update.message.reply_voice(voice=f)
            os.unlink(ogg)

    async def handle_voice(update, ctx):
        if not is_auth(update): return
        await update.message.reply_chat_action("record_voice")
        voice = update.message.voice
        file = await ctx.bot.get_file(voice.file_id)
        ogg_in = tempfile.mktemp(suffix=".ogg")
        await file.download_to_drive(ogg_in)
        wav_path = tempfile.mktemp(suffix=".wav")
        proc = await asyncio.create_subprocess_exec("ffmpeg", "-y", "-i", ogg_in, "-ar", "16000", "-ac", "1", wav_path,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await proc.wait()
        os.unlink(ogg_in)
        import soundfile as sf
        audio, sr = sf.read(wav_path)
        os.unlink(wav_path)
        whisper = get_whisper()
        segments, _ = whisper.transcribe(audio.astype(np.float32), language="en", beam_size=3)
        text = " ".join(s.text.strip() for s in segments).strip()
        if not text:
            await update.message.reply_text("Couldn't understand that.")
            return
        await update.message.reply_text(f'You: "{text}"')
        await update.message.reply_chat_action("typing")
        response = await ask_claude(text, current_agent)
        await update.message.reply_text(f"{current_agent.upper()}: {response}")
        cfg = AGENTS.get(current_agent, AGENTS["vii"])
        await update.message.reply_chat_action("record_voice")
        ogg = generate_tts_ogg(response, cfg["voice"], cfg["speed"])
        if ogg:
            with open(ogg, "rb") as f:
                await update.message.reply_voice(voice=f)
            os.unlink(ogg)

    async def handle_text(update, ctx):
        if not is_auth(update): return
        text = update.message.text
        if not text: return
        await update.message.reply_chat_action("typing")
        response = await ask_claude(text, current_agent)
        await update.message.reply_text(f"{current_agent.upper()}: {response}")

    bot = ApplicationBuilder().token(token).build()
    bot.add_handler(CommandHandler("start", cmd_start))
    bot.add_handler(CommandHandler("screen", cmd_screen))
    bot.add_handler(CommandHandler("click", cmd_click))
    bot.add_handler(CommandHandler("type", cmd_type))
    bot.add_handler(CommandHandler("key", cmd_key))
    bot.add_handler(CommandHandler("agent", cmd_agent))
    bot.add_handler(CommandHandler("ask", cmd_ask))
    bot.add_handler(MessageHandler(filters.VOICE, handle_voice))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("VII Remote LIVE. Waiting for messages.")
    await bot.initialize()
    await bot.start()
    await bot.updater.start_polling()
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await bot.updater.stop()
        await bot.stop()
        await bot.shutdown()


if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: No Anthropic API key.")
        sys.exit(1)
    print("\n  VII Remote — Control from Phone")
    print("  The 747 Lab\n")
    print("  Loading models...")
    t = time.time(); get_whisper(); print(f"  Whisper ready ({time.time()-t:.1f}s)")
    t = time.time(); get_kokoro(); print(f"  Kokoro ready ({time.time()-t:.1f}s)")
    print()
    asyncio.run(run_bot())
