# VII Two — Frontend & UX Specification

## Design Philosophy

VII Two must feel like an Apple product demo. Every interaction has visual feedback.
No loading spinners. No modal dialogs. No dead moments. The UI is alive.

## What Makes Great Voice UI Feel "Snappy" (Design Principles)

### 1. Immediate Visual Feedback on Every State Change
- User speaks → glow starts INSTANTLY (not after transcription completes)
- LLM thinking → glow shifts to pulse pattern
- TTS speaking → glow intensifies + chat bubble appears
- Done → smooth fade back to idle
- **Zero dead moments.** Always animating something.

### 2. Breathing Glow Engine (4 Styles)
```
breathing: sinusoidal alpha 0.3→1.0, continuous (thinking, processing)
pulse:     same math, faster speed (listening, active)
fade:      InOutCubic easing, forward+backward (transitions)
flash:     N-cycle burst then stop (interrupts, errors)
```
- 60fps tick rate (16ms intervals)
- Color per agent (Bob=blue, Pixi=pink, Falcon=green, Ace=amber, Buzz=purple)
- Configurable in skin.json per event

### 3. Instant Interaction Model
- 5px drag threshold (prevents accidental moves, feels instant once triggered)
- No confirmation dialogs — all actions are immediate and reversible
- Context menu refreshes state before showing (never stale)
- Position saved on every drag release (persists across sessions)

### 4. Chat Bubble Overlay
- Rounded rectangle + triangular tail pointing at avatar
- 260px max width, auto word-wrap
- Auto-positions above avatar, flips below if no room
- Translucent white background (240/255 alpha)
- Appears during speaking, fades after TTS completes
- Shows abbreviated response text (what the agent is saying)

### 5. Ping-Pong Animation
- Idle animations play forward then backward (more natural than loop)
- 24fps frame rate (42ms per frame)
- Smooth crossfade between agent switches

### 6. macOS-Specific Polish
- NSWindow.Level.floating for always-on-top
- Re-assert on-top level every 5 seconds (Qt/AppKit can lose it during Space switching)
- Clean exit: hide → stop animations → stop glow → quit (no orphaned processes)

## VII Two Overlay States

```
IDLE        → Agent avatar, idle animation, no glow
LISTENING   → Breathing glow (agent color), listening animation
THINKING    → Pulse glow (faster), thinking animation, "..." bubble
SPEAKING    → Pulse glow (brightest), speaking animation, text bubble
INTERRUPTED → Flash glow (2 cycles), snap back to IDLE
SELECTING   → Agent selection grid overlay (new feature)
```

### User-Priority Blocking (from DecisionsAI)
If user is in LISTENING or SELECTING state, background events (like TTS completion)
cannot override it. User actions always take priority.

## Agent Selection UI (New Feature)

**Two Modes:**

### Voice Selection (existing, improved)
- "Hey Bob" / "Falcon, what's..." → dispatch by name
- Avatar crossfades to selected agent within 200ms
- Glow color transitions smoothly

### Visual Selection (new)
- Tap/click the overlay → agent grid appears
- Grid layout: 2x3 (Bob, Falcon, Ace, Pixi, Buzz, Claude)
- Each agent shows: avatar thumbnail + name + one-line role
- Tap agent → grid closes, avatar switches, glow transitions
- Grid auto-closes after 5s of no interaction
- Keyboard shortcut: Ctrl+1-6 for quick agent switch

### Selection Grid Design
```
+--------+--------+--------+
|  BOB   | FALCON |  ACE   |
| Strategy| Intel  |  Ops   |
+--------+--------+--------+
|  PIXI  |  BUZZ  | CLAUDE |
| Create | Content| General|
+--------+--------+--------+
```
- Dark translucent background (navy, 85% opacity)
- Agent thumbnails with subtle glow ring showing their color
- Selected agent has brighter glow + slight scale up (1.1x)
- Smooth appear/disappear animation (200ms ease-in-out)

## Web UI Design (Settings & Remote)

### Color Palette (747 Brand)
```
Background:     #0d1117 (GitHub dark)
Surface:        #161b22
Border:         rgba(255,255,255,0.1)
Text Primary:   #f0f6fc
Text Secondary: #8b949e
Accent:         #f97316 (747 orange) or per-agent color
Error:          #f85149
Warning:        #d29922
Success:        #3fb950
```

### Layout Principles
- Sticky sidebar navigation (settings categories)
- No page reloads — tab switching is instant (display toggle)
- Save/Reload buttons always visible (floating top-right)
- Activity log with color-coded severity
- Responsive: works on phone (for Telegram web link)

## Speed Perception Tricks

### Response Chain Timing
```
User stops speaking    → 0ms:   Glow shifts to "thinking" IMMEDIATELY
                       → 144ms: Whisper transcription complete
                       → 300ms: First LLM token arrives (streaming)
                       → 500ms: First complete sentence extracted
                       → 800ms: First TTS audio chunk generated
                       → 900ms: First audio playback begins ← THIS IS THE GOAL
                       → 900ms: Glow shifts to "speaking", bubble appears
```
**Perceived latency: <1 second** (even though full response takes 3-5s to complete)

### Animation During Wait
- The transition from "listening" to "thinking" glow happens BEFORE transcription
  (on voice activity end, not on transcription complete)
- This buys 144ms of perceived speed
- The "thinking" animation should be energetic (not slow), suggesting activity

### Audio Overlap
- Start playback on first sentence, not full response
- Second sentence generates while first plays
- No gap between sentences (watermark tracking ensures continuous audio)

## Marketing & Pitch Positioning

### Tagline Options
- "Speak. They listen. They act." 
- "Your voice. Their intelligence. One interface."
- "The AI agents that hear you."

### Key Differentiators (vs. competitors)
1. **Multi-Agent** — Not one generic assistant. Five specialists with unique voices.
2. **Local-First** — STT and TTS run on your machine. Privacy by default.
3. **Sub-Second Response** — Streaming pipeline. First audio in under 1 second.
4. **Remote Access** — Control your laptop from your phone via Telegram.
5. **Beautiful UI** — Animated avatars, glow effects, agent selection grid.
6. **Open Architecture** — Swap LLMs, TTS engines, add agents. Not locked in.

### Competitive Landscape (April 2026)
| Product | Strength | VII Two Edge |
|---------|----------|-------------|
| DecisionsAI | Open source, full desktop control | Multi-agent + better design |
| Siri/Apple Intelligence | Native integration | Agent personalities + speed |
| Google Gemini | Cloud power | Local-first privacy |
| ChatGPT Voice | Natural conversation | Multi-agent dispatch |
| Lindy | Customizable workflows | Voice-first + desktop control |
| ElevenLabs | Voice quality | Full agent system, not just voices |

### Apple Pitch Angle
- "What if Siri had specialists? A strategist. An analyst. A creative director."
- "What if you could switch between AI personalities as easily as switching apps?"
- "What if your AI assistant could see your screen, hear your voice, and control your computer?"
- "We built it. It works. It's beautiful. And it runs locally on Apple Silicon."

### Product Hunt Launch Strategy (Target: April 20-24, 2026)
1. **Demo Video** (60s): Show the full flow — speak to Bob, switch to Pixi, 
   see the glow transitions, remote control from phone
2. **Landing Page**: Dark theme, animated hero showing avatar in action
3. **First Comment**: "Built by The 747 Lab. Open source coming soon."
4. **Makers Story**: "I wanted Siri but with specialists who actually understand context."
