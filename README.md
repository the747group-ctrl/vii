# VII Two — Voice Intelligence Interface v2

**The upgrade. The market-ready build. The Apple pitch.**

VII Two builds on the foundation of VII Zero (Phases 1-7) with a reimagined streaming architecture. Inspired by the best open source voice AI work — including DecisionsAI, Keith Schacht's Task Master, and emerging patterns from the wider voice AI community — VII Two is an original creation designed to be the voice interface people actually love using.

## Vision

A voice-first AI interface so smooth, so fast, and so beautiful that Apple (or any major platform) would want to ship it natively. Multiple AI agents with unique voices and personalities, controllable from your desk or your phone.

## What's New in VII Two

| Feature | VII Zero | VII Two |
|---------|----------|---------|
| Response latency | 5-8s | <2s (streaming pipeline) |
| Remote access | None | Full laptop control from phone via Telegram |
| Avatar animations | Static PNG | WebM with state-driven glow effects |
| Agent selection | Voice-only dispatch | Voice + visual selection overlay |
| Echo cancellation | None | NLMS adaptive filter + dual-gate interruption |
| Hands-free mode | Push-to-talk only | Continuous listening with echo gating |
| Computer control | Respond only | Execute actions (open apps, run scripts) |

## Architecture

```
                    +------------------+
                    |   User (Voice)   |
                    +--------+---------+
                             |
                    +--------v---------+
                    | Rust STT Binary  |  <-- Whisper.cpp, ~144ms
                    | (hotkey capture)  |
                    +--------+---------+
                             |
                    +--------v---------+
                    | Pipeline Engine   |  <-- Pipecat-inspired streaming
                    | (Python/asyncio)  |
                    +--------+---------+
                             |
              +--------------+--------------+
              |                             |
     +--------v---------+         +--------v---------+
     | Claude API        |         | Agent Router     |
     | (streaming)       |         | (Bob/Falcon/etc) |
     +--------+---------+         +------------------+
              |
     +--------v---------+
     | TTS Daemon        |  <-- Kokoro, sentence-by-sentence
     | (streaming audio) |
     +--------+---------+
              |
     +--------v---------+
     | Swift Overlay     |  <-- Animated avatars, glow, bubbles
     +------------------+

     +------------------+
     | Telegram Remote   |  <-- Screen share, click, type from phone
     | (FastAPI + Bot)   |
     +------------------+
```

## Project Structure

```
vii-two/
  core/                  # Voice pipeline engine
    pipeline/            # Pipecat-inspired streaming orchestrator
    audio/               # Audio I/O, playback, time stretching
    echo/                # NLMS echo cancellation
  overlay/               # Visual layer
    swift/               # WhisperOverlay.app source (upgraded)
    skins/               # Agent avatar packs (skin.json + WebM)
  remote/                # Phone access
    telegram/            # Telegram bot + remote control
    web-ui/              # Local web UI for preferences
    screen-capture/      # Screenshot + WebP encoding
  rust-stt/              # Rust STT binary (from VII Zero, upgraded)
  scripts/               # TTS daemon, utilities
  config/                # Settings, avatars, dictionary
  models/ -> symlink     # Whisper + Kokoro models (shared with VII Zero)
  docs/                  # Architecture, specs, API docs
```

## Rollback

VII Zero is preserved at `~/.openclaw/workspace/projects/local-whisper/` (git tag: `vii-zero`). The deployed binary at `/Applications/Whisper Dictation.app/` is untouched.

## Tech Stack

- **STT:** Whisper.cpp via Rust (native ARM64, 144ms)
- **LLM:** Claude API (streaming)
- **TTS:** Kokoro-82M (local, 0.35x RTF)
- **Pipeline:** Python asyncio (Pipecat-inspired)
- **Overlay:** Swift/AppKit (macOS native)
- **Remote:** FastAPI + python-telegram-bot
- **Echo:** NLMS adaptive filter (numpy vectorized)

## Inspiration & Open Source References

- **DecisionsAI** — Open source voice desktop assistant (Pipecat pipeline, Telegram integration)
- **Keith Schacht's Task Master** — Voice-first UX patterns (LiveKit, real-time updates)
- **VII Zero** — Our own foundation (`~/.openclaw/workspace/projects/local-whisper/`)

---

*Developed by The 747 Lab*
