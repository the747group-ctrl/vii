"""
VII Two — Telegram Remote Control Bot.
Control your laptop from your phone via Telegram.

Features:
- /screen — Screenshot of current display
- /click x,y — Click at coordinates
- /type text — Type text via AppleScript
- /key combo — Press key combination (e.g., cmd+space)
- /agent name — Switch active agent
- /status — VII system status
- Voice messages — Full round-trip (voice→STT→LLM→TTS→voice)

Ported from DecisionsAI's Telegram integration pattern.
Security: Only responds to authorized chat_id.
"""

import asyncio
import base64
import hashlib
import hmac
import io
import json
import logging
import os
import secrets
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("vii.remote.telegram")

# Security
AUTHORIZED_CHAT_ID = os.environ.get("VII_TELEGRAM_CHAT_ID", "")
HMAC_SECRET = os.environ.get("VII_HMAC_SECRET", secrets.token_hex(32))


def is_authorized(chat_id: int) -> bool:
    """Only respond to the founder's chat."""
    if not AUTHORIZED_CHAT_ID:
        logger.warning("VII_TELEGRAM_CHAT_ID not set — rejecting all messages")
        return False
    return str(chat_id) == str(AUTHORIZED_CHAT_ID)


class VIITelegramBot:
    """
    Telegram bot for remote VII control.
    Uses python-telegram-bot (async).
    """

    def __init__(self, token: Optional[str] = None, pipeline=None):
        self.token = token or os.environ.get("VII_TELEGRAM_TOKEN", "")
        self.pipeline = pipeline  # Reference to VIIPipelineOrchestrator
        self._app = None

    async def start(self):
        """Start the Telegram bot."""
        try:
            from telegram import Update
            from telegram.ext import (
                ApplicationBuilder, CommandHandler,
                MessageHandler, filters,
            )
        except ImportError:
            logger.error("python-telegram-bot not installed. Run: pip install python-telegram-bot")
            return

        self._app = (
            ApplicationBuilder()
            .token(self.token)
            .build()
        )

        # Command handlers
        self._app.add_handler(CommandHandler("screen", self._cmd_screen))
        self._app.add_handler(CommandHandler("click", self._cmd_click))
        self._app.add_handler(CommandHandler("type", self._cmd_type))
        self._app.add_handler(CommandHandler("key", self._cmd_key))
        self._app.add_handler(CommandHandler("agent", self._cmd_agent))
        self._app.add_handler(CommandHandler("status", self._cmd_status))
        self._app.add_handler(CommandHandler("start", self._cmd_start))

        # Voice message handler
        self._app.add_handler(MessageHandler(filters.VOICE, self._handle_voice))

        # Text message handler (pass to pipeline)
        self._app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self._handle_text,
        ))

        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()
        logger.info("VII Telegram bot started")

    async def stop(self):
        """Stop the bot."""
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

    # --- Command Handlers ---

    async def _cmd_start(self, update, context):
        """Welcome message."""
        if not is_authorized(update.effective_chat.id):
            return
        await update.message.reply_text(
            "VII Two Remote Control\n\n"
            "/screen - Screenshot\n"
            "/click x,y - Click\n"
            "/type text - Type\n"
            "/key combo - Key press\n"
            "/agent name - Switch agent\n"
            "/status - System status\n\n"
            "Send voice message for full VII interaction.\n"
            "Send text to chat with current agent.\n\n"
            "Developed by The 747 Lab"
        )

    async def _cmd_screen(self, update, context):
        """Capture and send screenshot."""
        if not is_authorized(update.effective_chat.id):
            return

        await update.message.reply_text("Capturing...")

        screenshot = await capture_screenshot()
        if screenshot:
            await update.message.reply_photo(
                photo=screenshot,
                caption=f"Screen @ {time.strftime('%H:%M:%S')}",
            )
        else:
            await update.message.reply_text("Screenshot failed.")

    async def _cmd_click(self, update, context):
        """Click at coordinates. Usage: /click 500,300"""
        if not is_authorized(update.effective_chat.id):
            return

        args = context.args
        if not args:
            await update.message.reply_text("Usage: /click x,y")
            return

        try:
            coords = args[0].split(",")
            x, y = int(coords[0]), int(coords[1])
        except (ValueError, IndexError):
            await update.message.reply_text("Usage: /click x,y (e.g., /click 500,300)")
            return

        success = await click_at(x, y)
        if success:
            # Send screenshot after click
            await asyncio.sleep(0.3)
            screenshot = await capture_screenshot()
            if screenshot:
                await update.message.reply_photo(
                    photo=screenshot,
                    caption=f"Clicked ({x}, {y})",
                )
        else:
            await update.message.reply_text(f"Click failed at ({x}, {y})")

    async def _cmd_type(self, update, context):
        """Type text. Usage: /type Hello world"""
        if not is_authorized(update.effective_chat.id):
            return

        text = " ".join(context.args) if context.args else ""
        if not text:
            await update.message.reply_text("Usage: /type Hello world")
            return

        success = await type_text(text)
        status = "Typed" if success else "Type failed"
        await update.message.reply_text(f"{status}: {text[:50]}")

    async def _cmd_key(self, update, context):
        """Press key combination. Usage: /key cmd+space"""
        if not is_authorized(update.effective_chat.id):
            return

        combo = " ".join(context.args) if context.args else ""
        if not combo:
            await update.message.reply_text("Usage: /key cmd+space")
            return

        success = await press_key_combo(combo)
        status = "Pressed" if success else "Key press failed"
        await update.message.reply_text(f"{status}: {combo}")

    async def _cmd_agent(self, update, context):
        """Switch agent. Usage: /agent bob"""
        if not is_authorized(update.effective_chat.id):
            return

        name = context.args[0].lower() if context.args else ""
        valid = ["bob", "falcon", "ace", "pixi", "buzz", "claude"]
        if name not in valid:
            await update.message.reply_text(
                f"Usage: /agent <name>\nAvailable: {', '.join(valid)}"
            )
            return

        if self.pipeline:
            await self.pipeline.inject_text(f"Switch to {name}", agent=name)
        await update.message.reply_text(f"Agent: {name.title()}")

    async def _cmd_status(self, update, context):
        """VII system status."""
        if not is_authorized(update.effective_chat.id):
            return

        status = (
            "VII Two Status\n"
            f"Pipeline: {'Running' if self.pipeline else 'Not connected'}\n"
            f"Time: {time.strftime('%H:%M:%S %Z')}\n"
            f"Uptime: Active"
        )
        await update.message.reply_text(status)

    # --- Message Handlers ---

    async def _handle_voice(self, update, context):
        """Handle voice message — full VII round-trip."""
        if not is_authorized(update.effective_chat.id):
            return

        await update.message.reply_chat_action("record_voice")

        # Download voice message
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            ogg_path = f.name
            await file.download_to_drive(ogg_path)

        # Convert OGG to WAV (16kHz mono for Whisper)
        wav_path = ogg_path.replace(".ogg", ".wav")
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-i", ogg_path,
                "-ar", "16000", "-ac", "1", wav_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except Exception as e:
            logger.error(f"ffmpeg conversion failed: {e}")
            await update.message.reply_text("Audio conversion failed.")
            return
        finally:
            os.unlink(ogg_path)

        # TODO: Transcribe WAV, inject into pipeline, capture response, TTS, send back
        # For now, send to pipeline as text (placeholder)
        await update.message.reply_text(
            "Voice received. Full voice round-trip coming in Phase 2B."
        )

        # Clean up
        if os.path.exists(wav_path):
            os.unlink(wav_path)

    async def _handle_text(self, update, context):
        """Handle text message — send to pipeline."""
        if not is_authorized(update.effective_chat.id):
            return

        text = update.message.text
        if not text:
            return

        await update.message.reply_chat_action("typing")

        if self.pipeline:
            await self.pipeline.inject_text(text)
            await update.message.reply_text("Sent to VII.")
        else:
            await update.message.reply_text("Pipeline not connected.")


