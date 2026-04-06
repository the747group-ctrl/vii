#!/usr/bin/env python3
"""
VII Desktop — Floating AI Avatar App

A floating orb on your desktop. Always there. Click to talk.
Right-click for agent selection. Drag to reposition.

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

import numpy as np

from PyQt6.QtWidgets import QApplication, QWidget, QMenu
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, pyqtSignal, QThread
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QPen, QFont

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
CLAUDE_MODEL = "claude-sonnet-4-20250514"

AGENTS = {
    "vii":    {"voice": "af_heart",   "speed": 1.1,  "color": "#06b6d4", "role": "Your voice AI."},
    "bob":    {"voice": "am_onyx",    "speed": 1.0,  "color": "#3b82f6", "role": "Lead strategist."},
    "falcon": {"voice": "am_michael", "speed": 0.95, "color": "#22c55e", "role": "Intel analyst."},
    "pixi":   {"voice": "af_heart",   "speed": 1.25, "color": "#ec4899", "role": "Creative director."},
    "buzz":   {"voice": "am_puck",    "speed": 1.3,  "color": "#f97316", "role": "Content strategist."},
}


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


class AIWorker(QThread):
    transcript_ready = pyqtSignal(str)
    response_ready = pyqtSignal(str, str)
    audio_ready = pyqtSignal(object, int)
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._whisper = None
        self._kokoro = None
        self._task_queue = queue.Queue()

    def load_models(self):
        self.status_changed.emit("Loading Whisper...")
        from faster_whisper import WhisperModel
        model_dir = os.path.join(MODELS_DIR, "models--Systran--faster-whisper-small", "snapshots")
        if os.path.exists(model_dir):
            snaps = [s for s in os.listdir(model_dir) if not s.startswith('.')]
            if snaps:
                self._whisper = WhisperModel(os.path.join(model_dir, snaps[0]), device="cpu", compute_type="int8")
        if not self._whisper:
            self._whisper = WhisperModel("small", device="cpu", compute_type="int8")

        self.status_changed.emit("Loading Kokoro...")
        from kokoro_onnx import Kokoro
        self._kokoro = Kokoro(
            os.path.join(MODELS_DIR, "kokoro", "kokoro-v1.0.onnx"),
            os.path.join(MODELS_DIR, "kokoro", "voices-v1.0.bin"),
        )
        self.status_changed.emit("Ready")

    def submit(self, audio_data, agent="vii"):
        self._task_queue.put(("process", audio_data, agent))

    def run(self):
        while True:
            try:
                task = self._task_queue.get(timeout=1)
            except queue.Empty:
                continue
            if task is None:
                break
            cmd, audio_data, agent = task
            try:
                self._process(audio_data, agent)
            except Exception as e:
                self.error_occurred.emit(str(e))

    def _process(self, audio_data, agent):
        self.status_changed.emit("Listening...")
        segments, _ = self._whisper.transcribe(audio_data, language="en", beam_size=3)
        text = " ".join(s.text.strip() for s in segments).strip()

        if not text or len(text) < 2:
            self.status_changed.emit("Ready")
            return

        lower = text.lower().strip()
        if lower in ("thank you", "thanks", "bye", "you", "the end",
                      "thank you for watching", "subscribe"):
            self.status_changed.emit("Ready")
            return

        self.transcript_ready.emit(text)
        self.status_changed.emit("Thinking...")

        import httpx
        import subprocess

        MAC_CONTROL = os.path.expanduser("~/.747lab/mac-control.sh")

        system = (
            "You are VII, a voice-controlled AI assistant by The 747 Lab. "
            "You can control the user's Mac computer AND have conversations.\n\n"
            "IMPORTANT: When the user asks you to DO something on their computer, "
            "respond with the ACTION in a special format, then a brief spoken confirmation.\n\n"
            "Format for actions:\n"
            "  [ACTION: open-app Safari]\n"
            "  [ACTION: open-url https://google.com/search?q=voice+AI]\n"
            "  [ACTION: type-text Hello world]\n"
            "  [ACTION: key-combo cmd+space]\n"
            "  [ACTION: screenshot]\n"
            "  [ACTION: volume 50]\n"
            "  [ACTION: notify VII 'Task complete']\n\n"
            "Available actions: open-app, quit-app, focus, open-url, type-text, "
            "key-press, key-combo, screenshot, volume, mute, unmute, notify, clipboard-get, "
            "clipboard-set, dark-mode\n\n"
            "After the [ACTION] line, write a brief spoken confirmation (1 sentence, no markdown).\n"
            "If no action is needed, just respond conversationally in 2-3 sentences. No markdown."
        )

        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": CLAUDE_MODEL, "max_tokens": 250, "system": system,
                  "messages": [{"role": "user", "content": text}]},
            timeout=30.0,
        )
        resp.raise_for_status()
        response_text = resp.json().get("content", [{}])[0].get("text", "")

        # Execute any actions
        action_pattern = re.compile(r'\[ACTION:\s*(.+?)\]')
        actions_found = action_pattern.findall(response_text)
        for action in actions_found:
            parts = action.strip().split(None, 1)
            cmd = parts[0]
            args = parts[1] if len(parts) > 1 else ""
            print(f"  [ACTION] {cmd} {args}")
            try:
                result = subprocess.run(
                    [MAC_CONTROL, cmd] + (args.split() if args else []),
                    capture_output=True, text=True, timeout=10,
                )
                if result.stdout.strip():
                    print(f"  [RESULT] {result.stdout.strip()[:100]}")
            except Exception as e:
                print(f"  [ACTION ERROR] {e}")

        # Remove action tags from spoken text
        spoken = action_pattern.sub('', response_text).strip()
        if not spoken:
            spoken = "Done."

        self.response_ready.emit("vii", spoken)
        self.status_changed.emit("Speaking...")

        txt = re.sub(r'[`#*]', '', spoken)
        txt = txt.replace('%', ' percent').replace('&', ' and ')
        txt = txt.replace('\u2019', "'").replace('\u2018', "'")
        samples, sr = self._kokoro.create(txt, voice="am_onyx", speed=1.0, lang="en-us")
        self.audio_ready.emit(samples, sr)
        self.status_changed.emit("Ready")


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

        self.orb_size = 80
        self.setFixedSize(self.orb_size + 40, self.orb_size + 55)

        self.state = "idle"
        self.agent_color = QColor("#06b6d4")
        self.agent_name = "VII"
        self.glow_phase = 0.0
        self.audio_level = 0.0
        self.status_text = "Loading..."
        self.current_agent = "vii"

        self._drag_start = None
        self._drag_moved = False
        self._recording = False
        self._audio_chunks = []
        self._audio_stream = None

        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

        # Position center of screen so it's impossible to miss
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.center().x() - self.width() // 2, screen.center().y() - self.height() // 2)
        # Force visibility
        self.show()
        self.raise_()
        self.activateWindow()

    def _tick(self):
        self.glow_phase += 0.05
        self.update()

    def set_state(self, state, agent=None, color=None):
        self.state = state
        if agent:
            self.agent_name = agent.upper()
        if color:
            self.agent_color = QColor(color)
        self.update()

    def set_status(self, text):
        self.status_text = text
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width() // 2
        cy = 10 + self.orb_size // 2
        r = self.orb_size // 2

        if self.state == "idle":
            ga = 0.05 + 0.03 * math.sin(self.glow_phase)
        elif self.state == "listening":
            ga = 0.15 + 0.1 * math.sin(self.glow_phase * 2)
        elif self.state == "thinking":
            ga = 0.1 + 0.08 * math.sin(self.glow_phase * 1.5)
        elif self.state == "speaking":
            ga = 0.12 + self.audio_level * 0.15
        else:
            ga = 0.05

        gc = QColor(self.agent_color)
        gc.setAlphaF(min(ga, 1.0))
        grad = QRadialGradient(cx, cy, r * 2)
        grad.setColorAt(0, gc)
        grad.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPoint(cx, cy), r * 2, r * 2)

        body = QRadialGradient(cx - r * 0.2, cy - r * 0.2, r * 1.2)
        body.setColorAt(0, QColor(30, 30, 45))
        body.setColorAt(1, QColor(12, 12, 20))
        p.setBrush(body)
        rc = QColor(self.agent_color)
        rc.setAlphaF(min(0.3 + ga, 1.0))
        p.setPen(QPen(rc, 1.5))
        p.drawEllipse(QPoint(cx, cy), r, r)

        p.setPen(QColor(80, 80, 100))
        font = p.font()
        font.setPointSize(9)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        p.setFont(font)
        p.drawText(QRect(0, cy + r + 8, self.width(), 20),
                   Qt.AlignmentFlag.AlignHCenter, self.status_text.upper())
        p.end()

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
            if self.state == "speaking":
                # Interrupt current response — click during speech stops it
                import sounddevice as sd
                sd.stop()
                self.set_state("idle")
                self.set_status("Tap to speak")
            elif not self._recording:
                self._start_recording()
            else:
                self._stop_recording()
        self._drag_start = None
        self._drag_moved = False

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("QMenu{background:#1a1a2e;color:#ccc;border:1px solid #333;padding:4px}"
                           "QMenu::item{padding:6px 20px}"
                           "QMenu::item:selected{background:#2a2a4e}")
        for name, cfg in AGENTS.items():
            act = menu.addAction(f"{name.upper()} — {cfg['role']}")
            act.triggered.connect(lambda checked, n=name, c=cfg: self._switch_agent(n, c))
        menu.addSeparator()
        menu.addAction("Quit VII").triggered.connect(QApplication.quit)
        menu.exec(event.globalPos())

    def _switch_agent(self, name, cfg):
        self.current_agent = name
        self.agent_name = name.upper()
        self.agent_color = QColor(cfg["color"])
        self.set_status(f"{name.upper()} active")

    def _start_recording(self):
        import sounddevice as sd
        self._recording = True
        self._audio_chunks = []
        self.set_state("listening")
        self.set_status("Listening...")

        def cb(indata, frames, t, status):
            if self._recording:
                # Amplify 30x for RODE PodMic (dynamic mic, low output)
                amplified = indata.copy() * 30.0
                amplified = np.clip(amplified, -1.0, 1.0)
                self._audio_chunks.append(amplified)
                rms = float(np.sqrt(np.mean(amplified ** 2)))
                self.audio_level = min(rms * 3.0, 1.0)

        self._audio_stream = sd.InputStream(samplerate=16000, channels=1, dtype='float32',
                                             blocksize=1024, callback=cb)
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
            if rms > 0.003 and len(audio) > 4800:
                self.set_state("thinking")
                self.set_status("Processing...")
                self.recording_stopped.emit(audio)
                return

        self.set_state("idle")
        self.set_status("Tap to speak")


class VIIApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.orb = OrbWidget()
        self.orb.show()

        self.worker = AIWorker()
        self.worker.transcript_ready.connect(self._on_transcript)
        self.worker.response_ready.connect(self._on_response)
        self.worker.audio_ready.connect(self._on_audio)
        self.worker.status_changed.connect(self._on_status)
        self.worker.error_occurred.connect(self._on_error)
        self.orb.recording_stopped.connect(self._on_recorded)

        QTimer.singleShot(100, self._load)

    def _load(self):
        # Load models in background — orb shows immediately, models load behind
        def _bg_load():
            self.worker.load_models()
            self.worker.start()
            # Signal ready on main thread
            self.orb.set_status("Tap to speak")
            print("  VII ready.")

        loader = threading.Thread(target=_bg_load, daemon=True)
        loader.start()

    def _on_recorded(self, audio):
        self.worker.submit(audio, self.orb.current_agent)

    def _on_transcript(self, text):
        print(f"  You: \"{text}\"")

    def _on_response(self, agent, text):
        cfg = AGENTS.get(agent, AGENTS["vii"])
        self.orb.set_state("speaking", agent=agent, color=cfg["color"])
        print(f"  {agent.upper()}: {text}")

    def _on_audio(self, samples, sr):
        import sounddevice as sd

        def play():
            sd.play(samples, sr)
            sd.wait()
            self.orb.set_state("idle")
            self.orb.set_status("Tap to speak")

        threading.Thread(target=play, daemon=True).start()

    def _on_status(self, text):
        self.orb.set_status(text)

    def _on_error(self, text):
        print(f"  Error: {text}")
        self.orb.set_state("idle")
        self.orb.set_status("Tap to retry")

    def run(self):
        print("\n  VII Desktop — The 747 Lab")
        print("  Click orb to speak. Right-click for agents.\n")
        sys.exit(self.app.exec())


if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: No Anthropic API key.")
        sys.exit(1)
    VIIApp().run()
