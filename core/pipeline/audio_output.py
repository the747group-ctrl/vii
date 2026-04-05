"""
VII Two — Audio output processor.
Plays audio chunks via PyAudio/CoreAudio.
Tracks playback watermark for echo cancellation timing.
Sends mouth sync data to overlay via IPC.
"""

import asyncio
import json
import logging
import socket
import struct
import time
from typing import Optional

from .processor import FrameProcessor
from .frames import (
    Frame, AudioOutputFrame, TTSStartedFrame, TTSStoppedFrame,
    InterruptionFrame, StateChangeFrame, PipelineState,
)

logger = logging.getLogger("vii.pipeline.audio_output")


class AudioOutputProcessor(FrameProcessor):
    """
    Plays audio frames through the system speaker.
    Tracks playback watermark (DecisionsAI pattern) for AEC timing.
    Sends state + mouth sync to overlay via Unix socket.
    """

    def __init__(self, overlay_socket_path: str = "/tmp/vii-overlay.sock"):
        super().__init__(name="AudioOutput")
        self._overlay_socket_path = overlay_socket_path
        self._playback_watermark = 0.0
        self._stream = None
        self._pyaudio = None
        self._volume = 1.0
        self._is_playing = False

        # Playback timing constants (from DecisionsAI)
        self._PLAYBACK_BUFFER_MARGIN = 0.6  # Hardware buffer drain margin
        self._PLAYBACK_MIN_WAIT = 0.8       # Minimum wait even for short audio

    async def start(self):
        await super().start()
        try:
            import pyaudio
            self._pyaudio = pyaudio.PyAudio()
            self._stream = self._pyaudio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=24000,
                output=True,
                frames_per_buffer=1024,
            )
            logger.info("Audio output stream opened (24kHz, mono, 16-bit)")
        except ImportError:
            logger.warning("PyAudio not available — audio output disabled")
        except Exception as e:
            logger.error(f"Failed to open audio output: {e}")

    async def stop(self):
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        if self._pyaudio:
            self._pyaudio.terminate()
        await super().stop()

    async def process_frame(self, frame: Frame):
        if isinstance(frame, AudioOutputFrame):
            await self._play_audio(frame)

        elif isinstance(frame, TTSStartedFrame):
            self._is_playing = True
            await self._send_overlay_state("speaking")

        elif isinstance(frame, TTSStoppedFrame):
            # Don't immediately mark as done — wait for hardware drain
            asyncio.create_task(self._wait_for_drain())

        elif isinstance(frame, InterruptionFrame):
            await self._interrupt_playback()

        elif isinstance(frame, StateChangeFrame):
            state_name = frame.to_state.value
            await self._send_overlay_state(state_name, agent=frame.agent)

        else:
            await self.push_frame(frame)

    async def _play_audio(self, frame: AudioOutputFrame):
        """Write audio to output stream and update watermark."""
        if not self._stream:
            return

        loop = asyncio.get_event_loop()

        # Apply volume
        if self._volume != 1.0:
            import numpy as np
            audio_array = np.frombuffer(frame.audio, dtype=np.int16).astype(np.float32)
            audio_array *= self._volume
            audio_array = np.clip(audio_array, -32768, 32767)
            audio_bytes = audio_array.astype(np.int16).tobytes()
        else:
            audio_bytes = frame.audio

        # Calculate frame duration
        bytes_per_sample = 2  # 16-bit
        frame_duration = len(audio_bytes) / (frame.sample_rate * bytes_per_sample)

        # Update playback watermark (DecisionsAI pattern)
        now = time.time()
        if self._playback_watermark < now:
            self._playback_watermark = now + frame_duration
        else:
            self._playback_watermark += frame_duration

        # Write audio (in executor to avoid blocking)
        await loop.run_in_executor(None, self._stream.write, audio_bytes)

        # Send mouth sync to overlay
        if frame.mouth_sync:
            await self._send_overlay_mouth_sync(frame.mouth_sync)

    async def _wait_for_drain(self):
        """Wait for hardware buffer to drain before signaling completion."""
        now = time.time()
        remaining = self._playback_watermark - now
        wait_time = max(self._PLAYBACK_MIN_WAIT, remaining + self._PLAYBACK_BUFFER_MARGIN)

        await asyncio.sleep(wait_time)

        if self._is_playing:  # Not interrupted during drain
            self._is_playing = False
            await self._send_overlay_state("idle")

    async def _interrupt_playback(self):
        """Immediately stop playback."""
        self._is_playing = False
        self._playback_watermark = 0.0

        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.start_stream()
            except Exception:
                pass

        await self._send_overlay_state("idle")

    async def _send_overlay_state(self, state: str, agent=None):
        """Send state change to overlay via Unix socket."""
        msg = {"type": "state", "state": state}
        if agent:
            msg["agent"] = agent.value if hasattr(agent, 'value') else str(agent)
        await self._send_overlay_message(msg)

    async def _send_overlay_mouth_sync(self, levels: list):
        """Send mouth sync RMS levels to overlay."""
        msg = {"type": "audio_level", "levels": levels}
        await self._send_overlay_message(msg)

    async def _send_overlay_message(self, msg: dict):
        """Send JSON message to overlay via Unix domain socket."""
        try:
            data = json.dumps(msg).encode() + b"\n"
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(0.1)
            sock.connect(self._overlay_socket_path)
            sock.sendall(data)
            sock.close()
        except (ConnectionRefusedError, FileNotFoundError, socket.timeout):
            pass  # Overlay not running — that's fine
        except Exception as e:
            logger.debug(f"Overlay IPC error: {e}")

    def set_volume(self, volume: float):
        """Set output volume (0.0 to 1.0)."""
        self._volume = max(0.0, min(1.0, volume))

    @property
    def playback_watermark(self) -> float:
        """Current playback watermark timestamp. Used by echo canceller."""
        return self._playback_watermark
