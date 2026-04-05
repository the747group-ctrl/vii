# VII Two — Technical Architecture

## Design Principles

1. **Stream everything** — No buffering full responses. LLM tokens flow to TTS, audio flows to speaker immediately.
2. **Rust for speed, Python for flexibility** — Rust handles hotkey + STT (latency-critical). Python handles pipeline orchestration (needs Pipecat/asyncio).
3. **Agent-first** — Every interaction routes through an agent personality. No generic assistant mode.
4. **Phone-native** — Telegram is the remote interface. Full laptop control from your pocket.
5. **Skin-driven visuals** — Every agent has a skin pack. Animations, glow, transitions defined in JSON.

## Component Architecture

### 1. Rust STT Binary (`rust-stt/`)

Carried forward from VII Zero. Responsibilities:
- Hotkey capture (Left Ctrl / Unknown(76|83))
- Audio recording via CoreAudio
- Whisper.cpp transcription (~144ms)
- Agent dispatch parsing ("Hey Bob, ...")
- IPC to Python pipeline via Unix socket

**VII Two changes:**
- Output transcription to pipeline engine (not directly to API)
- Accept pipeline commands (interrupt, mode switch)
- New IPC protocol: JSON messages over Unix domain socket

### 2. Pipeline Engine (`core/pipeline/`)

New in VII Two. Python asyncio service inspired by DecisionsAI's Pipecat integration.

**Frame types:**
- `TextFrame` — LLM output text chunk
- `AudioFrame` — Raw audio bytes + sample rate
- `InterruptionFrame` — Kill current response
- `AgentSwitchFrame` — Change active agent
- `StateFrame` — Pipeline state change (idle/listening/thinking/speaking)

**Pipeline topology:**
```
STT Input → Agent Router → LLM Service → Text Cleaner → TTS Service → Audio Output
                                                                    ↓
                                                              Overlay IPC
```

**Key patterns from DecisionsAI:**
- Sentence-boundary extraction before TTS (handles decimals, versions)
- Smart quote normalization for phonemization
- Hot-swappable LLM/TTS services mid-conversation
- Playback watermark for drain tracking

### 3. TTS Daemon (`scripts/tts-daemon.py`)

Upgraded from VII Zero. Changes:
- Accept streaming text input (sentence-by-sentence, not full response)
- Output streaming audio chunks (not wait for full generation)
- Mouth sync data per chunk (RMS levels at 20Hz)
- Speed control (time stretcher with overlap-add)

### 4. Echo Cancellation (`core/echo/`)

New in VII Two. Ported from DecisionsAI's `echo_canceller.py`.

**Architecture:**
- Block NLMS adaptive filter (vectorized numpy, 50-100x faster than sample-by-sample)
- Reference buffer shared between audio output and AEC filter
- Dual-gate interruption: echo gate (energy threshold) + pipeline gate (suppress false VAD)
- Playback watermark: deactivate AEC only after hardware buffer drains

### 5. Swift Overlay (`overlay/swift/`)

Upgraded from VII Zero. Changes:
- Adopt skin.json config format per agent
- WebM animation playback (per state: idle, thinking, speaking)
- Glow engine (4 styles: breathing, pulse, fade, flash)
- Chat bubble overlay (auto-positioning, word-wrap)
- Agent selection UI (grid/wheel overlay on tap)
- State machine with user-priority blocking

### 6. Agent Skins (`overlay/skins/`)

New in VII Two. One folder per agent:
```
skins/bob/
  skin.json          # Config: events, transitions, rendering
  idle.webm          # Idle animation
  thinking.webm      # Thinking animation
  speaking.webm      # Speaking animation
  idle-thinking.webm # Transition animation (optional)
```

### 7. Telegram Remote (`remote/telegram/`)

New in VII Two. Ported from DecisionsAI's integration pattern.

**Components:**
- `bot.py` — Telegram bot setup, command handlers
- `remote_control.py` — Screen capture, click, type, scroll
- `voice_handler.py` — Voice message round-trip (OGG→WAV→STT→LLM→TTS→OGG)
- `security.py` — HMAC-SHA256 envelope, daily-rotating channel hash
- `screen.py` — Screenshot → WebP encoding → base64 transmission

**Commands:**
- `/screen` — Get current screen screenshot
- `/click x,y` — Click at coordinates
- `/type text` — Type text via AppleScript
- `/voice` — Send voice message, get voice response
- `/agent bob` — Switch active agent
- `/status` — VII system status

### 8. Web UI (`remote/web-ui/`)

New in VII Two. Local-only FastAPI server for preferences and settings.
- Model selection (Claude model, TTS voice)
- Agent configuration
- Skin preview
- Chat history browser
- Remote access link generator

## IPC Protocol

All components communicate via Unix domain sockets with JSON messages:

```json
{
  "type": "transcription",
  "agent": "bob",
  "text": "What's the status of the morning brief?",
  "timestamp": 1712380800
}
```

```json
{
  "type": "tts_chunk",
  "audio": "<base64>",
  "sample_rate": 24000,
  "mouth_sync": [0.2, 0.8, 0.5, 0.3],
  "is_final": false
}
```

```json
{
  "type": "state_change",
  "from": "thinking",
  "to": "speaking",
  "agent": "bob"
}
```

## Security

- All Telegram messages wrapped in HMAC-SHA256 envelope
- Daily-rotating channel hash (MD5 of chat_id + date)
- Internal API protected by runtime token (secrets.token_urlsafe)
- No remote access without Telegram authentication
- Screen capture never stored to disk (memory-only WebP encode)

## Performance Targets

| Metric | VII Zero | VII Two Target |
|--------|----------|----------------|
| STT latency | 144ms | 144ms (unchanged) |
| LLM first token | 800ms | 800ms (unchanged) |
| LLM to first audio | 4-6s | <500ms (streaming) |
| Total end-to-end | 5-8s | <2s |
| Echo cancellation | None | <10ms per frame |
| Screen capture | N/A | <200ms (WebP) |
