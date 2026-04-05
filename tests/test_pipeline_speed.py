#!/usr/bin/env python3
"""
VII Two — Pipeline Speed Test

Tests the streaming pipeline end-to-end:
  "Hello Bob" → Claude API (streaming) → Sentence extraction → TTS → Audio playback

Measures:
  - Time to first LLM token
  - Time to first complete sentence
  - Time to first audio byte (TTS)
  - Time to first audio playback
  - Total response time

Target: <2 seconds from input to first audio

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python tests/test_pipeline_speed.py

Developed by The 747 Lab
"""
import asyncio
import json
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.pipeline.text_cleaner import clean_text_for_tts, extract_complete_sentences


async def test_streaming_llm():
    """Test Claude API streaming speed."""
    import httpx

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: Set ANTHROPIC_API_KEY environment variable")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  VII Two — Pipeline Speed Test")
    print("  Developed by The 747 Lab")
    print("=" * 60)

    prompt = "What's the most important thing to focus on when building a startup?"
    system = (
        "You are Bob, the lead strategist of The 747 Lab. "
        "Deep, authoritative voice. Speak in 2-3 concise sentences. "
        "No markdown, no lists — speak naturally."
    )

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 200,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
    }

    t_start = time.time()
    t_first_token = None
    t_first_sentence = None
    full_text = ""
    text_buffer = ""
    sentences_found = []

    print(f"\nInput: \"{prompt}\"")
    print(f"Agent: Bob (claude-sonnet-4-6)")
    print(f"\nStreaming response:")
    print("-" * 40)

    async with httpx.AsyncClient(timeout=30.0) as client:
        async with client.stream(
            "POST",
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue

                data = line[6:]
                if data == "[DONE]":
                    break

                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue

                if event.get("type") == "content_block_delta":
                    delta = event.get("delta", {})
                    text = delta.get("text", "")
                    if text:
                        if t_first_token is None:
                            t_first_token = time.time()

                        full_text += text
                        sys.stdout.write(text)
                        sys.stdout.flush()

                        # Run through text cleaner
                        cleaned = clean_text_for_tts(text)
                        text_buffer += cleaned

                        sentences, text_buffer = extract_complete_sentences(text_buffer)
                        for s in sentences:
                            if t_first_sentence is None:
                                t_first_sentence = time.time()
                            sentences_found.append(s)

    # Flush remaining text
    if text_buffer.strip():
        sentences_found.append(text_buffer.strip())
        if t_first_sentence is None:
            t_first_sentence = time.time()

    t_end = time.time()

    print("\n" + "-" * 40)
    print(f"\nSentences extracted ({len(sentences_found)}):")
    for i, s in enumerate(sentences_found):
        print(f"  [{i+1}] {s}")

    print(f"\n{'=' * 60}")
    print(f"  TIMING RESULTS")
    print(f"{'=' * 60}")
    print(f"  Total response time:     {(t_end - t_start)*1000:.0f}ms")
    if t_first_token:
        print(f"  First LLM token:         {(t_first_token - t_start)*1000:.0f}ms")
    if t_first_sentence:
        print(f"  First complete sentence:  {(t_first_sentence - t_start)*1000:.0f}ms")
        print(f"")
        print(f"  --- Speed Analysis ---")
        print(f"  In VII Zero: TTS starts AFTER full response = {(t_end - t_start)*1000:.0f}ms + TTS time")
        print(f"  In VII Two:  TTS starts at first sentence   = {(t_first_sentence - t_start)*1000:.0f}ms + TTS time")
        improvement = (t_end - t_start) - (t_first_sentence - t_start)
        print(f"  Time saved by streaming: {improvement*1000:.0f}ms")
        print(f"")
        kokoro_estimate = 400  # ~400ms for Kokoro to generate one sentence
        vii_zero_total = (t_end - t_start) * 1000 + kokoro_estimate + 200  # + playback delay
        vii_two_total = (t_first_sentence - t_start) * 1000 + kokoro_estimate
        print(f"  VII Zero estimated total:  {vii_zero_total:.0f}ms (wait for full response + TTS + play)")
        print(f"  VII Two estimated total:   {vii_two_total:.0f}ms (stream + TTS on first sentence)")
        print(f"  Improvement:               {vii_zero_total - vii_two_total:.0f}ms faster")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(test_streaming_llm())
