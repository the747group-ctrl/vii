# VII Two — Business Strategy & Market Path

## The Vision

VII is a voice-first AI companion with multiple agent personalities. Users download the app, speak, and it's done. No typing. No setup wizard. Just conversation.

"I use VII for brainstorming." "I use VII as my therapist." "I use VII for everything."

---

## Market Size (2026)

| Segment | Size | Growth |
|---------|------|--------|
| AI companion apps (consumer) | $120M revenue, 220M downloads | 64% YoY |
| Broader AI companion market | $37.7B | 31% CAGR → $435B by 2034 |
| AI mental health | $2.0B | 34% CAGR → $9.1B by 2033 |
| Voice AI total | $22-24B | 25% YoY |
| Voice AI agents | $3.1B | 34.8% CAGR → $47.5B by 2034 |

**Key stat:** Top 10% of companion apps capture 89% of revenue. Must be in that bracket.

---

## Competitive Gap — What Nobody Has Combined

| Feature | ChatGPT | Replika | Character.AI | Siri/Alexa | **VII** |
|---------|---------|---------|-------------|------------|---------|
| Voice-first | Bolt-on | Premium | Limited | Native | **Native** |
| Intelligence | Best | Limited | Roleplay | Weak | **Claude-tier** |
| Personality | None | 1 custom | Many text | None | **5 specialists** |
| Memory | Basic | Good | None | None | **Per-agent** |
| Offline | No | No | No | Partial | **Yes (STT+TTS)** |
| Agent switching | No | No | Yes (text) | No | **Voice + visual** |
| Desktop control | No | No | No | Limited | **Full** |
| Remote access | No | No | No | No | **Telegram** |

**Nobody combines: voice-first + multiple agent personas + real intelligence + memory + offline. That's VII.**

---

## Revenue Model

### Consumer App (Phase 1)

| Tier | Price | Features |
|------|-------|----------|
| **Free** | $0 | 10 voice min/day, 1 agent (Claude), text chat unlimited |
| **Pro** | $9.99/mo | Unlimited voice, all 5 agents, conversation history, custom wake word |
| **Ultra** | $19.99/mo | Priority speed, voice cloning, offline mode, API access |

**Benchmarks:**
- Replika: $8-25/mo, 25% free-to-paid conversion (exceptional)
- Character.AI: $9.99/mo, $32M ARR
- Industry average conversion: 2-5%
- Revenue per download: $1.18 average, top apps $5+

**Target:** 10K users in 3 months, 1K paying ($10K MRR)

### Developer API (Phase 2, 6-18 months)

| Plan | Price | Includes |
|------|-------|---------|
| **Starter** | Free | 100 min/month |
| **Growth** | $0.05/min | Up to 100K min/month |
| **Enterprise** | Custom | Dedicated infra, SLA, custom voices |

### Enterprise White-Label (Phase 3, 12-24 months)

Target verticals:
- **Hospitality** (hotels, airlines): In-room/in-flight voice concierge
- **Automotive** (car infotainment): Multi-agent voice assistant
- **Healthcare** (patient intake, companion for elderly)

**Revenue model:** $50K-500K ACV per enterprise contract

### OEM Device Licensing (Phase 4, 24-36 months)

**Revenue model:** $2-5 per device royalty
**Benchmark:** Cerence averages $4.91/vehicle, $331M annual revenue

---

## The 5-Phase Revenue Escalation

