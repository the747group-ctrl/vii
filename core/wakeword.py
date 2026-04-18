"""
VII Wake Word Detection — Local keyword spotting.
Detects "Hey VII" or "VII" using Whisper on short audio chunks.

Runs as a background thread, triggers recording when wake word detected.
Uses tiny audio windows (2s) for low latency detection.

Developed by The 747 Lab
"""

import threading
import time
import numpy as np


class WakeWordDetector:
    """Listens for 'VII' or 'Hey VII' using periodic Whisper checks."""

    WAKE_PHRASES = {"seven", "vii", "hey seven", "hey vii", "hey v",
                     "hey 7", "a7", "hey vi", "vi", "hey v i i"}

    def __init__(self, whisper_model, mic_gain=10.0, check_interval=2.0):
        self._whisper = whisper_model
        self._mic_gain = mic_gain
        self._interval = check_interval
        self._running = False
        self._callback = None
        self._thread = None

    def start(self, on_wake):
        """Start listening for wake word. Calls on_wake() when detected."""
        self._callback = on_wake
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _listen_loop(self):
        import sounddevice as sd

        while self._running:
            try:
                # Record short chunk
                audio = sd.rec(int(16000 * self._interval), samplerate=16000,
                               channels=1, dtype='float32')
                sd.wait()
                audio = np.clip(audio.flatten() * self._mic_gain, -1.0, 1.0)

                rms = float(np.sqrt(np.mean(audio ** 2)))
                if rms < 0.005:
                    continue  # Silence — skip transcription

                # Quick transcribe with small beam
                segments, _ = self._whisper.transcribe(
                    audio, language="en", beam_size=1,
                    no_speech_threshold=0.6,
                )
                text = " ".join(s.text.strip().lower() for s in segments).strip()

                if any(phrase in text for phrase in self.WAKE_PHRASES):
                    if self._callback:
                        self._callback()
                    # Cooldown after wake
                    time.sleep(1.0)

            except Exception:
                time.sleep(1.0)
