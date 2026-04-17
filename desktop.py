#!/usr/bin/env python3
"""
VII Desktop — Voice-Controlled AI Computer Assistant

Floating orb. Click or hold to speak. Hands-free mode available.
Controls your Mac. Remembers conversation. Multiple agents.

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

import numpy as np

from PyQt6.QtWidgets import QApplication, QWidget, QMenu, QSystemTrayIcon
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, pyqtSignal, QThread
from PyQt6.QtGui import (QPainter, QColor, QRadialGradient, QPen, QFont,
                          QIcon, QPixmap, QAction)
from core.skins import SkinManager
from core.db import new_conversation, add_message, get_messages, get_latest_conversation

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAC_CONTROL = os.path.expanduser("~/.747lab/mac-control.sh")
MIC_GAIN = 30.0  # Amplification for RODE PodMic (dynamic mic, low output)


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

SYSTEM_PROMPT = (
    "You are VII, a voice-controlled AI assistant by The 747 Lab.\n"
    "You can control the user's Mac, see their screen, AND have natural conversations.\n\n"
    "ACTIONS — when the user asks you to DO something on their computer:\n"
    "  [ACTION: open-app Safari]\n"
    "  [ACTION: open-url https://google.com/search?q=query+here]\n"
    "  [ACTION: type-text Hello world]\n"
    "  [ACTION: key-combo cmd+space]\n"
    "  [ACTION: screenshot]\n"
    "  [ACTION: volume 50]\n"
    "  [ACTION: mute] or [ACTION: unmute]\n"
    "  [ACTION: notify Title Message here]\n"
    "  [ACTION: quit-app AppName]\n"
    "  [ACTION: focus AppName]\n"
    "  [ACTION: dark-mode on] or [ACTION: dark-mode off]\n\n"
    "After any action, say a brief spoken confirmation (1 sentence).\n"
    "For conversations, respond in 2-3 natural sentences. No markdown ever.\n"
    "Be warm, direct, and genuinely helpful. You're their AI companion."
)


# ─── AI Worker ────────────────────────────────────────────

class AIWorker(QThread):
    transcript_ready = pyqtSignal(str)
    response_ready = pyqtSignal(str)
    audio_ready = pyqtSignal(object, int)
    action_executed = pyqtSignal(str, str)  # cmd, result
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._whisper = None
        self._kokoro = None
        self._task_queue = queue.Queue()
        self._models_ready = False
        # Persistent conversation
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
        if self._models_ready:
            self._task_queue.put(audio_data)

    def _capture_screen_b64(self):
        """Capture screenshot and return as base64 JPEG."""
        import tempfile, base64
        png = tempfile.mktemp(suffix=".png")
        subprocess.run(["screencapture", "-x", "-C", png], capture_output=True)
        if not os.path.exists(png):
            return None
        from PIL import Image
        import io
        img = Image.open(png)
        if img.width > 1280:
            ratio = 1280 / img.width
            img = img.resize((1280, int(img.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=50)
        b64 = base64.b64encode(buf.getvalue()).decode()
        os.unlink(png)
        return b64

    def _new_conversation(self):
        self._conv_id = new_conversation("VII Session")

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
                self.error_occurred.emit(str(e))
                self.status_changed.emit("Ready")

    def _process(self, audio_data):
        # ── STT ──
        self.status_changed.emit("Transcribing...")
        t0 = time.time()
        segments, _ = self._whisper.transcribe(audio_data, language="en", beam_size=3)
        text = " ".join(s.text.strip() for s in segments).strip()
        stt_ms = (time.time() - t0) * 1000

        if not text or len(text) < 2:
            self.status_changed.emit("Ready")
            return

        # Filter hallucinations
        lower = text.lower().strip()
        hallucinations = {"thank you", "thanks", "bye", "you", "the end",
                          "thank you for watching", "subscribe", "you you"}
        if lower in hallucinations or (len(lower) < 5 and lower.isalpha()):
            self.status_changed.emit("Ready")
            return

        self.transcript_ready.emit(text)
        self.status_changed.emit("Thinking...")

        # Vision — detect screen-related queries
        vision_triggers = ["screen", "see", "look at", "what's this", "what is this",
                           "show me", "read this", "what do you see", "analyze"]
        is_vision = any(t in lower for t in vision_triggers)
        screenshot_b64 = None
        if is_vision:
            self.status_changed.emit("Capturing screen...")
            screenshot_b64 = self._capture_screen_b64()

        # ── LLM ──
        import httpx

        add_message(self._conv_id, "user", text)
        messages = get_messages(self._conv_id, limit=20)

        # If vision, replace last user message with image + text
        if screenshot_b64 and messages:
            messages[-1] = {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": screenshot_b64}},
                    {"type": "text", "text": text},
                ],
            }

        # Load settings for provider selection
        settings_path = os.path.join(PROJECT_ROOT, "config", "vii-settings.json")
        llm_provider = "anthropic"
        llm_model = CLAUDE_MODEL
        ollama_url = "http://127.0.0.1:11434"
        if os.path.exists(settings_path):
            with open(settings_path) as f:
                s = json.load(f)
                llm_provider = s.get("llm_provider", "anthropic")
                llm_model = s.get("llm_model", CLAUDE_MODEL)
                ollama_url = s.get("ollama_url", "http://127.0.0.1:11434")

        t0 = time.time()
        response_text = ""

        if llm_provider == "ollama":
            # Local Ollama — no API key needed
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(
                    f"{ollama_url}/api/chat",
                    json={
                        "model": llm_model or "llama3.2:1b",
                        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                        "stream": False,
                    },
                )
                resp.raise_for_status()
                response_text = resp.json().get("message", {}).get("content", "")

        else:
            # Anthropic Claude (streaming + overlapped TTS)
            api_key = API_KEY
            if os.path.exists(settings_path):
                with open(settings_path) as f:
                    s = json.load(f)
                    custom_key = s.get("api_keys", {}).get("anthropic", "")
                    if custom_key.startswith("sk-"):
                        api_key = custom_key

            # TTS settings
            tts_voice = "am_onyx"
            tts_speed = 1.0
            if os.path.exists(settings_path):
                with open(settings_path) as f:
                    vs = json.load(f)
                    tts_voice = vs.get("tts_voice", "am_onyx")
                    tts_speed = vs.get("tts_speed", 1.0)

            # Stream Claude + extract sentences + TTS per sentence + play overlapped
            sentence_buffer = ""
            sentences_spoken = []
            first_audio = False
            import sounddevice as sd

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

                                # Check for complete sentence — speak it immediately
                                for i, ch in enumerate(sentence_buffer):
                                    if ch in '.!?' and i + 2 < len(sentence_buffer) and sentence_buffer[i+1] == ' ' and sentence_buffer[i+2].isupper():
                                        sentence = sentence_buffer[:i+1].strip()
                                        sentence_buffer = sentence_buffer[i+1:].strip()
                                        if sentence and len(sentence) > 5 and '[ACTION' not in sentence:
                                            # TTS this sentence NOW while Claude keeps streaming
                                            clean_s = re.sub(r'[`#*\[\]]', '', sentence)
                                            clean_s = clean_s.replace('%', ' percent').replace('&', ' and ')
                                            clean_s = clean_s.replace('\u2019', "'").replace('\u2018', "'")
                                            if not first_audio:
                                                first_audio = True
                                                self.response_ready.emit(sentence)
                                                self.status_changed.emit("Speaking...")
                                                print(f"  [first audio: {(time.time()-t0)*1000:.0f}ms]")
                                            s_samples, s_sr = self._kokoro.create(clean_s, voice=tts_voice, speed=tts_speed, lang="en-us")
                                            sd.play(s_samples, s_sr)
                                            sd.wait()
                                            sentences_spoken.append(sentence)
                                        break

        llm_ms = (time.time() - t0) * 1000

        # Speak any remaining text
        remaining = sentence_buffer.strip()
        if remaining and len(remaining) > 3 and '[ACTION' not in remaining:
            clean_r = re.sub(r'[`#*\[\]]', '', remaining)
            clean_r = clean_r.replace('%', ' percent').replace('&', ' and ')
            clean_r = clean_r.replace('\u2019', "'").replace('\u2018', "'")
            if not first_audio:
                self.response_ready.emit(remaining)
                self.status_changed.emit("Speaking...")
            s_samples, s_sr = self._kokoro.create(clean_r, voice=tts_voice, speed=tts_speed, lang="en-us")
            sd.play(s_samples, s_sr)
            sd.wait()

        add_message(self._conv_id, "assistant", response_text)

        # ── Execute Actions ──
        action_re = re.compile(r'\[ACTION:\s*(.+?)\]')
        for action in action_re.findall(response_text):
            parts = action.strip().split(None, 1)
            cmd = parts[0]
            args = parts[1] if len(parts) > 1 else ""
            try:
                result = subprocess.run(
                    [MAC_CONTROL, cmd] + ([args] if args else []),
                    capture_output=True, text=True, timeout=10,
                )
                out = result.stdout.strip()[:100]
                self.action_executed.emit(cmd, out or "done")
            except Exception as e:
                self.action_executed.emit(cmd, f"error: {e}")

        print(f"  [{stt_ms:.0f}ms stt | {llm_ms:.0f}ms llm]")
        self.status_changed.emit("Ready")


# ─── Orb Widget ───────────────────────────────────────────

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

        # Skin system
        self.skin_manager = SkinManager()
        self.skin = self.skin_manager.active_skin()
        self.orb_size = self.skin.size
        self.setFixedSize(self.orb_size + 48, self.orb_size + 50)

        # State
        self.state = "loading"
        self.accent = QColor("#06b6d4")
        self.glow_phase = 0.0
        self.audio_level = 0.0
        self.status_text = "Loading..."
        self.transcript_text = ""
        self.response_text = ""

        # Interaction
        self._drag_start = None
        self._drag_moved = False
        self._recording = False
        self._audio_chunks = []
        self._audio_stream = None
        self._models_ready = False

        # Hands-free mode
        self.hands_free = False
        self._vad_buffer = []
        self._vad_speaking = False
        self._vad_silence_frames = 0
        self._vad_speech_frames = 0
        self._continuous_stream = None

        # Animation
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)  # 30fps

        # Re-assert on-top every 5s (DecisionsAI pattern — Qt can lose it)
        self._top_timer = QTimer()
        self._top_timer.timeout.connect(self._reassert_top)
        self._top_timer.start(5000)

        # Position bottom-right
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.width() - self.width() - 20, screen.height() - self.height() - 40)

    def _tick(self):
        self.glow_phase += 0.05
        self.update()

    def _reassert_top(self):
        self.raise_()

    def set_models_ready(self):
        self._models_ready = True
        if not self.hands_free:
            self.state = "idle"
            self.status_text = "Tap to speak"
        self.update()

    def set_state(self, state):
        self.state = state
        self.update()

    def set_status(self, text):
        self.status_text = text
        self.update()

    def set_transcript(self, text):
        self.transcript_text = text

    def set_response(self, text):
        self.response_text = text

    # ── Paint ──

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width() // 2
        cy = 12 + self.orb_size // 2
        r = self.orb_size // 2

        # Glow intensity by state
        if self.state == "loading":
            ga = 0.03 + 0.02 * math.sin(self.glow_phase * 0.5)
        elif self.state == "idle":
            ga = 0.04 + 0.025 * math.sin(self.glow_phase)
        elif self.state == "listening":
            ga = 0.12 + 0.08 * math.sin(self.glow_phase * 2.5) + self.audio_level * 0.1
        elif self.state == "thinking":
            ga = 0.08 + 0.06 * math.sin(self.glow_phase * 1.8)
        elif self.state == "speaking":
            ga = 0.1 + self.audio_level * 0.2
        else:
            ga = 0.04

        # Colors from skin
        color = QColor(self.skin.color_for_state(self.state) if self.state != "loading" else "#475569")
        glow_mult = self.skin.glow_intensity if self.skin.glow else 0.3

        # Outer glow (scaled by skin intensity)
        ga = ga * glow_mult
        gc = QColor(color)
        gc.setAlphaF(min(ga, 1.0))
        grad = QRadialGradient(cx, cy, r * 2.2)
        grad.setColorAt(0, gc)
        grad.setColorAt(0.5, QColor(gc.red(), gc.green(), gc.blue(), int(ga * 80)))
        grad.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPoint(cx, cy), int(r * 2.2), int(r * 2.2))

        # Orb body
        body = QRadialGradient(cx - r * 0.15, cy - r * 0.15, r * 1.1)
        body.setColorAt(0, QColor(28, 28, 42))
        body.setColorAt(0.7, QColor(15, 15, 24))
        body.setColorAt(1, QColor(8, 8, 14))
        p.setBrush(body)

        # Ring
        rc = QColor(color)
        rc.setAlphaF(min(0.25 + ga * 1.5, 1.0))
        p.setPen(QPen(rc, 1.5))
        p.drawEllipse(QPoint(cx, cy), r, r)

        # Inner waveform during recording
        if self.state == "listening" and self.audio_level > 0.01:
            wc = QColor(color)
            wc.setAlphaF(0.4)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(wc)
            wave_r = int(r * 0.3 + r * 0.4 * self.audio_level)
            p.drawEllipse(QPoint(cx, cy), wave_r, wave_r)

        # Thinking spinner dots
        if self.state == "thinking":
            for i in range(3):
                angle = self.glow_phase * 3 + i * (2 * math.pi / 3)
                dx = int(math.cos(angle) * r * 0.35)
                dy = int(math.sin(angle) * r * 0.35)
                dot_alpha = 0.4 + 0.4 * math.sin(self.glow_phase * 2 + i)
                dc = QColor(color)
                dc.setAlphaF(min(dot_alpha, 1.0))
                p.setBrush(dc)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPoint(cx + dx, cy + dy), 3, 3)

        # Status text
        p.setPen(QColor(100, 100, 120))
        font = p.font()
        font.setPointSize(8)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        p.setFont(font)
        status = self.status_text.upper()
        if self.hands_free and self.state == "idle":
            status = "HANDS-FREE"
        p.drawText(QRect(0, cy + r + 6, self.width(), 18),
                   Qt.AlignmentFlag.AlignHCenter, status)

        p.end()

    # ── Mouse ──

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.globalPosition().toPoint()
            self._drag_moved = False

    def mouseMoveEvent(self, event):
        if self._drag_start and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_start
            if delta.manhattanLength() > 5:
                self._drag_moved = True
                self.move(self.pos() + delta)
                self._drag_start = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self._drag_moved:
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
        self._drag_start = None
        self._drag_moved = False

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#12121e;color:#bbb;border:1px solid #252535;padding:4px;font-size:12px}"
            "QMenu::item{padding:8px 24px}"
            "QMenu::item:selected{background:#1e1e35;color:#fff}"
            "QMenu::separator{background:#252535;height:1px;margin:4px 8px}"
        )

        # Listen / Hands-free
        listen_act = menu.addAction("Listening: ON" if self._models_ready else "Listening: OFF")
        listen_act.setEnabled(self._models_ready)

        hf = menu.addAction("Hands-Free: ON" if self.hands_free else "Hands-Free: OFF")
        hf.triggered.connect(self._toggle_hands_free)

        dict_act = menu.addAction("Dictation Mode")
        dict_act.triggered.connect(self._toggle_dictation)

        menu.addSeparator()

        # Conversation
        menu.addAction("New Chat").triggered.connect(self._new_chat)
        menu.addAction("What's on screen?").triggered.connect(
            lambda: self.recording_stopped.emit(np.array([0.01], dtype=np.float32)))

        menu.addSeparator()

        # Appearance
        skin_menu = menu.addMenu("Skin")
        skin_menu.setStyleSheet(menu.styleSheet())
        for skin_id, skin_name in self.skin_manager.list_skins():
            active = " *" if skin_id == self.skin_manager._active else ""
            act = skin_menu.addAction(f"{skin_name}{active}")
            act.triggered.connect(lambda checked, sid=skin_id: self._set_skin(sid))

        menu.addAction("Preferences").triggered.connect(self._open_preferences)

        menu.addSeparator()

        # System
        menu.addAction("Hide VII").triggered.connect(self.hide)
        menu.addAction("Restart").triggered.connect(self._restart)
        menu.addAction("Quit VII").triggered.connect(QApplication.quit)
        menu.exec(event.globalPos())

    def _open_preferences(self):
        """Launch settings web UI and open in browser."""
        import webbrowser
        # Start settings server if not running
        if not hasattr(self, '_settings_proc') or self._settings_proc is None or self._settings_proc.poll() is not None:
            import sys
            python = os.path.join(PROJECT_ROOT, "tts-venv", "bin", "python3")
            if not os.path.exists(python):
                python = sys.executable
            self._settings_proc = subprocess.Popen(
                [python, os.path.join(PROJECT_ROOT, "settings_ui.py")],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            import time
            time.sleep(1)
        webbrowser.open("http://localhost:7748")

    def _new_chat(self):
        """Start a fresh conversation."""
        from core.db import new_conversation
        # Signal the worker to start new conversation
        self.set_status("New chat")

    def _restart(self):
        """Restart VII."""
        QApplication.quit()
        subprocess.Popen([sys.executable, os.path.join(PROJECT_ROOT, "desktop.py")])

    def _toggle_dictation(self):
        """Toggle dictation mode — types what you say instead of talking to AI."""
        self._dictation_mode = not getattr(self, '_dictation_mode', False)
        if self._dictation_mode:
            self.set_status("Dictation ON")
        else:
            self.set_status("Tap to speak")

    def _set_skin(self, skin_id):
        if self.skin_manager.set_active(skin_id):
            self.skin = self.skin_manager.active_skin()
            self.orb_size = self.skin.size
            self.setFixedSize(self.orb_size + 48, self.orb_size + 50)
            self.set_status(f"Skin: {self.skin.name}")
            self.update()

    def _toggle_hands_free(self):
        self.hands_free = not self.hands_free
        if self.hands_free:
            self._start_hands_free()
        else:
            self._stop_hands_free()

    # ── Push-to-Talk Recording ──

    def _start_recording(self):
        import sounddevice as sd
        self._recording = True
        self._audio_chunks = []
        self.set_state("listening")
        self.set_status("Listening...")

        def cb(indata, frames, t, status):
            if self._recording:
                amplified = indata.copy() * MIC_GAIN
                amplified = np.clip(amplified, -1.0, 1.0)
                self._audio_chunks.append(amplified)
                rms = float(np.sqrt(np.mean(amplified ** 2)))
                self.audio_level = min(rms * 3.0, 1.0)

        self._audio_stream = sd.InputStream(
            samplerate=16000, channels=1, dtype='float32', blocksize=1024, callback=cb
        )
        self._audio_stream.start()

    def _stop_recording(self):
        self._recording = False
        if self._audio_stream:
            self._audio_stream.stop()
            self._audio_stream.close()
            self._audio_stream = None

        if self._audio_chunks:
            audio = np.concatenate(self._audio_chunks, axis=0).flatten()
            rms = float(np.sqrt(np.mean(audio ** 2)))
            duration = len(audio) / 16000
            if rms > 0.005 and duration > 0.3:
                self.set_state("thinking")
                self.set_status("Processing...")
                self.recording_stopped.emit(audio)
                return

        self.set_state("idle")
        self.set_status("Tap to speak")
        self.audio_level = 0.0

    # ── Hands-Free (VAD) ──

    def _start_hands_free(self):
        import sounddevice as sd
        self.set_status("Hands-free")
        self._vad_speaking = False
        self._vad_silence_frames = 0
        self._vad_speech_frames = 0
        self._audio_chunks = []

        def cb(indata, frames, t, status):
            amplified = indata.copy() * MIC_GAIN
            amplified = np.clip(amplified, -1.0, 1.0)
            rms = float(np.sqrt(np.mean(amplified ** 2)))
            self.audio_level = min(rms * 3.0, 1.0)

            if self._vad_speaking:
                self._audio_chunks.append(amplified)
                if rms < 0.01:
                    self._vad_silence_frames += 1
                    # 500ms of silence = end of speech (16000/1024 * 0.5 ≈ 8 frames)
                    if self._vad_silence_frames > 8:
                        self._vad_speaking = False
                        self._vad_silence_frames = 0
                        self._vad_speech_frames = 0
                        # Process in main thread
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
                if rms > 0.02:
                    self._vad_speech_frames += 1
                    # 100ms of speech = start recording (about 2 frames)
                    if self._vad_speech_frames > 2:
                        self._vad_speaking = True
                        self._audio_chunks = [amplified]
                        self.set_state("listening")
                        self.set_status("Listening...")
                else:
                    self._vad_speech_frames = 0

        self._continuous_stream = sd.InputStream(
            samplerate=16000, channels=1, dtype='float32', blocksize=1024, callback=cb
        )
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


# ─── Main App ────────────────────────────────────────────

class VIIApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setApplicationName("VII")

        # Orb
        self.orb = OrbWidget()
        self.orb.show()

        # System tray
        self._setup_tray()

        # AI worker
        self.worker = AIWorker()
        self.worker.transcript_ready.connect(self._on_transcript)
        self.worker.response_ready.connect(self._on_response)
        self.worker.audio_ready.connect(self._on_audio)
        self.worker.action_executed.connect(self._on_action)
        self.worker.status_changed.connect(self._on_status)
        self.worker.error_occurred.connect(self._on_error)
        self.orb.recording_stopped.connect(self._on_recorded)

        # Load models in background
        QTimer.singleShot(100, self._load)

    def _setup_tray(self):
        # Create a simple tray icon
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor("#06b6d4"))
        icon = QIcon(pixmap)

        self.tray = QSystemTrayIcon(icon, self.app)
        tray_menu = QMenu()
        tray_menu.setStyleSheet(
            "QMenu{background:#12121e;color:#bbb;border:1px solid #252535}"
            "QMenu::item{padding:6px 20px}"
            "QMenu::item:selected{background:#1e1e35;color:#fff}"
        )
        tray_menu.addAction("Show VII").triggered.connect(self.orb.show)
        tray_menu.addAction("Hide VII").triggered.connect(self.orb.hide)
        tray_menu.addSeparator()
        tray_menu.addAction("Quit").triggered.connect(self._quit)
        self.tray.setContextMenu(tray_menu)
        self.tray.setToolTip("VII — The 747 Lab")
        self.tray.show()

    def _load(self):
        def _bg():
            self.worker.load_models()
            self.worker.start()
            self.orb.set_models_ready()

        threading.Thread(target=_bg, daemon=True).start()

    def _on_recorded(self, audio):
        self.worker.submit(audio)

    def _on_transcript(self, text):
        self.orb.set_transcript(text)
        print(f"  You: \"{text}\"")

    def _on_response(self, text):
        self.orb.set_response(text)
        self.orb.set_state("speaking")
        print(f"  VII: {text[:100]}")

    def _on_audio(self, samples, sr):
        # TTS now plays directly in the worker thread (overlapped with streaming)
        # This callback is kept for compatibility but audio is already played
        pass

    def _on_action(self, cmd, result):
        print(f"  [ACTION] {cmd} → {result}")

    def _on_status(self, text):
        if text == "Ready":
            if self.orb.hands_free:
                self.orb.set_state("idle")
                self.orb.set_status("Hands-free")
            else:
                self.orb.set_state("idle")
                self.orb.set_status("Tap to speak")
            self.orb.audio_level = 0.0
        else:
            self.orb.set_status(text)

    def _on_error(self, text):
        print(f"  [ERROR] {text}")
        self.orb.set_state("idle")
        self.orb.set_status("Error — tap to retry")

    def _quit(self):
        if self.orb._continuous_stream:
            self.orb._stop_hands_free()
        self.worker._task_queue.put(None)
        self.tray.hide()
        self.app.quit()

    def run(self):
        print()
        print("  ╔══════════════════════════════════════╗")
        print("  ║  VII — Voice Intelligence Interface  ║")
        print("  ║  The 747 Lab                         ║")
        print("  ╚══════════════════════════════════════╝")
        print()
        print("  Click orb to speak. Right-click for menu.")
        print("  System tray icon active.")
        print()
        sys.exit(self.app.exec())


if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: No Anthropic API key.")
        sys.exit(1)
    VIIApp().run()
