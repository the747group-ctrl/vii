#!/usr/bin/env python3
"""
VII Desktop — Voice-Controlled AI Computer Assistant

Floating orb. Click to speak or go hands-free.
Controls your Mac. Remembers conversations. Sees your screen.
Global hotkey: Ctrl to toggle recording.

Run: ./tts-venv/bin/python3 desktop.py
Developed by The 747 Lab
"""

import sys
import os
import json
import time
import threading
import queue
import re
import math
import subprocess
import io

import numpy as np

from PyQt6.QtWidgets import QApplication, QWidget, QMenu, QSystemTrayIcon
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, pyqtSignal, QThread
from PyQt6.QtGui import (QPainter, QColor, QRadialGradient, QPen, QFont,
                          QIcon, QPixmap)

from core.skins import SkinManager
from core.db import new_conversation, add_message, get_messages, get_latest_conversation
from core.chat_bubble import ChatBubble

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
SETTINGS_PATH = os.path.join(CONFIG_DIR, "vii-settings.json")
CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAC_CONTROL = os.path.expanduser("~/.747lab/mac-control.sh")


def load_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    # Check vii-settings first
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH) as f:
            k = json.load(f).get("api_keys", {}).get("anthropic", "")
            if k.startswith("sk-"):
                return k
    # Check OpenClaw
    auth = os.path.expanduser("~/.openclaw/agents/main/agent/auth-profiles.json")
    if os.path.exists(auth):
        with open(auth) as f:
            k = json.load(f).get("profiles", {}).get("anthropic:manual", {}).get("token", "")
            if k.startswith("sk-"):
                return k
    return ""


def load_setting(key, default=None):
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH) as f:
            return json.load(f).get(key, default)
    return default


API_KEY = load_api_key()

import datetime
_today = datetime.date.today().strftime("%A, %B %d, %Y")

SYSTEM_PROMPT = (
    f"You are VII, a voice-controlled AI assistant by The 747 Lab.\n"
    f"Today is {_today}.\n"
    "You can control the user's Mac, see their screen, AND have natural conversations.\n\n"
    "ACTIONS — when the user asks you to DO something:\n"
    "  [ACTION: open-app Safari]\n"
    "  [ACTION: open-url https://google.com/search?q=query]\n"
    "  [ACTION: type-text Hello world]\n"
    "  [ACTION: key-combo cmd+space]\n"
    "  [ACTION: screenshot]\n"
    "  [ACTION: volume 50]\n"
    "  [ACTION: mute] or [ACTION: unmute]\n"
    "  [ACTION: quit-app AppName]\n"
    "  [ACTION: focus AppName]\n"
    "  [ACTION: notify Title Message]\n"
    "  [ACTION: scroll up] or [ACTION: scroll down]\n"
    "  [ACTION: dark-mode on] or [ACTION: dark-mode off]\n"
    "  [ACTION: clipboard-get] — read clipboard contents\n"
    "  [ACTION: clipboard-set text here] — copy text to clipboard\n"
    "  [ACTION: say message here] — speak a message aloud via macOS\n"
    "  [ACTION: wifi] — get WiFi network name\n"
    "  [ACTION: battery] — get battery percentage\n"
    "  [ACTION: apps] — list running applications\n"
    "  [ACTION: frontmost] — get the frontmost app name\n"
    "  [ACTION: browser-url] — get current browser URL\n"
    "  [ACTION: browser-title] — get current browser tab title\n\n"
    "IMPORTANT RULES:\n"
    "- You can chain multiple actions: [ACTION: open-app Safari] then [ACTION: open-url ...]\n"
    "- For web searches, use: [ACTION: open-url https://google.com/search?q=query+here]\n"
    "- When the user says 'remind me', use: [ACTION: notify VII Reminder: message]\n"
    "- When asked about clipboard, read it with [ACTION: clipboard-get] and include the result\n"
    "- Always confirm what you did in 1 spoken sentence after actions\n\n"
    "After actions, confirm briefly (1 sentence).\n"
    "For conversations, respond in 2-3 natural sentences. No markdown ever.\n"
    "Be warm, direct, genuinely helpful."
)


# ═══════════════════════════════════════════
# AI WORKER
# ═══════════════════════════════════════════

