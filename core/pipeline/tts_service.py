"""
VII Two — Streaming TTS service.
Receives SentenceFrames and generates AudioOutputFrames via Kokoro daemon.

Key difference from VII Zero:
- Generates audio per-sentence (not waiting for full response)
- Pushes audio chunks for immediate playback
- Tracks mouth sync data for overlay animation
"""

import asyncio
import json
import logging
import subprocess
import sys
import os
from pathlib import Path
from typing import Optional

from .processor import FrameProcessor
from .frames import (
    Frame, SentenceFrame, AudioOutputFrame, TTSStartedFrame,
    TTSStoppedFrame, InterruptionFrame, StateChangeFrame,
    PipelineState, AgentName,
)

logger = logging.getLogger("vii.pipeline.tts")

# Agent voice assignments (Kokoro voice IDs)
AGENT_VOICES = {
    AgentName.BOB: "am_onyx",       # Deep, authoritative
    AgentName.FALCON: "am_michael",  # Measured, professional
    AgentName.ACE: "bf_emma",        # British, efficient
    AgentName.PIXI: "af_heart",     # Expressive, creative
    AgentName.BUZZ: "am_puck",       # Playful, energetic
    AgentName.CLAUDE: "af_nicole",   # Warm, versatile
    AgentName.FOUNDER: "am_onyx",    # Same as Bob (placeholder)
}

# Agent speech speeds (WPM mapped to Kokoro speed param)
AGENT_SPEEDS = {
    AgentName.BOB: 1.0,
    AgentName.FALCON: 0.95,
    AgentName.ACE: 1.15,
    AgentName.PIXI: 1.25,
    AgentName.BUZZ: 1.3,
    AgentName.CLAUDE: 1.1,
    AgentName.FOUNDER: 1.0,
}


class StreamingTTSService(FrameProcessor):
    """
    Streaming TTS via Kokoro daemon.
    Receives sentences, generates audio, pushes chunks immediately.
    """

    def __init__(self, daemon_script: Optional[str] = None):
        super().__init__(name="StreamingTTS")
        self._daemon_script = daemon_script or str(
            Path(__file__).parent.parent.parent / "scripts" / "tts-daemon.py"
        )
        self._daemon_process: Optional[subprocess.Popen] = None
        self._current_agent = AgentName.BOB
        self._interrupted = False

    async def start(self):
        """Launch the TTS daemon process."""
        await super().start()
        await self._start_daemon()

    async def stop(self):
        """Kill the TTS daemon."""
        if self._daemon_process:
            self._daemon_process.terminate()
            self._daemon_process = None
        await super().stop()

    async def _start_daemon(self):
        """Start Kokoro TTS daemon (keeps model loaded in memory)."""
        venv_python = str(
            Path(__file__).parent.parent.parent / "tts-venv" / "bin" / "python3"
        )
        # Fall back to system python if venv doesn't exist
        python = venv_python if os.path.exists(venv_python) else sys.executable

        try:
            self._daemon_process = subprocess.Popen(
                [python, self._daemon_script],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            logger.info("TTS daemon started")
        except Exception as e:
            logger.error(f"Failed to start TTS daemon: {e}")

    async def process_frame(self, frame: Frame):
        if isinstance(frame, SentenceFrame):
            if self._interrupted:
                return  # Don't generate audio for interrupted responses

            # Signal TTS start
            await self.push_frame(TTSStartedFrame(
                sentence_index=frame.sentence_index,
            ))

            # Generate audio for this sentence
            await self._generate_audio(frame.text, frame.sentence_index)

            # Signal TTS end for this sentence
            await self.push_frame(TTSStoppedFrame(
                sentence_index=frame.sentence_index,
            ))

        elif isinstance(frame, InterruptionFrame):
            self._interrupted = True
            # Kill any in-progress TTS generation
            await self._interrupt_daemon()
            await self.push_frame(frame)

        elif isinstance(frame, StateChangeFrame):
            if frame.agent:
                self._current_agent = frame.agent
            # Reset interruption flag on new thinking state
            if frame.to_state == PipelineState.THINKING:
                self._interrupted = False
            await self.push_frame(frame)

        else:
            await self.push_frame(frame)

    async def _generate_audio(self, text: str, sentence_index: int):
        """Send text to Kokoro daemon, receive audio chunks."""
        if not self._daemon_process or self._daemon_process.poll() is not None:
            logger.error("TTS daemon not running, restarting...")
            await self._start_daemon()
            if not self._daemon_process:
                return

        voice = AGENT_VOICES.get(self._current_agent, "af_nicole")
        speed = AGENT_SPEEDS.get(self._current_agent, 1.0)

        request = json.dumps({
            "text": text,
            "voice": voice,
            "speed": speed,
            "stream": True,  # Request chunked output
        }) + "\n"

        loop = asyncio.get_event_loop()

        try:
            # Send request to daemon (run in executor to avoid blocking)
            await loop.run_in_executor(
                None,
                self._daemon_process.stdin.write,
                request.encode(),
            )
            await loop.run_in_executor(
                None,
                self._daemon_process.stdin.flush,
            )

            # Read audio chunks from daemon
            while not self._interrupted:
                line = await loop.run_in_executor(
                    None,
                    self._daemon_process.stdout.readline,
                )

                if not line:
                    break

                try:
                    response = json.loads(line.decode())
                except json.JSONDecodeError:
                    continue

                if response.get("type") == "audio_chunk":
                    import base64
                    audio_bytes = base64.b64decode(response["audio"])
                    mouth_sync = response.get("mouth_sync", [])

                    await self.push_frame(AudioOutputFrame(
                        audio=audio_bytes,
                        sample_rate=response.get("sample_rate", 24000),
                        mouth_sync=mouth_sync,
                        is_final=response.get("is_final", False),
                    ))

                elif response.get("type") == "done":
                    break

                elif response.get("type") == "error":
                    logger.error(f"TTS error: {response.get('message')}")
                    break

        except Exception as e:
            logger.error(f"TTS generation error: {e}")

    async def _interrupt_daemon(self):
        """Send interrupt signal to daemon."""
        if self._daemon_process and self._daemon_process.poll() is None:
            try:
                interrupt = json.dumps({"type": "interrupt"}) + "\n"
                self._daemon_process.stdin.write(interrupt.encode())
                self._daemon_process.stdin.flush()
            except Exception:
                pass
