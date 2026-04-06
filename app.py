#!/usr/bin/env python3
"""
VII — Voice Intelligence Interface
Open http://localhost:7747 → Click Start → Speak → Hear response.

Developed by The 747 Lab
"""

import asyncio
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time

import numpy as np
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 250
PORT = 7747

AGENTS = {
    "vii":    {"voice": "af_heart",   "speed": 1.1,  "color": "#06b6d4", "role": "Your voice AI companion. Warm, insightful, genuinely helpful."},
    "bob":    {"voice": "am_onyx",    "speed": 1.0,  "color": "#3b82f6", "role": "Lead strategist. Deep, authoritative, sees the big picture."},
    "falcon": {"voice": "am_michael", "speed": 0.95, "color": "#22c55e", "role": "Intelligence analyst. Measured, precise, data-driven."},
    "pixi":   {"voice": "af_heart",   "speed": 1.25, "color": "#ec4899", "role": "Creative director. Expressive, enthusiastic, visual thinker."},
    "buzz":   {"voice": "am_puck",    "speed": 1.3,  "color": "#f97316", "role": "Content strategist. Playful, energetic, story-driven."},
}


def load_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    auth = os.path.expanduser("~/.openclaw/agents/main/agent/auth-profiles.json")
    if os.path.exists(auth):
        with open(auth) as f:
            data = json.load(f)
            key = data.get("profiles", {}).get("anthropic:manual", {}).get("token", "")
            if key.startswith("sk-"):
                return key
    return ""


API_KEY = load_api_key()

_whisper = None
_kokoro = None


def get_whisper():
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        model_dir = os.path.join(MODELS_DIR, "models--Systran--faster-whisper-small", "snapshots")
        if os.path.exists(model_dir):
            snaps = [s for s in os.listdir(model_dir) if not s.startswith('.')]
            if snaps:
                _whisper = WhisperModel(os.path.join(model_dir, snaps[0]), device="cpu", compute_type="int8")
                return _whisper
        _whisper = WhisperModel("small", device="cpu", compute_type="int8")
    return _whisper


def get_kokoro():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        _kokoro = Kokoro(
            os.path.join(MODELS_DIR, "kokoro", "kokoro-v1.0.onnx"),
            os.path.join(MODELS_DIR, "kokoro", "voices-v1.0.bin"),
        )
    return _kokoro


app = FastAPI(title="VII")


@app.get("/", response_class=HTMLResponse)
async def index():
    return FRONTEND


