"""
VII Two — Frame processor base class.
Each pipeline stage is a processor that receives frames and pushes frames downstream.
"""

import asyncio
import logging
from typing import Optional
from .frames import Frame

logger = logging.getLogger("vii.pipeline")


class FrameProcessor:
    """Base class for all pipeline processors."""

    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__
        self._next: Optional[FrameProcessor] = None
        self._prev: Optional[FrameProcessor] = None
        self._running = False

    async def start(self):
        """Initialize the processor."""
        self._running = True
        logger.info(f"[{self.name}] Started")

    async def stop(self):
        """Clean up the processor."""
        self._running = False
        logger.info(f"[{self.name}] Stopped")

    async def process_frame(self, frame: Frame):
        """Process an incoming frame. Override in subclasses."""
        await self.push_frame(frame)

    async def push_frame(self, frame: Frame):
        """Push a frame to the next processor in the pipeline."""
        if self._next and self._running:
            await self._next.process_frame(frame)

    async def push_frame_upstream(self, frame: Frame):
        """Push a frame back upstream (e.g., InterruptionFrame)."""
        if self._prev:
            await self._prev.process_frame(frame)


class Pipeline:
    """
    Linear frame pipeline. Connects processors in sequence.
    Frames flow from first to last processor.

    Usage:
        pipeline = Pipeline([
            stt_processor,
            agent_router,
            llm_service,
            text_cleaner,
            tts_service,
            audio_output,
        ])
        await pipeline.start()
        await pipeline.push(TranscriptionFrame(text="Hello Bob"))
    """

    def __init__(self, processors: list[FrameProcessor]):
        self.processors = processors
        self._link_processors()

    def _link_processors(self):
        """Chain processors: each one's _next points to the next."""
        for i in range(len(self.processors) - 1):
            self.processors[i]._next = self.processors[i + 1]
            self.processors[i + 1]._prev = self.processors[i]

    async def start(self):
        """Start all processors."""
        for p in self.processors:
            await p.start()

    async def stop(self):
        """Stop all processors in reverse order."""
        for p in reversed(self.processors):
            await p.stop()

    async def push(self, frame: Frame):
        """Push a frame into the pipeline (enters at first processor)."""
        if self.processors:
            await self.processors[0].process_frame(frame)

    def swap_processor(self, old: FrameProcessor, new: FrameProcessor):
        """Hot-swap a processor in the running pipeline (DecisionsAI pattern)."""
        for i, p in enumerate(self.processors):
            if p is old:
                self.processors[i] = new
                # Re-link chain
                if old._prev:
                    old._prev._next = new
                    new._prev = old._prev
                if old._next:
                    new._next = old._next
                    old._next._prev = new
                new._running = old._running
                logger.info(f"Swapped [{old.name}] -> [{new.name}]")
                return True
        return False