# --- System Control Functions (macOS) ---

async def capture_screenshot() -> Optional[io.BytesIO]:
    """Capture screenshot, return as WebP BytesIO."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        png_path = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            "screencapture", "-x", "-C", png_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()

        if not os.path.exists(png_path):
            return None

        # Convert to WebP for smaller size (DecisionsAI pattern)
        from PIL import Image
        img = Image.open(png_path)

        # Resize if too large (max 1920 width for Telegram)
        if img.width > 1920:
            ratio = 1920 / img.width
            img = img.resize((1920, int(img.height * ratio)), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=70)
        buf.seek(0)
        return buf

    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        return None
    finally:
        if os.path.exists(png_path):
            os.unlink(png_path)


async def click_at(x: int, y: int) -> bool:
    """Click at screen coordinates using cliclick (safer than AppleScript)."""
    try:
        # Try cliclick first (brew install cliclick)
        proc = await asyncio.create_subprocess_exec(
            "cliclick", f"c:{x},{y}",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0
    except FileNotFoundError:
        # Fall back to AppleScript
        return await _applescript_click(x, y)


async def _applescript_click(x: int, y: int) -> bool:
    """Click via AppleScript (fallback)."""
    # Use Python to move mouse and click — safer than shell interpolation
    script = (
        f'do shell script "python3 -c \\"'
        f'import Quartz; '
        f'event = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDown, ({x}, {y}), 0); '
        f'Quartz.CGEventPost(Quartz.kCGHIDEventTap, event); '
        f'event = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, ({x}, {y}), 0); '
        f'Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)'
        f'\\""'
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        return proc.returncode == 0
    except Exception as e:
        logger.error(f"Click failed: {e}")
        return False


async def type_text(text: str) -> bool:
    """Type text using AppleScript keystroke."""
    # Sanitize: only allow printable ASCII to prevent injection
    safe_text = "".join(c for c in text if 32 <= ord(c) <= 126 and c != '"' and c != '\\')
    if not safe_text:
        return False

    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e",
            f'tell application "System Events" to keystroke "{safe_text}"',
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        return proc.returncode == 0
    except Exception as e:
        logger.error(f"Type failed: {e}")
        return False


async def press_key_combo(combo: str) -> bool:
    """Press key combination. E.g., 'cmd+space', 'ctrl+c'."""
    parts = combo.lower().split("+")
    key = parts[-1].strip()
    modifiers = [p.strip() for p in parts[:-1]]

    # Map modifier names to AppleScript
    mod_map = {
        "cmd": "command down", "command": "command down",
        "ctrl": "control down", "control": "control down",
        "alt": "option down", "option": "option down",
        "shift": "shift down",
    }

    # Map special key names to key codes
    key_code_map = {
        "space": 49, "return": 36, "enter": 36, "tab": 48,
        "escape": 53, "esc": 53, "delete": 51, "backspace": 51,
        "up": 126, "down": 125, "left": 123, "right": 124,
        "f1": 122, "f2": 120, "f3": 99, "f4": 118,
    }

    using_parts = [mod_map[m] for m in modifiers if m in mod_map]
    using_clause = f" using {{{', '.join(using_parts)}}}" if using_parts else ""

    if key in key_code_map:
        script = f'tell application "System Events" to key code {key_code_map[key]}{using_clause}'
    elif len(key) == 1 and key.isalnum():
        script = f'tell application "System Events" to keystroke "{key}"{using_clause}'
    else:
        return False

    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        return proc.returncode == 0
    except Exception as e:
        logger.error(f"Key combo failed: {e}")
        return False