@app.post("/api/listen")
async def listen(audio: UploadFile = File(...)):
    """Receive audio from browser, transcribe, respond with text + audio."""
    t_start = time.time()

    # Save uploaded audio (browser sends WebM/Opus)
    audio_bytes = await audio.read()
    webm_path = tempfile.mktemp(suffix=".webm")
    wav_path = tempfile.mktemp(suffix=".wav")

    with open(webm_path, "wb") as f:
        f.write(audio_bytes)

    # Convert WebM → 16kHz WAV with ffmpeg
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", webm_path, "-ar", "16000", "-ac", "1", "-f", "wav", wav_path,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
    os.unlink(webm_path)

    if not os.path.exists(wav_path):
        return JSONResponse({"error": "audio conversion failed"})

    # Transcribe with Whisper
    import soundfile as sf
    audio_data, sr = sf.read(wav_path)
    os.unlink(wav_path)

    if len(audio_data) < 1600:  # less than 0.1s
        return JSONResponse({"transcript": "", "response": ""})

    audio_f32 = audio_data.astype(np.float32)
    model = get_whisper()
    segments, _ = model.transcribe(audio_f32, language="en", beam_size=3)
    transcript = " ".join(s.text.strip() for s in segments).strip()
    t_stt = time.time()

    if not transcript or len(transcript) < 2:
        return JSONResponse({"transcript": "", "response": ""})

    # Filter hallucinations
    lower = transcript.lower().strip()
    hallucinations = ["thank you", "thanks", "bye", "you", "the end",
                      "thank you for watching", "subscribe"]
    if any(lower == h or (len(lower) < 15 and lower.startswith(h)) for h in hallucinations):
        return JSONResponse({"transcript": transcript, "response": "", "filtered": True})

    # Detect agent
    agent = "vii"
    clean_text = transcript
    for name in AGENTS:
        for prefix in [name + ", ", name + " ", "hey " + name + " ", "hey " + name + ", "]:
            if lower.startswith(prefix):
                agent = name
                clean_text = transcript[len(prefix):].strip()
                break
        if agent != "vii":
            break

    # Call Claude
    import httpx
    cfg = AGENTS[agent]
    system = (
        f"You are {agent.upper() if agent != 'vii' else 'VII'}, a voice AI by The 747 Lab. "
        f"{cfg['role']} "
        f"Respond in 2-3 concise spoken sentences. No markdown, no lists, no asterisks. "
        f"Speak naturally as if in conversation."
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": CLAUDE_MODEL, "max_tokens": MAX_TOKENS, "system": system,
                  "messages": [{"role": "user", "content": clean_text}]},
        )
        resp.raise_for_status()
        data = resp.json()
        response_text = data.get("content", [{}])[0].get("text", "")

    t_llm = time.time()

    # Generate TTS
    loop = asyncio.get_event_loop()
    def _tts():
        kokoro = get_kokoro()
        clean = re.sub(r'[`#*]', '', response_text)
        clean = clean.replace('%', ' percent').replace('&', ' and ')
        clean = clean.replace('\u2019', "'").replace('\u2018', "'")
        samples, sr = kokoro.create(clean, voice=cfg["voice"], speed=cfg["speed"], lang="en-us")
        # Convert to WAV bytes
        int16 = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
        return int16.tobytes(), sr

    audio_bytes, tts_sr = await loop.run_in_executor(None, _tts)
    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    t_tts = time.time()

    print(f"  [{agent.upper()}] \"{transcript}\" → {len(response_text)}ch | "
          f"stt:{(t_stt-t_start)*1000:.0f}ms llm:{(t_llm-t_stt)*1000:.0f}ms tts:{(t_tts-t_llm)*1000:.0f}ms "
          f"total:{(t_tts-t_start)*1000:.0f}ms")

    return JSONResponse({
        "transcript": transcript,
        "agent": agent,
        "agentColor": cfg["color"],
        "response": response_text,
        "audio": audio_b64,
        "sampleRate": tts_sr,
        "timing": {
            "stt": round((t_stt - t_start) * 1000),
            "llm": round((t_llm - t_stt) * 1000),
            "tts": round((t_tts - t_llm) * 1000),
            "total": round((t_tts - t_start) * 1000),
        }
    })


# ─── Frontend ─────────────────────────────────────────────

