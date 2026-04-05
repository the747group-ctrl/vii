"""
VII Two — Streaming LLM service.
Calls Claude API with streaming, pushes TextFrames per token.
"""

import asyncio
import json
import logging
import os
from typing import Optional

from .processor import FrameProcessor
from .frames import (
    Frame, TranscriptionFrame, TextFrame, SentenceFrame,
    InterruptionFrame, StateChangeFrame, PipelineState, AgentName,
)

logger = logging.getLogger("vii.pipeline.llm")

# Agent system prompts
AGENT_PROMPTS = {
    AgentName.BOB: (
        "You are Bob, the lead strategist of The 747 Lab. "
        "Deep, authoritative voice. Speak in 2-3 concise sentences. "
        "ROI-focused. Every answer connects to the bigger picture. "
        "No markdown, no lists — speak naturally as if in conversation."
    ),
    AgentName.FALCON: (
        "You are Falcon, the intelligence analyst of The 747 Lab. "
        "Measured, professional tone. Speak in 2-3 concise sentences. "
        "Always cite confidence levels. Analytical and precise. "
        "No markdown, no lists — speak naturally."
    ),
    AgentName.ACE: (
        "You are Ace, the operations specialist of The 747 Lab. "
        "British accent personality, efficient and direct. 2-3 sentences. "
        "Think checklists. Status reports. Risk flags. "
        "No markdown — speak naturally."
    ),
    AgentName.PIXI: (
        "You are Pixi, the creative director of The 747 Lab. "
        "Expressive, enthusiastic tone. 2-3 concise sentences. "
        "Visual-first thinking. Design intuition. Indie polish. "
        "No markdown — speak naturally."
    ),
    AgentName.BUZZ: (
        "You are Buzz, the content strategist of The 747 Lab. "
        "Playful, energetic voice. 2-3 concise sentences. "
        "Story-driven. Audience-aware. Tone-conscious. "
        "No markdown — speak naturally."
    ),
    AgentName.CLAUDE: (
        "You are Claude, a helpful AI assistant. "
        "Speak in 2-3 concise, natural sentences. "
        "No markdown, no lists — conversational tone."
    ),
}

DEFAULT_PROMPT = AGENT_PROMPTS[AgentName.CLAUDE]


class StreamingLLMService(FrameProcessor):
    """
    Calls Claude API with streaming enabled.
    Pushes TextFrame per token chunk for immediate TTS consumption.

    This is the key speed improvement over VII Zero:
    - VII Zero: wait for full response → send to TTS → wait for full audio → play
    - VII Two: stream tokens → TTS starts on first sentence → playback starts on first audio
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-6-20250514"):
        super().__init__(name="StreamingLLM")
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self.max_tokens = 300  # Voice responses should be short
        self._current_agent = AgentName.BOB
        self._conversation_history: list[dict] = []
        self._interrupted = False
        self._current_task: Optional[asyncio.Task] = None

    async def process_frame(self, frame: Frame):
        if isinstance(frame, TranscriptionFrame):
            # User said something — call LLM
            if frame.agent:
                self._current_agent = frame.agent

            # Signal thinking state
            await self.push_frame(StateChangeFrame(
                to_state=PipelineState.THINKING,
                agent=self._current_agent,
            ))

            # Stream the response
            self._interrupted = False
            self._current_task = asyncio.current_task()
            await self._stream_response(frame.text)

        elif isinstance(frame, InterruptionFrame):
            # User interrupted — stop generation
            self._interrupted = True
            logger.info("LLM generation interrupted")
            await self.push_frame(frame)  # Pass downstream to kill TTS too

        else:
            await self.push_frame(frame)

    async def _stream_response(self, user_text: str):
        """Call Claude API with streaming and push TextFrames."""
        import httpx

        system_prompt = AGENT_PROMPTS.get(self._current_agent, DEFAULT_PROMPT)

        # Build messages
        self._conversation_history.append({
            "role": "user",
            "content": user_text,
        })

        # Keep last 10 turns for context (voice conversations are short)
        messages = self._conversation_history[-20:]

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "messages": messages,
            "stream": True,
        }

        full_response = ""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream(
                    "POST",
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if self._interrupted:
                            break

                        if not line.startswith("data: "):
                            continue

                        data = line[6:]
                        if data == "[DONE]":
                            break

                        try:
                            event = json.loads(data)
                        except json.JSONDecodeError:
                            continue

                        # Extract text delta
                        if event.get("type") == "content_block_delta":
                            delta = event.get("delta", {})
                            text = delta.get("text", "")
                            if text:
                                full_response += text
                                await self.push_frame(TextFrame(text=text))

        except httpx.HTTPStatusError as e:
            logger.error(f"Claude API error: {e.response.status_code}")
            await self.push_frame(TextFrame(
                text="Sorry, I couldn't process that request."
            ))
        except Exception as e:
            logger.error(f"LLM streaming error: {e}")
            await self.push_frame(TextFrame(
                text="Something went wrong. Try again."
            ))

        # Store assistant response in history
        if full_response:
            self._conversation_history.append({
                "role": "assistant",
                "content": full_response,
            })

        # Signal end of response (TextCleaner will flush remaining buffer)
        await self.push_frame(StateChangeFrame(
            to_state=PipelineState.SPEAKING,
            agent=self._current_agent,
        ))