class AIWorker(QThread):
    transcript_ready = pyqtSignal(str)
    response_ready = pyqtSignal(str)
    audio_ready = pyqtSignal(object, int)
    action_executed = pyqtSignal(str, str)
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._whisper = None
        self._kokoro = None
        self._task_queue = queue.Queue()
        self._models_ready = False
        self._dictation = False
        self._speaking = False  # Echo gate: don't process while speaking
        self._conv_id = get_latest_conversation() or new_conversation("VII Session")

    @property
    def ready(self):
        return self._models_ready

    def load_models(self):
        self.status_changed.emit("Loading Whisper...")
        from faster_whisper import WhisperModel
        model_dir = os.path.join(MODELS_DIR, "models--Systran--faster-whisper-small", "snapshots")
        if os.path.exists(model_dir):
            snaps = [s for s in os.listdir(model_dir) if not s.startswith('.')]
            if snaps:
                self._whisper = WhisperModel(
                    os.path.join(model_dir, snaps[0]), device="cpu", compute_type="int8"
                )
        if not self._whisper:
            self._whisper = WhisperModel("small", device="cpu", compute_type="int8")

        self.status_changed.emit("Loading Kokoro...")
        from kokoro_onnx import Kokoro
        self._kokoro = Kokoro(
            os.path.join(MODELS_DIR, "kokoro", "kokoro-v1.0.onnx"),
            os.path.join(MODELS_DIR, "kokoro", "voices-v1.0.bin"),
        )
        self._models_ready = True
        self.status_changed.emit("Ready")

    def submit(self, audio_data):
        if self._models_ready and not self._speaking:
            self._task_queue.put(audio_data)

    def new_chat(self):
        self._conv_id = new_conversation("VII Session")

    def set_dictation_mode(self, enabled):
        self._dictation = enabled

    def run(self):
        while True:
            try:
                audio_data = self._task_queue.get(timeout=1)
            except queue.Empty:
                continue
            if audio_data is None:
                break
            try:
                self._process(audio_data)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.error_occurred.emit(str(e)[:80])
                self._speaking = False
                self.status_changed.emit("Ready")
                # Auto-recovery: ensure models still loaded
                if self._whisper is None or self._kokoro is None:
                    try:
                        self.load_models()
                    except:
                        pass

    def _capture_screen_b64(self):
        import tempfile, base64
        png = tempfile.mktemp(suffix=".png")
        subprocess.run(["screencapture", "-x", "-C", png], capture_output=True)
        if not os.path.exists(png):
            return None
        from PIL import Image
        img = Image.open(png)
        if img.width > 1280:
            ratio = 1280 / img.width
            img = img.resize((1280, int(img.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=50)
        b64 = __import__('base64').b64encode(buf.getvalue()).decode()
        os.unlink(png)
        return b64

    def _process(self, audio_data):
        import sounddevice as sd

        # ── STT ──
        self.status_changed.emit("Transcribing...")
        t_start = time.time()
        segments, _ = self._whisper.transcribe(
            audio_data, language="en", beam_size=3,
            no_speech_threshold=0.5,
            initial_prompt="VII, open Safari, search for, take a screenshot, what's on my screen, Bob, Falcon, hello world",
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        stt_ms = (time.time() - t_start) * 1000

        if not text or len(text) < 2:
            self.status_changed.emit("Ready")
            return

        # Filter hallucinations more aggressively
        lower = text.lower().strip().rstrip('.')
        hallucinations = {
            "thank you", "thanks", "bye", "you", "the end",
            "thank you for watching", "subscribe", "you you",
            "thanks for watching", "please subscribe", "goodbye",
            "so", "okay", "ok", "um", "uh", "hmm", "ah", "oh",
        }
        stripped = re.sub(r'[^\w\s]', '', lower).strip()
        if stripped in hallucinations or (len(stripped) < 4 and stripped.isalpha()):
            self.status_changed.emit("Ready")
            return
        # Repetitive pattern
        words = stripped.split()
        if len(words) >= 2 and all(w == words[0] for w in words):
            self.status_changed.emit("Ready")
            return

        self.transcript_ready.emit(text)

        # ── Reminders ──
        if "remind me" in lower or "set a timer" in lower or "set a reminder" in lower:
            from core.reminders import reminders
            delay = reminders.parse_delay(text)
            if delay:
                # Extract the reminder message (re already imported at module level)
                msg_match = re.search(r'(?:remind me|timer|reminder)\s+(?:in\s+\d+\s+\w+\s+)?(?:to\s+)?(.+)', lower)
                msg = msg_match.group(1).strip() if msg_match else text
                reminders.add(msg, delay)
                mins = delay // 60
                self.response_ready.emit(f"Reminder set for {mins} minutes: {msg}")
                self._speak_text(f"Got it. I'll remind you in {mins} minutes.",
                                 load_setting("tts_voice", "am_onyx"),
                                 load_setting("tts_speed", 1.0),
                                 __import__('sounddevice'))
                self.status_changed.emit("Ready")
                return

        # ── Dictation mode ──
        if self._dictation:
            self.status_changed.emit("Typing...")
            safe = "".join(c for c in text if 32 <= ord(c) <= 126 and c not in ('"', '\\'))
            if safe:
                subprocess.run(
                    ["osascript", "-e", f'tell application "System Events" to keystroke "{safe}"'],
                    capture_output=True, timeout=5,
                )
            self.response_ready.emit(f"Typed: {safe[:60]}")
            self.status_changed.emit("Ready")
            return

        self.status_changed.emit("Thinking...")

        # ── Vision check ──
        vision_triggers = ["screen", "see", "look at", "what's this", "what is this",
                           "show me", "read this", "what do you see", "analyze", "what's open"]
        is_vision = any(t in lower for t in vision_triggers)
        screenshot_b64 = None
        if is_vision:
            self.status_changed.emit("Looking at screen...")
            screenshot_b64 = self._capture_screen_b64()

        # ── LLM ──
        import httpx

        add_message(self._conv_id, "user", text)
        messages = get_messages(self._conv_id, limit=20)

        # Vision: replace last message with image + text
        if screenshot_b64 and messages:
            messages[-1] = {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": screenshot_b64}},
                    {"type": "text", "text": text},
                ],
            }

        # Load provider settings
        llm_provider = load_setting("llm_provider", "anthropic")
        llm_model = load_setting("llm_model", CLAUDE_MODEL)
        ollama_url = load_setting("ollama_url", "http://127.0.0.1:11434")
        tts_voice = load_setting("tts_voice", "am_onyx")
        tts_speed = load_setting("tts_speed", 1.0)

        t_llm = time.time()
        response_text = ""

        if llm_provider == "ollama":
            # Ollama streaming — overlapped TTS like Claude
            sentence_buffer = ""
            first_audio = False

            with httpx.Client(timeout=60.0) as client:
                with client.stream(
                    "POST", f"{ollama_url}/api/chat",
                    json={
                        "model": llm_model or "llama3.2:1b",
                        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                        "stream": True,
                    },
                ) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line:
                            continue
                        try:
                            chunk_data = json.loads(line)
                        except (json.JSONDecodeError, ValueError):
                            continue
                        chunk = chunk_data.get("message", {}).get("content", "")
                        if chunk:
                            response_text += chunk
                            sentence_buffer += chunk
                            # Extract sentences for overlapped TTS
                            for i, ch in enumerate(sentence_buffer):
                                if ch in '.!?' and i + 2 < len(sentence_buffer):
                                    if sentence_buffer[i+1] == ' ' and sentence_buffer[i+2].isupper():
                                        sentence = sentence_buffer[:i+1].strip()
                                        sentence_buffer = sentence_buffer[i+1:].strip()
                                        if sentence and len(sentence) > 5 and '[ACTION' not in sentence:
                                            if not first_audio:
                                                first_audio = True
                                                self.response_ready.emit(sentence)
                                                self.status_changed.emit("Speaking...")
                                            self._speak_text(sentence, tts_voice, tts_speed, sd)
                                        break

            # Speak remaining
            remaining = sentence_buffer.strip()
            if remaining and len(remaining) > 3 and '[ACTION' not in remaining:
                if not first_audio:
                    self.response_ready.emit(remaining)
                    self.status_changed.emit("Speaking...")
                self._speak_text(remaining, tts_voice, tts_speed, sd)

        else:
            # Claude streaming + overlapped TTS
            api_key = API_KEY
            sentence_buffer = ""
            first_audio = False

            with httpx.Client(timeout=30.0) as client:
                with client.stream(
                    "POST", "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": llm_model or CLAUDE_MODEL,
                        "max_tokens": 300,
                        "system": SYSTEM_PROMPT,
                        "messages": messages,
                        "stream": True,
                    },
                ) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            event = json.loads(data)
                        except (json.JSONDecodeError, ValueError):
                            continue
                        if event.get("type") == "content_block_delta":
                            chunk = event.get("delta", {}).get("text", "")
                            if chunk:
                                response_text += chunk
                                sentence_buffer += chunk

                                # Extract and speak sentences immediately
                                for i, ch in enumerate(sentence_buffer):
                                    if ch in '.!?' and i + 2 < len(sentence_buffer):
                                        next_ch = sentence_buffer[i+1:i+3]
                                        if len(next_ch) >= 2 and next_ch[0] == ' ' and next_ch[1].isupper():
                                            sentence = sentence_buffer[:i+1].strip()
                                            sentence_buffer = sentence_buffer[i+1:].strip()
                                            if sentence and len(sentence) > 5 and '[ACTION' not in sentence:
                                                if not first_audio:
                                                    first_audio = True
                                                    self.response_ready.emit(sentence)
                                                    self.status_changed.emit("Speaking...")
                                                    print(f"  [first audio: {(time.time()-t_start)*1000:.0f}ms]")
                                                self._speak_text(sentence, tts_voice, tts_speed, sd)
                                            break

            # Speak remaining
            remaining = sentence_buffer.strip()
            if remaining and len(remaining) > 3 and '[ACTION' not in remaining:
                if not first_audio:
                    self.response_ready.emit(remaining)
                    self.status_changed.emit("Speaking...")
                self._speak_text(remaining, tts_voice, tts_speed, sd)

        llm_ms = (time.time() - t_llm) * 1000
        add_message(self._conv_id, "assistant", response_text)

        # ── Execute Actions ──
        action_re = re.compile(r'\[ACTION:\s*(.+?)\]')
        for action in action_re.findall(response_text):
            parts = action.strip().split(None, 1)
            cmd = parts[0]
            args = parts[1] if len(parts) > 1 else ""
            try:
                if cmd == "clipboard-get":
                    # Read clipboard and inject into conversation context
                    result = subprocess.run(
                        ["pbpaste"], capture_output=True, text=True, timeout=5,
                    )
                    out = result.stdout.strip()[:200] or "(empty)"
                    self.action_executed.emit(cmd, f"Clipboard: {out}")
                    # Add clipboard content as context for the conversation
                    add_message(self._conv_id, "assistant", f"[Clipboard content: {out}]")
                elif cmd == "clipboard-set" and args:
                    subprocess.run(
                        ["pbcopy"], input=args.encode(), timeout=5,
                    )
                    out = f"Copied: {args[:60]}"
                    self.action_executed.emit(cmd, out)
                else:
                    result = subprocess.run(
                        [MAC_CONTROL, cmd] + ([args] if args else []),
                        capture_output=True, text=True, timeout=10,
                    )
                    out = result.stdout.strip()[:100] or "done"
                    self.action_executed.emit(cmd, out)
                # macOS notification for visible actions
                if cmd in ("open-app", "open-url", "screenshot", "notify"):
                    subprocess.Popen(["osascript", "-e",
                        f'display notification "{out}" with title "VII" sound name "Glass"'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                self.action_executed.emit(cmd, f"error: {e}")

        print(f"  [{stt_ms:.0f}ms stt | {llm_ms:.0f}ms llm | total: {(time.time()-t_start)*1000:.0f}ms]")
        self.status_changed.emit("Ready")

    def _speak_text(self, text, voice, speed, sd):
        """Generate TTS and play. Sets echo gate to prevent self-triggering."""
        self._speaking = True
        try:
            clean = re.sub(r'[`#*\[\]]', '', text)
            clean = clean.replace('%', ' percent').replace('&', ' and ')
            clean = clean.replace('\u2019', "'").replace('\u2018', "'")
            if len(clean) > 400:
                clean = clean[:400] + "."
            if not clean.strip():
                return
            samples, sr = self._kokoro.create(clean, voice=voice, speed=speed, lang="en-us")
            sd.play(samples, sr)
            sd.wait()
        finally:
            self._speaking = False


# ═══════════════════════════════════════════
# ORB WIDGET
# ═══════════════════════════════════════════

class OrbWidget(QWidget):
    recording_stopped = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Skin
        self.skin_manager = SkinManager()
        self.skin = self.skin_manager.active_skin()
        self.orb_size = self.skin.size
        self.setFixedSize(self.orb_size + 48, self.orb_size + 50)

        # State
        self.state = "loading"
        self.glow_phase = 0.0
        self.audio_level = 0.0
        self.status_text = "Loading..."
        self._models_ready = False
        self._dictation_mode = False

        # Interaction
        self._drag_start = None
        self._drag_moved = False
        self._recording = False
        self._audio_chunks = []
        self._audio_stream = None

        # Hands-free
        self.hands_free = False
        self.wake_word_active = False
        self._wake_detector = None
        self._vad_speaking = False
        self._vad_silence_frames = 0
        self._vad_speech_frames = 0
        self._continuous_stream = None

        # Animation
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

        # Re-assert on-top every 5s
        self._top_timer = QTimer()
        self._top_timer.timeout.connect(lambda: self.raise_())
        self._top_timer.start(5000)

        # Position — restore saved or default bottom-right
        self._pos_file = os.path.join(CONFIG_DIR, "orb-position.json")
        screen = QApplication.primaryScreen().availableGeometry()
        if os.path.exists(self._pos_file):
            try:
                with open(self._pos_file) as f:
                    pos = json.load(f)
                    self.move(pos["x"], pos["y"])
            except Exception:
                self.move(screen.width() - self.width() - 20, screen.height() - self.height() - 40)
        else:
            self.move(screen.width() - self.width() - 20, screen.height() - self.height() - 40)

    def _tick(self):
        self.glow_phase += 0.05
        self.update()

    def set_models_ready(self):
        self._models_ready = True
        self.state = "idle"
        self.status_text = "Tap to speak"
        self.update()

    def set_state(self, s):
        self.state = s
        self.update()

    def set_status(self, t):
        self.status_text = t
        self.setToolTip(t)
        self.update()

    # ── Paint ──

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width() // 2
        cy = 12 + self.orb_size // 2
        r = self.orb_size // 2

        # Glow by state
        ga = {
            "loading": 0.03 + 0.02 * math.sin(self.glow_phase * 0.5),
            "idle": 0.04 + 0.025 * math.sin(self.glow_phase),
            "listening": 0.12 + 0.08 * math.sin(self.glow_phase * 2.5) + self.audio_level * 0.1,
            "thinking": 0.08 + 0.06 * math.sin(self.glow_phase * 1.8),
            "speaking": 0.1 + self.audio_level * 0.2,
        }.get(self.state, 0.04)

        color = QColor(self.skin.color_for_state(self.state) if self.state != "loading" else "#475569")
        glow_mult = self.skin.glow_intensity if self.skin.glow else 0.3
        ga *= glow_mult

        # Outer glow
        gc = QColor(color)
        gc.setAlphaF(min(ga, 1.0))
        grad = QRadialGradient(cx, cy, r * 2.2)
        grad.setColorAt(0, gc)
        grad.setColorAt(0.5, QColor(gc.red(), gc.green(), gc.blue(), int(min(ga, 1.0) * 80)))
        grad.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPoint(cx, cy), int(r * 2.2), int(r * 2.2))

        # ── Siri-inspired animated orb ──
        t = self.glow_phase

        # Multiple layered gradients that shift and breathe
        # Layer 1: Deep base
        base = QRadialGradient(cx + math.sin(t * 0.7) * 4, cy + math.cos(t * 0.5) * 4, r * 1.05)
        if self.state == "listening":
            base.setColorAt(0, QColor(220, 80, 80, 200))
            base.setColorAt(0.6, QColor(180, 40, 60, 160))
            base.setColorAt(1, QColor(100, 20, 40, 80))
        elif self.state == "thinking":
            base.setColorAt(0, QColor(120, 100, 220, 200))
            base.setColorAt(0.6, QColor(80, 60, 180, 160))
            base.setColorAt(1, QColor(40, 30, 120, 80))
        elif self.state == "speaking":
            base.setColorAt(0, QColor(40, 200, 180, 200))
            base.setColorAt(0.6, QColor(20, 160, 140, 160))
            base.setColorAt(1, QColor(10, 100, 90, 80))
        else:
            # Idle — subtle warm breathing
            pulse = 0.7 + 0.3 * math.sin(t * 0.8)
            base.setColorAt(0, QColor(int(60 * pulse), int(50 * pulse), int(80 * pulse), 200))
            base.setColorAt(0.6, QColor(int(35 * pulse), int(30 * pulse), int(55 * pulse), 160))
            base.setColorAt(1, QColor(15, 12, 25, 100))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(base)
        p.drawEllipse(QPoint(cx, cy), r, r)

        # Layer 2: Flowing highlight (moves around the orb like Siri)
        highlight_angle = t * 1.2
        hx = cx + math.cos(highlight_angle) * r * 0.3
        hy = cy + math.sin(highlight_angle) * r * 0.3
        highlight = QRadialGradient(hx, hy, r * 0.6)
        if self.state == "listening":
            highlight.setColorAt(0, QColor(255, 140, 120, 100))
        elif self.state == "thinking":
            highlight.setColorAt(0, QColor(160, 140, 255, 100))
        elif self.state == "speaking":
            highlight.setColorAt(0, QColor(100, 255, 220, 100))
        else:
            highlight.setColorAt(0, QColor(140, 120, 180, int(40 + 30 * math.sin(t))))
        highlight.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(highlight)
        p.drawEllipse(QPoint(cx, cy), r, r)

        # Layer 3: Second flowing highlight (opposite direction)
        h2_angle = -t * 0.9 + 2.0
        h2x = cx + math.cos(h2_angle) * r * 0.25
        h2y = cy + math.sin(h2_angle) * r * 0.25
        h2 = QRadialGradient(h2x, h2y, r * 0.5)
        if self.state == "listening":
            h2.setColorAt(0, QColor(255, 200, 100, 70))
        elif self.state == "thinking":
            h2.setColorAt(0, QColor(200, 100, 255, 70))
        elif self.state == "speaking":
            h2.setColorAt(0, QColor(100, 220, 255, 70))
        else:
            h2.setColorAt(0, QColor(100, 80, 160, int(25 + 20 * math.sin(t * 1.3))))
        h2.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(h2)
        p.drawEllipse(QPoint(cx, cy), r, r)

        # Edge ring — subtle border
        ring_alpha = 0.15 + ga * 0.5
        rc = QColor(color)
        rc.setAlphaF(min(ring_alpha, 0.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(rc, 1.0))
        p.drawEllipse(QPoint(cx, cy), r, r)

        # ── State-specific effects ──

        # Listening: audio-reactive ring expansion
        if self.state == "listening" and self.audio_level > 0.01:
            for ring in range(3):
                ring_r = r + 4 + ring * 6 + self.audio_level * 15
                ring_a = max(0, 0.3 - ring * 0.1) * self.audio_level * 3
                rc2 = QColor(220, 100, 80, int(min(ring_a, 1.0) * 255))
                p.setPen(QPen(rc2, 1.5))
                p.setBrush(Qt.BrushStyle.NoPen)
                p.drawEllipse(QPoint(cx, cy), int(ring_r), int(ring_r))

        # Thinking: orbiting particles
        if self.state == "thinking":
            for i in range(4):
                angle = t * 2.5 + i * (math.pi / 2)
                orbit_r = r + 6 + 3 * math.sin(t * 3 + i)
                px2 = cx + math.cos(angle) * orbit_r
                py2 = cy + math.sin(angle) * orbit_r
                dot_a = 0.5 + 0.5 * math.sin(t * 2 + i * 1.5)
                dc = QColor(160, 140, 255, int(dot_a * 200))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(dc)
                p.drawEllipse(QPoint(int(px2), int(py2)), 3, 3)

        # Speaking: pulsing outer ring
        if self.state == "speaking":
            pulse_r = r + 4 + 6 * math.sin(t * 4)
            sc = QColor(40, 200, 180, int(80 + 40 * math.sin(t * 3)))
            p.setPen(QPen(sc, 1.5))
            p.setBrush(Qt.BrushStyle.NoPen)
            p.drawEllipse(QPoint(cx, cy), int(pulse_r), int(pulse_r))

        # Status
        p.setPen(QColor(100, 100, 120))
        font = p.font()
        font.setPointSize(8)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        p.setFont(font)
        status = "HANDS-FREE" if self.hands_free and self.state == "idle" else self.status_text.upper()
        if self._dictation_mode and self.state == "idle":
            status = "DICTATION"
        p.drawText(QRect(0, cy + r + 6, self.width(), 18), Qt.AlignmentFlag.AlignHCenter, status)
        p.end()

    # ── Mouse ──

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_start = e.globalPosition().toPoint()
            self._drag_moved = False

    def mouseMoveEvent(self, e):
        if self._drag_start and e.buttons() & Qt.MouseButton.LeftButton:
            delta = e.globalPosition().toPoint() - self._drag_start
            if delta.manhattanLength() > 5:
                self._drag_moved = True
                self.move(self.pos() + delta)
                self._drag_start = e.globalPosition().toPoint()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and not self._drag_moved:
            if not self._models_ready:
                return
            if self.state == "speaking":
                import sounddevice as sd
                sd.stop()
                self.set_state("idle")
                self.set_status("Ready")
            elif self._recording:
                self._stop_recording()
            else:
                self._start_recording()
        elif self._drag_moved:
            # Save position after drag
            self._save_position()
        self._drag_start = None
        self._drag_moved = False

    def mouseDoubleClickEvent(self, e):
        """Double-click: trigger screen analysis."""
        if not self._models_ready:
            return
        self.set_state("thinking")
        self.set_status("Analyzing screen...")
        # Submit a tiny audio that will be transcribed as nothing,
        # but we'll handle this via a direct text submission
        # For now, emit a vision-trigger phrase
        from kokoro_onnx import Kokoro
        k = self._get_kokoro_ref()
        if k:
            audio, _ = k.create("What is on my screen right now", voice="am_onyx", speed=1.5, lang="en-us")
            self.recording_stopped.emit(audio)

    def _get_kokoro_ref(self):
        """Get kokoro from worker if available."""
        try:
            return self.parent()._worker._kokoro if hasattr(self, 'parent') else None
        except:
            return None

    def _save_position(self):
        try:
            os.makedirs(os.path.dirname(self._pos_file), exist_ok=True)
            with open(self._pos_file, "w") as f:
                json.dump({"x": self.x(), "y": self.y()}, f)
        except Exception:
            pass

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#12121e;color:#bbb;border:1px solid #252535;padding:4px;font-size:12px}"
            "QMenu::item{padding:8px 24px}"
            "QMenu::item:selected{background:#1e1e35;color:#fff}"
            "QMenu::separator{background:#252535;height:1px;margin:4px 8px}"
        )

        # Mode indicators with shortcuts
        hf = menu.addAction("Hands-Free: ON" if self.hands_free else "Hands-Free: OFF")
        hf.triggered.connect(self._toggle_hands_free)

        dt = menu.addAction("Dictation: ON" if self._dictation_mode else "Dictation: OFF")
        dt.triggered.connect(self._toggle_dictation)

        ww = menu.addAction("Wake Word: ON" if self.wake_word_active else 'Wake Word: OFF ("Hey VII")')
        ww.triggered.connect(self._toggle_wake_word)

        menu.addSeparator()
        menu.addAction("New Chat").triggered.connect(self._new_chat)

        # Recent conversations
        from core.db import get_recent_conversations
        recent = get_recent_conversations(5)
        if recent:
            hist_menu = menu.addMenu("Recent Chats")
            hist_menu.setStyleSheet(menu.styleSheet())
            for c in recent:
                label = c["title"] or f"Chat {c['id']}"
                act = hist_menu.addAction(label)
                cid = c["id"]
                act.triggered.connect(lambda checked, i=cid: self._switch_conversation(i))

        menu.addAction("Ctrl — Toggle Recording")

        menu.addSeparator()
        skin_menu = menu.addMenu("Skin")
        skin_menu.setStyleSheet(menu.styleSheet())
        for sid, sname in self.skin_manager.list_skins():
            marker = " *" if sid == self.skin_manager._active else ""
            act = skin_menu.addAction(f"{sname}{marker}")
            act.triggered.connect(lambda checked, s=sid: self._set_skin(s))

        menu.addAction("Preferences").triggered.connect(self._open_preferences)

        menu.addSeparator()
        menu.addAction("Hide VII").triggered.connect(self.hide)
        menu.addAction("Restart").triggered.connect(self._restart)
        menu.addAction("Quit VII").triggered.connect(QApplication.quit)
        menu.exec(event.globalPos())

    def _open_preferences(self):
        import webbrowser
        if not hasattr(self, '_settings_proc') or self._settings_proc is None or self._settings_proc.poll() is not None:
            python = os.path.join(PROJECT_ROOT, "tts-venv", "bin", "python3")
            if not os.path.exists(python):
                python = sys.executable
            self._settings_proc = subprocess.Popen(
                [python, os.path.join(PROJECT_ROOT, "settings_ui.py")],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            time.sleep(1)
        webbrowser.open("http://localhost:7748")

    def _new_chat(self):
        self.set_status("New chat")

    def _restart(self):
        QApplication.quit()
        subprocess.Popen([sys.executable, os.path.join(PROJECT_ROOT, "desktop.py")])

    def _toggle_dictation(self):
        self._dictation_mode = not self._dictation_mode
        self.update()

    def _set_skin(self, sid):
        if self.skin_manager.set_active(sid):
            self.skin = self.skin_manager.active_skin()
            self.orb_size = self.skin.size
            self.setFixedSize(self.orb_size + 48, self.orb_size + 50)
            self.set_status(f"Skin: {self.skin.name}")

    def _switch_conversation(self, conv_id):
        """Switch to a different conversation."""
        # This gets overridden by VIIApp
        self.set_status(f"Chat {conv_id}")

    def _toggle_wake_word(self):
        self.wake_word_active = not self.wake_word_active
        if self.wake_word_active:
            self.set_status("Say 'Hey VII'")
            # Wake word detector will be started by VIIApp which has whisper ref
        else:
            if self._wake_detector:
                self._wake_detector.stop()
                self._wake_detector = None
            self.set_status("Tap to speak")

    def _toggle_hands_free(self):
        self.hands_free = not self.hands_free
        if self.hands_free:
            self._start_hands_free()
        else:
            self._stop_hands_free()

    # ── Recording ──

    def _play_sound(self, name):
        """Play a subtle macOS system sound."""
        sounds = {
            "start": "/System/Library/Sounds/Tink.aiff",
            "stop": "/System/Library/Sounds/Pop.aiff",
            "error": "/System/Library/Sounds/Basso.aiff",
            "done": "/System/Library/Sounds/Glass.aiff",
        }
        path = sounds.get(name)
        if path and os.path.exists(path):
            subprocess.Popen(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _start_recording(self):
        import sounddevice as sd
        self._play_sound("start")
        self._recording = True
        self._audio_chunks = []
        self.set_state("listening")
        self.set_status("Listening...")
        mic_gain = load_setting("mic_gain", 10.0)

        def cb(indata, frames, t, status):
            if self._recording:
                amp = np.clip(indata.copy() * mic_gain, -1.0, 1.0)
                self._audio_chunks.append(amp)
                self.audio_level = min(float(np.sqrt(np.mean(amp ** 2))) * 3.0, 1.0)

        self._audio_stream = sd.InputStream(samplerate=16000, channels=1, dtype='float32',
                                             blocksize=1024, callback=cb)
        self._audio_stream.start()

    def _stop_recording(self):
        self._play_sound("stop")
        self._recording = False
        if self._audio_stream:
            self._audio_stream.stop()
            self._audio_stream.close()
            self._audio_stream = None
        if self._audio_chunks:
            audio = np.concatenate(self._audio_chunks, axis=0).flatten()
            rms = float(np.sqrt(np.mean(audio ** 2)))
            if rms > 0.005 and len(audio) / 16000 > 0.3:
                self.set_state("thinking")
                self.set_status("Processing...")
                self.recording_stopped.emit(audio)
                return
        self.set_state("idle")
        self.set_status("Tap to speak")
        self.audio_level = 0.0

    # ── Hands-Free ──

    def _start_hands_free(self):
        import sounddevice as sd
        self.set_status("Hands-free")
        self._vad_speaking = False
        self._vad_silence_frames = 0
        self._vad_speech_frames = 0
        self._audio_chunks = []
        mic_gain = load_setting("mic_gain", 10.0)
        vad_thresh = (load_setting("vad_sensitivity", 50) / 100.0) * 0.04 + 0.005

        def cb(indata, frames, t, status):
            amp = np.clip(indata.copy() * mic_gain, -1.0, 1.0)
            rms = float(np.sqrt(np.mean(amp ** 2)))
            self.audio_level = min(rms * 3.0, 1.0)

            if self._vad_speaking:
                self._audio_chunks.append(amp)
                if rms < vad_thresh * 0.5:
                    self._vad_silence_frames += 1
                    if self._vad_silence_frames > 10:  # ~640ms silence
                        self._vad_speaking = False
                        self._vad_silence_frames = 0
                        self._vad_speech_frames = 0
                        audio = np.concatenate(self._audio_chunks, axis=0).flatten()
                        if len(audio) > 4800:
                            self.set_state("thinking")
                            self.set_status("Processing...")
                            self.recording_stopped.emit(audio)
                        self._audio_chunks = []
                        self.audio_level = 0.0
                else:
                    self._vad_silence_frames = 0
            else:
                if rms > vad_thresh:
                    self._vad_speech_frames += 1
                    if self._vad_speech_frames > 3:
                        self._vad_speaking = True
                        self._audio_chunks = [amp]
                        self.set_state("listening")
                        self.set_status("Listening...")
                else:
                    self._vad_speech_frames = 0

        self._continuous_stream = sd.InputStream(samplerate=16000, channels=1, dtype='float32',
                                                  blocksize=1024, callback=cb)
        self._continuous_stream.start()

    def _stop_hands_free(self):
        if self._continuous_stream:
            self._continuous_stream.stop()
            self._continuous_stream.close()
            self._continuous_stream = None
        self._vad_speaking = False
        self.set_state("idle")
        self.set_status("Tap to speak")
        self.audio_level = 0.0


# ═══════════════════════════════════════════
# MAIN APP
# ═══════════════════════════════════════════

class VIIApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setApplicationName("VII")

        self.orb = OrbWidget()
        self.orb.show()

        self.bubble = ChatBubble()

        self._setup_tray()

        self.worker = AIWorker()
        self.worker.transcript_ready.connect(self._on_transcript)
        self.worker.response_ready.connect(self._on_response)
        self.worker.audio_ready.connect(lambda s, r: None)
        self.worker.action_executed.connect(lambda c, r: print(f"  [ACTION] {c} → {r}"))
        self.worker.status_changed.connect(self._on_status)
        self.worker.error_occurred.connect(self._on_error)
        self.orb.recording_stopped.connect(self.worker.submit)

        # Wire orb menu to worker
        orig_new = self.orb._new_chat
        self.orb._new_chat = lambda: (self.worker.new_chat(), orig_new())

        orig_dict = self.orb._toggle_dictation
        def _d():
            orig_dict()
            self.worker.set_dictation_mode(self.orb._dictation_mode)
        self.orb._toggle_dictation = _d

        # Wire wake word toggle
        orig_ww = self.orb._toggle_wake_word
        def _ww():
            orig_ww()
            if self.orb.wake_word_active and self.worker._whisper:
                from core.wakeword import WakeWordDetector
                mic_gain = load_setting("mic_gain", 10.0)
                self.orb._wake_detector = WakeWordDetector(self.worker._whisper, mic_gain)
                self.orb._wake_detector.start(lambda: self.orb._start_recording())
        self.orb._toggle_wake_word = _ww

        # Wire conversation switching
        self.orb._switch_conversation = lambda cid: setattr(self.worker, '_conv_id', cid) or self.orb.set_status(f"Chat {cid}")

        QTimer.singleShot(100, self._load)

        # Global hotkey — Ctrl to toggle recording from anywhere
        self._setup_global_hotkey()

    def _setup_tray(self):
        tray_path = os.path.join(PROJECT_ROOT, "assets", "vii-tray.png")
        if os.path.exists(tray_path):
            px = QPixmap(tray_path)
        else:
            px = QPixmap(16, 16)
            px.fill(QColor("#c87850"))
        self.tray = QSystemTrayIcon(QIcon(px), self.app)
        m = QMenu()
        m.setStyleSheet("QMenu{background:#12121e;color:#bbb;border:1px solid #252535}QMenu::item{padding:6px 20px}QMenu::item:selected{background:#1e1e35;color:#fff}")
        m.addAction("Show VII").triggered.connect(self.orb.show)
        m.addAction("Hide VII").triggered.connect(self.orb.hide)
        m.addSeparator()
        m.addAction("Quit").triggered.connect(self._quit)
        self.tray.setContextMenu(m)
        self.tray.setToolTip("VII — The 747 Lab")
        self.tray.show()

    def _load(self):
        threading.Thread(target=lambda: (self.worker.load_models(), self.worker.start(), self.orb.set_models_ready()), daemon=True).start()

    def _setup_global_hotkey(self):
        """Global Ctrl key to toggle recording from anywhere."""
        def _hotkey_thread():
            try:
                from pynput import keyboard
                ctrl_pressed = [False]
                ctrl_time = [0.0]

                def on_press(key):
                    if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                        if not ctrl_pressed[0]:
                            ctrl_pressed[0] = True
                            ctrl_time[0] = time.time()

                def on_release(key):
                    if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                        if ctrl_pressed[0]:
                            ctrl_pressed[0] = False
                            # Only trigger if it was a quick tap (not held for shortcut)
                            if time.time() - ctrl_time[0] < 0.4:
                                if self.orb._models_ready:
                                    if self.orb._recording:
                                        self.orb._stop_recording()
                                    elif self.orb.state in ("idle",):
                                        self.orb._start_recording()

                with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
                    listener.join()
            except Exception as e:
                print(f"  [hotkey] Global hotkey unavailable: {e}")

        threading.Thread(target=_hotkey_thread, daemon=True).start()

    def _on_transcript(self, text):
        self.orb.set_status("Heard: " + text[:30])
        orb_center = QPoint(self.orb.x() + self.orb.width() // 2, self.orb.y())
        self.bubble.show_transcript(text, orb_center)
        print(f"  You: \"{text}\"")

    def _on_response(self, text):
        self.orb.set_state("speaking")
        orb_center = QPoint(self.orb.x() + self.orb.width() // 2, self.orb.y())
        self.bubble.show_response(text, orb_center)
        print(f"  VII: {text[:100]}")

    def _on_error(self, text):
        print(f"  [ERROR] {text}")
        self.orb._play_sound("error")
        # Show brief error, auto-clear after 3s
        short = text[:40] if len(text) > 40 else text
        self.orb.set_state("idle")
        self.orb.set_status(f"Error: {short}")
        QTimer.singleShot(3000, lambda: self.orb.set_status(
            "Hands-free" if self.orb.hands_free else "Tap to speak"))

    def _on_status(self, text):
        if text == "Ready":
            self.orb.set_state("idle")
            self.orb.set_status("Hands-free" if self.orb.hands_free else ("Dictation" if self.orb._dictation_mode else "Tap to speak"))
            self.orb.audio_level = 0.0
        else:
            self.orb.set_status(text)

    def _quit(self):
        if self.orb._continuous_stream:
            self.orb._stop_hands_free()
        self.worker._task_queue.put(None)
        self.tray.hide()
        self.app.quit()

    def run(self):
        ver = "2.0.0"
        try:
            vf = os.path.join(PROJECT_ROOT, "VERSION")
            if os.path.exists(vf):
                with open(vf) as f:
                    ver = f.read().strip()
        except:
            pass

        print()
        print(f"  VII v{ver} — Voice Intelligence Interface")
        print("  The 747 Lab")
        print()
        print("  Controls:")
        print("    Click orb    — Start/stop recording")
        print("    Ctrl tap     — Toggle recording (global)")
        print("    Right-click  — Menu (hands-free, dictation, settings)")
        print("    Double-click — Analyze screen")
        print("    Drag         — Reposition orb")
        print()
        sys.exit(self.app.exec())


if __name__ == "__main__":
    # First-run onboarding
    from onboarding import needs_onboarding, OnboardingDialog
    if needs_onboarding() and not API_KEY:
        _app = QApplication(sys.argv)
        dialog = OnboardingDialog()
        if dialog.exec() == 0:  # Rejected/skipped without config
            if not load_api_key():
                print("  No API key configured. Use Preferences to set one, or use Ollama.")
                print("  Run: ./tts-venv/bin/python3 desktop.py")
                sys.exit(1)
        API_KEY = load_api_key()
        del _app

    if not API_KEY and load_setting("llm_provider") != "ollama":
        print("ERROR: No API key. Run VII to set up, or set ANTHROPIC_API_KEY.")
        sys.exit(1)

    VIIApp().run()