### Phase 1: Consumer App (0-12 months)
- Ship iOS + Android app
- Push-to-talk (Apple won't allow always-listening for 3rd parties)
- Multi-agent personas with distinct voices — THE differentiator
- Freemium + $9.99/mo Pro
- Product Hunt launch April 20-24, 2026
- **Revenue target: $120K ARR**

### Phase 2: Developer Platform (6-18 months)  
- Package voice pipeline as API (STT + agent routing + TTS)
- Per-minute pricing, undercut ElevenLabs/Deepgram
- Edge deployment option for privacy-sensitive customers
- SOC 2 Type I certification ($50K, 3-6 months)
- **Revenue target: $10K MRR from 100 developers**

### Phase 3: Enterprise White-Label (12-24 months)
- Custom voices, branding, domain vocabulary
- ONE vertical first (hospitality = UAE natural fit)
- SOC 2 Type II + GDPR compliance
- Multi-language: English, Arabic, Hindi, Mandarin
- **Revenue target: 3-5 contracts at $50K-500K ACV**

### Phase 4: OEM Licensing (24-36 months)
- Quantized models for ARM NPUs (ONNX/TFLite)
- Wake word detection (always-on, low-power)
- Smart TV apps (Samsung Tizen + LG webOS)
- Start with smaller OEMs, not Apple/Samsung day one
- **Revenue target: 1 OEM deal, 100K devices, $2-5/device**

### Phase 5: Major Enterprise (36+ months)
- Emirates, Samsung, LG-tier deals
- Thales/Panasonic partnership for airline IFE
- ISO 26262 for automotive
- Multi-region data centers
- **Revenue target: $1M+ ACV deals**

---

## Device Integration Requirements

### iOS
- Apple opening 3rd-party voice assistant via Side Button (EU/Japan only, iOS 26.2)
- App Intents framework for Siri integration
- No always-listening for 3rd parties — push-to-talk only
- **Strategy:** Build as App Intents app, position for global Side Button opening

### Android  
- Can be set as default assistant (Android 14+)
- VoiceInteractionService for system-level access
- Partner with OEMs for pre-installation
- **Strategy:** VoiceInteractionService + OEM partnerships

### Smart TVs
- Samsung Tizen + LG webOS both support HTML/JS apps
- Voice framework APIs available
- SoundHound already doing voice commerce on TVs (CES 2026)

### Airlines (Emirates ICE)
- Thales AVANT Up has open platform for developers
- 10+ month certification cycle
- **Phase 5 play** — requires proven scale first

### Cars
- Android Automotive OS offers deepest integration
- CarPlay is Apple-controlled and restrictive
- **Strategy:** Android Automotive first, partner with OEM

---

## Technical Requirements for Licensability

| Capability | Current | Required | Priority |
|-----------|---------|----------|----------|
| End-to-end latency | 3-5s | <1s | CRITICAL |
| Multi-language | English only | 10+ languages | HIGH |
| Offline mode | Desktop only | Mobile + embedded | HIGH |
| Wake word | None (hotkey) | Custom, always-on | HIGH |
| Custom voices | 7 Kokoro presets | Voice cloning | MEDIUM |
| SDK/API | None | iOS, Android, REST, C | MEDIUM |
| Compliance | None | SOC 2, GDPR, ISO 27001 | MEDIUM (blocks enterprise) |
| Noise cancellation | None | In-car/in-flight grade | MEDIUM |
| Voice commerce | None | Payments, transactions | LATER |

---

## Marketing Strategy

### The "I Use VII" Campaign

**Format:** 15-30 second vertical videos (TikTok/Reels/Shorts)
**Style:** Real people, real contexts. Apple "Shot on iPhone" meets diversity

**Testimonial roster:**

| Person | Setting | Line | Use Case |
|--------|---------|------|----------|
| Black woman, warm smile | Living room, cozy | "I use VII for brainstorming" | Creativity |
| Italian mom | Kitchen, cooking | "I use VII for my friend" | Companionship |
| College student | Walking campus | "I use VII for everything" | General |
| Elderly grandfather | Porch, sunset | "VII remembers" | Memory/loneliness |
| Entrepreneur, tired eyes | Desk at 2 AM | "I use VII at 2 AM when no one else is up" | Late-night support |
| Teen with headphones | Bus stop | "I use VII to practice Spanish" | Language learning |
| Therapist's client | Park bench, earbuds | "I use VII between sessions" | Mental health |
| Dad with toddler | Playground | "I use VII to stay organized" | Productivity |
| Nurse after night shift | Car, sunrise | "I use VII to decompress" | Emotional support |
| Blind user | Kitchen | "I use VII because I don't need a screen" | Accessibility |

**Production notes:**
- Natural lighting, no studio
- Phone-shot quality (authentic, not polished)
- Person speaks directly to camera
- Show the VII interface for 3 seconds max
- End card: "VII. Just speak." + download link
- 63% of top-performing videos deliver their message in first 3 seconds

### Growth Channels (Priority Order)

1. **TikTok paid** — $0.30-0.40/install (cheapest paid channel, Replika proved it)
2. **Reddit organic** — #1 social traffic source for Replika. Post in r/singularity, r/ChatGPT, r/AIcompanions
3. **Product Hunt launch** — April 20-24 target. "Built by The 747 Lab. The Jarvis you've been waiting for."
4. **YouTube creator partnerships** — AI review channels, productivity YouTubers
5. **TikTok organic** — "I just talked to VII for an hour and..." reaction content
6. **App Store optimization** — Voice AI keywords, emotional screenshots, demo video

### Key Marketing Principles

1. **Lead with emotion, not technology** — "It remembers" > "Multi-agent RAG pipeline"
2. **Diversity is the strategy** — Every person is a different market segment
3. **Simplicity is the hook** — "Download. Speak. Done." Three words
4. **The 2 AM test** — Would someone use this at 2 AM when they're alone? If yes, it's sticky
5. **Values-driven virality** — Claude topped App Store by refusing surveillance. Position on privacy and ethics

---

## Competitive Moat (What Makes VII Defensible)

1. **Multi-agent architecture** — No one else has 5 specialized voice agents in one app
2. **Local-first privacy** — STT and TTS on-device. Competitors are cloud-dependent
3. **Voice-native** — Built for voice from day one, not text with voice bolted on
4. **Agent memory** — Each agent remembers past conversations
5. **Open architecture** — Swap LLMs, add agents, customize voices
6. **Remote access** — Control your devices from your phone via voice

---

## Funding Path

| Stage | Raise | What It Funds | Milestone |
|-------|-------|---------------|-----------|
| Pre-seed (now) | $0 (bootstrapped) | MVP, Product Hunt launch | 10K users |
| Seed | $500K-1M | iOS/Android app, 2 engineers, marketing | 100K users, $50K MRR |
| Series A | $5-10M | Multi-language, SDK, SOC 2, team of 10 | 1M users, $500K MRR |
| Series B | $20-50M | Enterprise sales, OEM partnerships, global | 10M users, $5M ARR |

**Benchmark valuations:**
- Vapi (voice AI dev platform): $20M raise at Series A
- Cartesia (voice AI models): $64M Series A
- ElevenLabs: $500M Series D at $11B valuation
- Giga (voice agents): $61M Series A

---

## The Pitch (One Paragraph)

VII is the voice AI companion that actually understands you. Five specialized agents — a strategist, an analyst, an operations expert, a creative director, and a content specialist — each with their own voice, memory, and personality. It runs locally on your device for privacy, responds in under a second, and works from your desktop, phone, or any connected device. In a world where Siri is still dumb, Alexa just broke basic commands, and ChatGPT has no personality — VII is the thing people have been building on GitHub for years. We just built it right.

---

*Developed by The 747 Lab*
