# VII — Product Hunt Launch Checklist

## Critical Context

- **Comments > Upvotes.** One quality comment carries the weight of 40-50 upvotes in PH's algorithm.
- **First 4 hours decide everything.** Ranking at hour 4 is roughly your final position.
- **400 engaged supporters > 4,000 cold contacts.** Quality over volume.
- **Video = 2.7x more upvotes.** The demo video is not optional.
- **Featured status is critical.** Apply in advance via PH.

---

## Phase 1: Pre-Launch (2-3 Weeks Before)

### Product Hunt Setup
- [ ] Create PH maker account (if not already)
- [ ] Submit for "upcoming" status — build followers before launch
- [ ] Apply for Featured status via PH team contact
- [ ] Pick launch day: **Wednesday** (historically strongest day; avoid Monday/Friday)
- [ ] Set launch time: **12:01 AM PT** (8:01 AM UAE) — maximizes the full 24-hour window

### Assets to Create
- [ ] Demo video (60 seconds) — see `demo-script.md`
- [ ] Hero image (1270x760) — orb on clean desktop, mid-glow
- [ ] Gallery GIFs (4-5): voice command, vision, agent switch, remote access, hands-free
- [ ] Logo (240x240, transparent background)
- [ ] Listing copy finalized — see `product-hunt-listing.md`
- [ ] Maker's first comment written and ready to paste

### Landing Page / Download
- [ ] Download page live (vii.747lab.com or similar)
- [ ] One-command installer working: `curl -sSL https://vii.747lab.com/install | bash`
- [ ] README with quick start (3 steps max)
- [ ] GitHub repo public (if open-sourcing) — or "open source coming soon" in listing

### Build Your 400
- [ ] List of 50+ personal contacts who will comment (not just upvote)
- [ ] Draft personalized DMs for each — don't send a generic link
- [ ] Identify 10-15 indie maker friends on PH — ask them to leave real comments
- [ ] Post "building in public" updates on X leading up to launch (build anticipation)
- [ ] Engage in 5-10 PH communities/discussions in the weeks before (build presence)

### Content Pipeline
- [ ] Write X/Twitter thread (launch day)
- [ ] Write LinkedIn post (launch day)
- [ ] Write Reddit posts for r/ChatGPT, r/singularity, r/macapps, r/artificial (launch day)
- [ ] Prepare Hacker News "Show HN" post
- [ ] Draft email to any newsletter contacts or communities

### Product Readiness
- [ ] Test full voice flow end-to-end 10 times
- [ ] Test on clean Mac (fresh user, no pre-existing config)
- [ ] Confirm installer works on macOS 14, 15, 26
- [ ] Verify all 5 agents respond correctly
- [ ] Test hands-free mode for 5+ minutes continuous
- [ ] Test remote access via Telegram
- [ ] Test vision (screenshot analysis) on various screen content
- [ ] Fix any crash or error that appears more than once
- [ ] Ensure first-run experience takes under 2 minutes from download to first voice interaction

---

## Phase 2: Launch Day

### Hour 0 (12:01 AM PT / 8:01 AM UAE)

- [ ] Launch the listing on Product Hunt
- [ ] Immediately post the maker's first comment (within 60 seconds)
- [ ] Post on X/Twitter:

**X/Twitter Post:**
```
I just launched VII on Product Hunt.

It's a voice-controlled AI that lives on your Mac desktop. 
You talk to it. It answers. It opens apps. It controls your 
computer. It sees your screen. It remembers conversations.

5 specialist agents. Each with their own voice.
The intelligence of ChatGPT with the hands of Siri.
Running on your machine.

Free. No account needed.

[Product Hunt link]

Built solo at The 747 Lab.
```

- [ ] Post on LinkedIn:

**LinkedIn Post:**
```
Today I launched VII — Voice Intelligence Interface — on Product Hunt.

The problem: AI assistants can talk, but they can't do anything. 
Siri sets timers. ChatGPT writes essays. Neither one can open my 
browser, find a file, or control my computer while my hands are busy.

VII is a floating orb on your Mac desktop. You speak to it. It 
understands you, responds with its own voice, and controls your 
computer. Open apps. Search the web. Analyze your screen. All by voice.

It has five specialist agents — strategy, research, operations, 
creative, content — each with a unique voice and personality.

Speech recognition and text-to-speech run locally on your machine. 
Your voice never leaves your computer.

And you can control your Mac from your phone via Telegram.

Free to download. Built at The 747 Lab.

Would love your feedback: [Product Hunt link]
```

- [ ] Post on Reddit (pick 2-3 subreddits, space them out by 1-2 hours):

**r/macapps post:**
```
Title: I built a voice-controlled AI assistant that actually controls your Mac

I got frustrated with voice assistants that can talk but can't 
do anything on your computer. So I built VII.

It's a floating orb on your desktop. You talk to it, it responds 
with its own voice, and it can open apps, type text, click buttons, 
take screenshots, and analyze what's on your screen.

It has 5 specialist agents with different voices. Speech recognition 
runs locally via Whisper. TTS runs locally via Kokoro. 
Free, no account needed.

Demo video: [link]
Download: [link]
Product Hunt: [link]

Happy to answer any questions. Would love feedback from Mac power users.
```

### Hours 1-4 (THE CRITICAL WINDOW)

- [ ] **Monitor PH page constantly** — respond to every comment within 10 minutes
- [ ] Send personal DMs to your 50+ contacts: "We're live, would love a real comment about X"
- [ ] Stagger your outreach — don't blast everyone at once (PH flags coordinated voting)
  - Hour 1: 10-15 close friends/makers
  - Hour 2: 10-15 more contacts
  - Hour 3: 10-15 community contacts
  - Hour 4: Remaining contacts
