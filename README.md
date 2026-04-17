# VII — Voice Intelligence Interface

**Talk to your Mac. It listens, thinks, and acts.**

VII is a voice-controlled AI desktop assistant. A floating orb lives on your screen — click it and speak. It answers questions, opens apps, controls your computer, remembers conversations, and sees your screen.

The intelligence of ChatGPT with the hands of Siri, running on your machine.

Developed by [The 747 Lab](https://747lab.ai).

---

## Features

- **Voice control** — Click the orb or go hands-free. Speak naturally.
- **Computer control** — "Open Safari", "Search for flights to Tokyo", "Take a screenshot"
- **Screen awareness** — "What's on my screen?" — VII sees and understands your display
- **Conversation memory** — Remembers what you've talked about across sessions
- **Customizable** — Multiple skins, voices, LLM providers, TTS engines
- **Remote access** — Control your Mac from your phone, from anywhere
- **Private** — STT and TTS run locally. Your voice never leaves your machine.

## Quick Start

```bash
# Install
git clone https://github.com/the747group-ctrl/vii.git ~/.vii
cd ~/.vii
python3 -m venv venv
./venv/bin/pip install PyQt6 sounddevice soundfile numpy httpx kokoro-onnx faster-whisper fastapi uvicorn pynput Pillow sqlalchemy

# Run
./venv/bin/python3 desktop.py
```

Or use the installer:
```bash
bash install.sh
```

## How It Works

1. Click the floating orb (or enable hands-free mode)
2. Speak — Whisper transcribes your voice locally
3. Claude thinks — streaming response, first words in under 2 seconds
4. VII acts — opens apps, searches the web, types text, or just responds
5. Kokoro speaks — response played through your speakers

## What Can VII Do?

| Say This | VII Does This |
|----------|--------------|
| "Open Safari" | Opens Safari |
| "Search for voice AI startups" | Opens browser with search results |
| "Take a screenshot" | Captures your screen |
| "Turn the volume to 50" | Adjusts system volume |
| "What's on my screen?" | Analyzes your display and describes it |
| "Remember, I have a meeting at 3" | Saves to conversation memory |
| "What did I say about the meeting?" | Recalls from memory |

## Settings

Right-click the orb → **Preferences** to configure:
- LLM provider (Claude, Ollama local, OpenAI, Groq, OpenRouter)
- TTS voice and speed
- Audio input/output device
- Mic gain
- Hands-free mode / VAD sensitivity
- Skin appearance

## Remote Access

Start the remote server to control your Mac from your phone:
```bash
./venv/bin/python3 remote_server.py
```

Or launch everything at once:
```bash
./start.sh
```

This starts the desktop orb + remote server + Cloudflare tunnel. Access your Mac from anywhere in the world.

## Architecture

```
Voice → Whisper STT (local) → Claude API (streaming) → Action Execution
                                                      → Kokoro TTS (local) → Speaker
```

- **STT:** faster-whisper (local, ~1s transcription)
- **LLM:** Claude Sonnet 4 (streaming) or Ollama (local)
- **TTS:** Kokoro-82M (local, multiple voices)
- **UI:** PyQt6 floating orb with state-driven glow
- **PC Control:** AppleScript bridge via mac-control.sh
- **Vision:** Claude vision API with screenshot capture
- **Storage:** SQLite for conversation persistence
- **Remote:** FastAPI + Cloudflare Tunnel

## Requirements

- macOS 14+
- Python 3.11+
- Anthropic API key (or Ollama for free local LLM)
- Microphone

## License

Built on open source foundations. Inspired by the voice AI community.

---

*VII — Just speak.*
*The 747 Lab*
