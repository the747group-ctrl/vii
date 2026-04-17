# VII — Product Hunt Listing

## Tagline (60 chars max)

**Talk to your Mac. It listens, thinks, and acts.**
(50 chars)

Alternates:
- "Your voice controls your computer. For real this time." (55 chars)
- "The AI assistant that actually does things on your Mac." (55 chars)

---

## Short Description (260 chars max)

VII is a voice-controlled AI desktop assistant. Speak to a floating orb on your screen — it answers questions, opens apps, controls your Mac, remembers conversations, and sees your screen. Five specialist agents with unique voices. Runs locally. Free.

(252 chars)

---

## Topics / Categories

Select these on Product Hunt:
1. Artificial Intelligence
2. Productivity
3. Developer Tools
4. Mac
5. Voice Assistant

---

## Pricing

**Free**

---

## Gallery Assets (Prepare These)

1. **Hero image** — The orb on a clean desktop, mid-glow (blue)
2. **GIF 1** — Speaking to the orb, it responds with a chat bubble
3. **GIF 2** — Saying "open Safari and search for flights to Tokyo" — watch it happen
4. **GIF 3** — Agent switching: "Hey Pixi" — orb color shifts from blue to pink
5. **GIF 4** — Phone screenshot: controlling Mac remotely via Telegram
6. **Demo video thumbnail** — Split: person speaking on left, Mac reacting on right

---

## Maker's First Comment (Post This Immediately at Launch)

---

Hey Product Hunt. I'm the maker of VII.

**The short version:** I got tired of AI assistants that can talk but can't do anything. Siri can set a timer. ChatGPT can write an essay. Neither one can open my browser, find a file, or control my computer while I'm cooking dinner with my hands covered in flour.

So I built the thing I wanted.

**What VII actually does:**

You see a small floating orb on your screen. You speak to it. It transcribes your voice locally using Whisper (nothing leaves your machine for STT). It thinks using Claude. Then it speaks back to you with its own voice — and if you asked it to do something, it does it. Opens apps. Types text. Clicks buttons. Takes screenshots and analyzes what's on your screen.

**The part that makes it different:**

VII has five specialist agents, each with their own voice and personality:
- **Bob** — Strategy and decision-making. Deep voice, thinks before he speaks.
- **Falcon** — Research and analysis. Methodical, gives you sources and confidence scores.
- **Ace** — Operations. British accent, efficient, loves checklists.
- **Pixi** — Creative work. Expressive, visual-first, great for brainstorming.
- **Buzz** — Content and messaging. Energetic, story-driven.

You switch between them by voice ("Hey Falcon, look into this") or by tapping the orb to get a selection grid. Each one remembers your past conversations.

**The tech, briefly:**
- STT: Whisper.cpp compiled to native ARM64 Rust. Transcription in ~144ms.
- TTS: Kokoro-82M running locally. No cloud dependency for voice output.
- LLM: Claude API (streaming). First audio response starts in under a second.
- Overlay: Native Swift/AppKit. Animated avatars with glow effects that shift per agent.
- Remote: Control your Mac from your phone via Telegram. See your screen, click, type — from bed, from the couch, from another country.

**Why it's free:**

Because right now it's a desktop app for Mac power users and developers. I want people to use it, break it, and tell me what's missing. A Pro tier is coming (unlimited voice minutes, voice cloning, more agents), but the core experience will always be free.

**What I'd love from you:**

Try it. Talk to it for 5 minutes. Then tell me what felt magical and what felt broken. That's more valuable than any upvote.

The goal is simple: make your computer as easy to control as talking to another person. We're not there yet. But VII is the closest I've gotten.

Built solo at The 747 Lab. Happy to answer anything.

---

## Full Product Description (For the "About" Section)

### VII — Voice Intelligence Interface

**The intelligence of ChatGPT with the hands of Siri, running on your machine.**

VII is a voice-controlled AI assistant that lives as a floating orb on your Mac desktop. You speak to it. It understands you, responds with its own voice, and controls your computer — opening apps, managing files, searching the web, analyzing your screen, and executing multi-step tasks. All by voice.

#### Not just one assistant. Five.

VII gives you a crew of specialist agents, each with a unique voice and personality:

| Agent | Role | Voice |
|-------|------|-------|
| Bob | Strategy & decisions | Deep, authoritative |
| Falcon | Research & analysis | Measured, professional |
| Ace | Operations & systems | British, efficient |
| Pixi | Creative & design | Expressive, warm |
| Buzz | Content & messaging | Energetic, playful |

Switch agents by voice ("Hey Falcon") or tap the orb to select. Each agent remembers your conversations and builds context over time.

#### Privacy by default.

Speech recognition (Whisper.cpp) and text-to-speech (Kokoro-82M) both run locally on your Mac. Your voice never leaves your machine for processing. The only cloud call is to the LLM for intelligence — and you choose which one.

#### Control your Mac from your phone.

VII includes Telegram-based remote access. See your screen, click, type, and give voice commands to your Mac from your phone — anywhere in the world.

#### Key Features

- Floating orb interface with animated avatars and color-coded glow effects
- Hands-free mode — continuous listening, no button press needed
- Computer control — open apps, type text, click, screenshot, keyboard shortcuts
- Vision — VII can see your screen and answer questions about what's on it
- Conversation memory — per-agent, persistent across sessions
- Customizable skins — swap the orb's look and feel
- Sub-second perceived response time via streaming pipeline
- Native ARM64 performance on Apple Silicon

#### Built with

Rust (STT), Python (pipeline), Swift (overlay), Claude API (intelligence), Kokoro-82M (TTS)

#### Free. No account required.

Download, install, start talking.

---

*Developed by The 747 Lab*
