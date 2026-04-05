# Keith Schacht Patterns — What VII Two Steals

## Source: Keith Schacht (@keith__schacht)
- Ex-Facebook PM, sold Mystery Science for $140M
- Now building AI demos that feel SMOOTH
- Task Master: taskmaster.keithschacht.com (voice-first todo, real-time updates)
- Clippy: clippy.keithschacht.com (screen-aware voice AI)

## Task Master — The Snappy Voice UX

### What Makes It Feel Fast

1. **Breathing circle** as mic button — 4.5s animation cycle, meditative feel, always pulsing
   - NOT a static button. The animation tells you "I'm alive, I'm waiting"
   - Glow intensifies on hover

2. **LiveKit WebRTC** for voice — direct connection, no HTTP round-trips
   - Browser → LiveKit Cloud → Agent (server-side processing)
   - WebRTC eliminates the latency of HTTP uploads
   - Voice streams in real-time, not after recording stops

3. **Turbo Streams + ActionCable** for instant UI updates
   - Tasks appear/move/complete WHILE you're still talking
   - No "processing..." state — changes happen mid-sentence
   - All connected browsers see updates simultaneously

4. **ElevenLabs TTS** for response voice (not Kokoro)
   - Premium voice quality drives the "polished" perception

5. **CSS transitions with easing curves** — cubic-bezier(0.4, 0, 0.6, 1)
   - Hardware-accelerated (transform/opacity only)
   - No layout thrashing

6. **Undo pattern** — every action returns undo instructions
   - "Actually, undo that" works naturally
   - Safe, reversible operations

### Wake Word Activation
- "Say Task Master" to start
- "Stop listening" to deactivate
- Audio NOT sent to server while inactive (privacy)
- Client-side wake word detection

### The Architecture That Enables Speed
```
Browser (mic) → WebRTC → LiveKit Cloud → Agent (Python)
                                            ↓
                                    Whisper STT (streaming)
                                            ↓
                                    LLM (tool calls)
                                            ↓
                                    Rails API (CRUD)
                                            ↓
                                    ActionCable broadcast
                                            ↓
                                    All browsers update instantly
```

## Clippy — Screen-Aware Voice AI

### Key Patterns
1. **getDisplayMedia** — browser screen sharing API
2. **Client-side wake word** — "Clippy" detected locally, no server call until activated
3. **Tool-callable screenshots** — model can request fresh screenshots for more context
4. **Points to where to click** — spatial understanding of screen content

### What VII Two Takes From This
- The screen-awareness pattern is PERFECT for VII's agent actions
- "Bob, what's on my screen?" → screenshot → Claude vision → spoken response
- "Pixi, help me with this design" → screenshot → creative feedback
- Integrates naturally with our Telegram remote control (send screenshot + voice context)

## Integration Plan for VII Two

### From Task Master:
1. **Breathing circle mic button** → Port to VII overlay (replace static avatar trigger)
2. **LiveKit WebRTC** → Evaluate replacing our Unix socket IPC for lower-latency voice streaming
3. **Real-time UI updates** → Tasks/actions update WHILE the agent speaks
4. **Undo pattern** → Every agent action is reversible by voice
5. **Wake word with privacy** → Local detection, no server call until activated

### From Clippy:
1. **Screen awareness** → Agent can see your screen when asked
2. **Spatial pointing** → "Click here" with visual indicator
3. **Context-rich responses** → Agent understands what you're looking at

### Speed Improvements for VII Two:
- Current: Hotkey → Record → Stop → Transcribe → API → TTS → Play (5-8s)
- Keith's pattern: Wake word → Streaming audio → Streaming transcription → Streaming LLM → Streaming TTS (< 1s)
- The key difference: EVERYTHING is streaming. No step waits for the previous step to fully complete.