- [ ] Engage authentically — answer technical questions, thank people, share behind-the-scenes details
- [ ] If someone leaves a detailed comment, reply with something equally substantive

### Hours 4-12

- [ ] Continue responding to every comment
- [ ] Share milestone updates on X if hitting upvote/comment milestones
- [ ] Post the Hacker News "Show HN" (afternoon PT is good for HN)
- [ ] Share in any Slack/Discord communities you're part of
- [ ] Monitor for bugs — if someone reports an issue, fix it live and reply with the fix

### Hours 12-24

- [ ] Final push — send reminders to anyone who said they'd support but hasn't yet
- [ ] Post a "12 hours in, here's what I've learned" update on X
- [ ] Thank early supporters publicly
- [ ] Keep responding to comments (PH rewards engagement throughout the full 24h)

---

## Phase 3: Post-Launch (Days 2-14)

### Day 2 (The Day After)
- [ ] Post launch results on X/LinkedIn (rank, upvotes, comments, key feedback)
- [ ] Write a "What I learned launching on Product Hunt" thread (this itself gets engagement)
- [ ] Compile all feedback into categories: bugs, feature requests, praise, confusion points
- [ ] Prioritize top 3 quick fixes from user feedback

### Week 1
- [ ] Ship at least one fix or improvement based on PH feedback
- [ ] Announce the fix publicly: "You asked for X, we shipped it"
- [ ] Follow up with everyone who left a comment — DM thanking them
- [ ] Monitor PH for late comments (they trickle in for days)
- [ ] Track metrics: downloads, daily active users, retention

### Week 2
- [ ] Write a retrospective (internal): what worked, what didn't, what to do differently
- [ ] Plan the second launch (4-6 months out) with a major new feature
- [ ] If results were strong, start drafting outreach to tech press / AI newsletters
- [ ] Begin collecting user testimonials for the next launch

---

## Social Media Templates (Ready to Copy-Paste)

### X/Twitter — Teaser (Post 3-5 days before launch)
```
Building something I've wanted for years.

An AI that doesn't just talk — it actually controls your computer.

You speak. It opens apps. Searches the web. Analyzes your screen. 
Remembers your conversations. Five different agents, five different voices.

Launching on Product Hunt [date]. 

[screenshot or GIF of the orb in action]
```

### X/Twitter — "Why I Built This"
```
I wanted my AI to actually DO things on my computer, not just talk.

Siri: "I can't do that on your Mac."
ChatGPT: *writes a great answer but can't act on it*
Me: *builds VII*

It's a floating orb on your desktop. You talk to it. 
It thinks. It acts. It remembers.

Free. Launching on PH [date].
```

### X/Twitter — Technical Thread (For Dev Audience)
```
How I built a sub-second voice AI pipeline on a MacBook:

1/ STT: Whisper.cpp compiled to native ARM64 Rust. ~144ms transcription.

2/ LLM: Claude API with streaming. First token in ~300ms.

3/ TTS: Kokoro-82M running locally. 0.35x real-time factor.

4/ Pipeline: Sentence-level streaming. Start speaking the first 
sentence while generating the second.

5/ Result: You stop talking → first audio response in under 1 second.

6/ Overlay: Native Swift/AppKit. Animated avatars with per-agent glow colors.

7/ Remote: Full Mac control from your phone via Telegram.

The whole thing: [Product Hunt link]
```

### Reddit — r/singularity or r/artificial
```
Title: Voice AI that controls your Mac — not just dictation, actual computer control

I've been working on VII (Voice Intelligence Interface) for the 
past few months. It's different from the usual voice assistants 
because it actually executes actions on your computer.

What it does:
- Floating orb on your desktop — speak to it naturally
- Opens apps, types text, clicks, takes screenshots
- Sees your screen and answers questions about it
- 5 specialist AI agents with different voices/personalities
- Conversation memory (per agent)
- Remote control from your phone via Telegram
- STT and TTS run locally (Whisper + Kokoro) — privacy first

Tech stack: Rust (STT), Python (pipeline), Swift (overlay), 
Claude API (LLM), Kokoro-82M (TTS)

Free, Mac only for now.

Demo: [video link]
Download: [link]

Interested in feedback — especially on what features would make 
this useful for your daily workflow.
```

---

## Anti-Patterns (What NOT to Do)

- **DO NOT** send a mass email blast with just a PH link. Personalize every ask.
- **DO NOT** ask people to "upvote." Ask them to "try it and leave honest feedback."
- **DO NOT** post on more than 2-3 subreddits on the same day (spam flags).
- **DO NOT** use upvote exchange groups or services. PH detects and penalizes this.
- **DO NOT** go silent after the first 4 hours. Engagement must last the full 24h.
- **DO NOT** argue with negative feedback. Thank them, acknowledge, say what you'll fix.
- **DO NOT** launch on a holiday, during a major Apple/Google event, or on a Friday.

---

## Success Metrics

| Metric | Good | Great | Exceptional |
|--------|------|-------|-------------|
| Upvotes (24h) | 200+ | 400+ | 700+ |
| Comments | 50+ | 100+ | 200+ |
| Rank | Top 10 | Top 5 | #1 Product of the Day |
| Downloads (week 1) | 500 | 1,000 | 5,000 |
| Maker comment replies | Every single one | — | — |

---

*Developed by The 747 Lab*
