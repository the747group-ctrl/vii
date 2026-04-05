"""
VII Two — Pipeline orchestrator.
The main entry point that wires everything together and provides
the interface between the Rust STT binary and the Python pipeline.

Listens on a Unix domain socket for transcriptions from the Rust binary,
runs them through the streaming pipeline, and manages lifecycle.
"""

import asyncio
import json
import logging
import os
import socket
from pathlib import Path
from typing import Optional

from .processor import Pipeline
from .frames import (
    TranscriptionFrame, InterruptionFrame, AgentSwitchFrame,
    AgentName, StartFrame, StopFrame,
)
from .text_cleaner import TextCleaner
from .llm_service import StreamingLLMService
from .tts_service import StreamingTTSService
from .audio_output import AudioOutputProcessor

logger = logging.getLogger("vii.pipeline")

SOCKET_PATH = "/tmp/vii-pipeline.sock"


class VIIPipelineOrchestrator:
    """
    Main orchestrator for VII Two's voice pipeline.

    Architecture:
        Rust Binary --[Unix Socket]--> Orchestrator --> Pipeline --> Audio Output
                                                                --> Overlay IPC

    The Rust binary handles:
        - Hotkey capture
        - Audio recording
        - Whisper STT
        - Agent dispatch parsing

    The Python pipeline handles:
        - Streaming LLM calls
        - Sentence extraction
        - Streaming TTS
        - Audio playback
        - Overlay communication
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.pipeline: Optional[Pipeline] = None
        self._server: Optional[asyncio.AbstractServer] = None
        self._running = False

    async def start(self):
        """Initialize and start the pipeline."""
        logger.info("Starting VII Two pipeline orchestrator...")

        # Build pipeline
        llm = StreamingLLMService(api_key=self.api_key)
        text_cleaner = TextCleaner()
        tts = StreamingTTSService()
        audio_out = AudioOutputProcessor()

        self.pipeline = Pipeline([
            llm,
            text_cleaner,
            tts,
            audio_out,
        ])

        await self.pipeline.start()

        # Start Unix socket server for Rust binary IPC
        await self._start_socket_server()

        self._running = True
        logger.info("VII Two pipeline running. Waiting for input on %s", SOCKET_PATH)

    async def stop(self):
        """Shut down the pipeline."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if self.pipeline:
            await self.pipeline.stop()
        # Clean up socket
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)
        logger.info("VII Two pipeline stopped.")

    async def _start_socket_server(self):
        """Start Unix domain socket server for Rust STT binary."""
        # Clean up stale socket
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)

        self._server = await asyncio.start_unix_server(
            self._handle_connection,
            path=SOCKET_PATH,
        )
        # Make socket accessible
        os.chmod(SOCKET_PATH, 0o666)

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming connection from Rust binary."""
        try:
            while self._running:
                line = await reader.readline()
                if not line:
                    break

                try:
                    msg = json.loads(line.decode())
                except json.JSONDecodeError:
                    continue

                await self._handle_message(msg)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Connection handler error: {e}")
        finally:
            writer.close()

    async def _handle_message(self, msg: dict):
        """Route incoming message from Rust binary to pipeline."""
        msg_type = msg.get("type", "")

        if msg_type == "transcription":
            # User speech transcribed — run through pipeline
            agent_str = msg.get("agent")
            agent = None
            if agent_str:
                try:
                    agent = AgentName(agent_str.lower())
                except ValueError:
                    agent = AgentName.BOB  # Default

            frame = TranscriptionFrame(
                text=msg.get("text", ""),
                agent=agent,
            )
            logger.info(f"Transcription: [{agent or 'auto'}] {frame.text}")
            await self.pipeline.push(frame)

        elif msg_type == "interrupt":
            # User pressed hotkey or spoke during response
            await self.pipeline.push(InterruptionFrame())

        elif msg_type == "agent_switch":
            # Explicit agent switch command
            try:
                agent = AgentName(msg.get("agent", "bob").lower())
                await self.pipeline.push(AgentSwitchFrame(agent=agent))
            except ValueError:
                pass

        elif msg_type == "shutdown":
            await self.stop()

    async def inject_text(self, text: str, agent: Optional[str] = None):
        """
        Inject text directly into the pipeline (for Telegram remote, testing, etc.)
        Bypasses the Rust STT binary.
        """
        agent_enum = None
        if agent:
            try:
                agent_enum = AgentName(agent.lower())
            except ValueError:
                pass

        frame = TranscriptionFrame(text=text, agent=agent_enum)
        if self.pipeline:
            await self.pipeline.push(frame)


async def main():
    """Run the VII Two pipeline as a standalone service."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    orchestrator = VIIPipelineOrchestrator()

    try:
        await orchestrator.start()
        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await orchestrator.stop()


if __name__ == "__main__":
    asyncio.run(main())