FRONTEND = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>VII</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;overflow:hidden}
body{background:#08080c;color:#d4d4dc;font-family:'Outfit',sans-serif;display:flex;flex-direction:column;align-items:center;justify-content:center}

.logo{position:fixed;top:32px;left:50%;transform:translateX(-50%);font-size:12px;letter-spacing:8px;text-transform:uppercase;color:#333;font-weight:500}

.agent-badge{position:fixed;top:68px;left:50%;transform:translateX(-50%);font-size:10px;letter-spacing:4px;text-transform:uppercase;font-weight:500;opacity:0;transition:all .4s}

.response{position:fixed;top:14%;left:50%;transform:translateX(-50%);max-width:560px;width:88%;text-align:center;font-size:19px;font-weight:300;line-height:1.75;color:#a8a8b8;opacity:0;transition:opacity .4s;overflow-y:auto;max-height:45vh}

.you-said{position:fixed;bottom:200px;left:50%;transform:translateX(-50%);font-size:12px;color:#444;max-width:400px;text-align:center;font-style:italic;opacity:0;transition:opacity .3s}

.orb-wrap{position:fixed;bottom:70px;left:50%;transform:translateX(-50%)}

.orb{width:96px;height:96px;border-radius:50%;border:none;background:radial-gradient(circle at 38% 32%,#141420,#0a0a12);cursor:pointer;position:relative;outline:none;transition:all .3s}
.orb::before{content:'';position:absolute;inset:-12px;border-radius:50%;border:1px solid rgba(255,255,255,.03);transition:all .3s}
.orb::after{content:'';position:absolute;inset:-24px;border-radius:50%;border:1px solid rgba(255,255,255,.015);animation:pulse 4s ease-in-out infinite}

.orb.idle{box-shadow:0 0 40px rgba(80,80,160,.06)}
.orb.idle::before{border-color:rgba(255,255,255,.03)}

.orb.listening{background:radial-gradient(circle at 38% 32%,#1e1018,#120a10);box-shadow:0 0 60px rgba(220,60,60,.1)}
.orb.listening::before{border-color:rgba(220,80,80,.12);transform:scale(1.04)}

.orb.thinking{background:radial-gradient(circle at 38% 32%,#10101e,#0a0a14);box-shadow:0 0 60px rgba(60,60,220,.12)}
.orb.thinking::before{border-color:rgba(80,80,220,.12);animation:think-ring 1.5s ease-in-out infinite}

.orb.speaking{box-shadow:0 0 60px rgba(6,182,212,.1)}
.orb.speaking::before{border-color:rgba(6,182,212,.15)}

.orb-icon{position:absolute;inset:0;display:flex;align-items:center;justify-content:center}
.orb-icon svg{width:26px;height:26px;opacity:.35;transition:all .3s}
.orb.listening .orb-icon svg{opacity:.8;filter:drop-shadow(0 0 8px rgba(220,80,80,.4))}
.orb.thinking .orb-icon svg{opacity:.6;animation:think-pulse 1.5s ease-in-out infinite}
.orb.speaking .orb-icon svg{opacity:.7;filter:drop-shadow(0 0 8px rgba(6,182,212,.4))}

.status{text-align:center;margin-top:16px;font-size:10px;letter-spacing:3px;text-transform:uppercase;color:#333;min-height:14px;transition:color .3s}

.footer{position:fixed;bottom:14px;font-size:9px;color:#222;letter-spacing:2px}

@keyframes pulse{0%,100%{opacity:.3;transform:scale(1)}50%{opacity:.5;transform:scale(1.01)}}
@keyframes think-ring{0%,100%{transform:scale(1);opacity:.8}50%{transform:scale(1.06);opacity:1}}
@keyframes think-pulse{0%,100%{opacity:.4}50%{opacity:.8}}
</style>
</head>
<body>

<div class="logo">VII</div>
<div class="agent-badge" id="badge"></div>
<div class="response" id="response"></div>
<div class="you-said" id="youSaid"></div>

<div class="orb-wrap">
  <button class="orb idle" id="orb">
    <div class="orb-icon">
      <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
        <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
      </svg>
    </div>
  </button>
  <div class="status" id="status">Tap to speak</div>
</div>

<div class="footer">THE 747 LAB</div>

<script>
const orb = document.getElementById('orb');
const statusEl = document.getElementById('status');
const responseEl = document.getElementById('response');
const badgeEl = document.getElementById('badge');
const youSaid = document.getElementById('youSaid');

let state = 'idle'; // idle, listening, thinking, speaking
let mediaRecorder = null;
let audioChunks = [];
let audioCtx = null;

function setState(s, opts) {
  state = s;
  orb.className = 'orb ' + s;

  if (s === 'idle') {
    statusEl.textContent = 'Tap to speak';
    statusEl.style.color = '#333';
  } else if (s === 'listening') {
    statusEl.textContent = 'Listening...';
    statusEl.style.color = '#664444';
    responseEl.style.opacity = '0';
    youSaid.style.opacity = '0';
  } else if (s === 'thinking') {
    statusEl.textContent = 'Thinking...';
    statusEl.style.color = '#444466';
  } else if (s === 'speaking') {
    statusEl.textContent = '';
    statusEl.style.color = '#336';
    if (opts && opts.agent) {
      badgeEl.textContent = opts.agent.toUpperCase();
      badgeEl.style.color = opts.color || '#06b6d4';
      badgeEl.style.opacity = '1';
    }
    if (opts && opts.response) {
      responseEl.textContent = opts.response;
      responseEl.style.opacity = '1';
    }
    if (opts && opts.transcript) {
      youSaid.textContent = '"' + opts.transcript + '"';
      youSaid.style.opacity = '1';
    }
  }
}

async function startListening() {
  if (state !== 'idle') return;
  setState('listening');
  audioChunks = [];

  try {
    const stream = await navigator.mediaDevices.getUserMedia({audio: true});
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
    mediaRecorder.start();
  } catch(e) {
    statusEl.textContent = 'Mic access denied';
    setState('idle');
  }
}

async function stopListening() {
  if (state !== 'listening' || !mediaRecorder) return;
  setState('thinking');

  mediaRecorder.stop();
  mediaRecorder.stream.getTracks().forEach(t => t.stop());

  await new Promise(resolve => { mediaRecorder.onstop = resolve; });

  const blob = new Blob(audioChunks, {type: mediaRecorder.mimeType || 'audio/webm'});

  if (blob.size < 1000) {
    setState('idle');
    return;
  }

  // Upload to server
  const form = new FormData();
  form.append('audio', blob, 'recording.webm');

  try {
    const resp = await fetch('/api/listen', {method: 'POST', body: form});
    const data = await resp.json();

    if (data.error) {
      statusEl.textContent = data.error;
      setTimeout(() => setState('idle'), 2000);
      return;
    }

    if (!data.response || data.filtered) {
      if (data.transcript) {
        youSaid.textContent = '"' + data.transcript + '"';
        youSaid.style.opacity = '1';
        statusEl.textContent = 'Try again';
      }
      setTimeout(() => setState('idle'), 1500);
      return;
    }

    // Play audio response
    setState('speaking', {
      agent: data.agent,
      color: data.agentColor,
      response: data.response,
      transcript: data.transcript,
    });

    if (data.audio) {
      await playAudio(data.audio, data.sampleRate || 24000);
    }

    // Show timing
    if (data.timing) {
      statusEl.textContent = data.timing.total + 'ms';
      statusEl.style.color = '#2a4a2a';
    }

    setTimeout(() => {
      setState('idle');
      badgeEl.style.opacity = '0';
    }, 3000);

  } catch(e) {
    statusEl.textContent = 'Connection error';
    setTimeout(() => setState('idle'), 2000);
  }
}

async function playAudio(b64, sampleRate) {
  if (!audioCtx) audioCtx = new AudioContext({sampleRate: sampleRate});

  // Decode base64 to int16 array
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  const int16 = new Int16Array(bytes.buffer);

  // Convert to float32
  const float32 = new Float32Array(int16.length);
  for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768.0;

  // Create audio buffer and play
  const buf = audioCtx.createBuffer(1, float32.length, sampleRate);
  buf.copyToChannel(float32, 0);

  return new Promise(resolve => {
    const source = audioCtx.createBufferSource();
    source.buffer = buf;
    source.connect(audioCtx.destination);
    source.onended = resolve;
    source.start();
  });
}

// Tap to toggle recording
orb.addEventListener('click', () => {
  if (state === 'idle') {
    startListening();
  } else if (state === 'listening') {
    stopListening();
  }
});

// Space bar
document.addEventListener('keydown', e => {
  if (e.code === 'Space' && !e.repeat) {
    e.preventDefault();
    if (state === 'idle') startListening();
    else if (state === 'listening') stopListening();
  }
});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: No Anthropic API key.")
        sys.exit(1)

    print()
    print("  VII — Just Speak.")
    print("  http://localhost:7747")
    print("  The 747 Lab")
    print()
    print("  Loading...")
    t = time.time(); get_whisper(); print(f"  Whisper ready ({time.time()-t:.1f}s)")
    t = time.time(); get_kokoro(); print(f"  Kokoro ready ({time.time()-t:.1f}s)")
    print(f"  Open http://localhost:{PORT}\n")

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
