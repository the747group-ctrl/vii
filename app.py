#!/usr/bin/env python3
"""
VII — Voice Intelligence Interface
Web App: Open in browser, speak, hear response.

Run:  ./tts-venv/bin/python3 app.py
Open: http://localhost:7747

Developed by The 747 Lab
"""

import asyncio
import base64
import json
import os
import re
import sys
import tempfile
import threading
import time
import queue

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

# ─── Config ───

CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 250
PORT = 7747

AGENTS = {
    "vii": {"voice": "af_heart", "speed": 1.1, "role": "Your voice AI. Warm, insightful, real."},
    "bob": {"voice": "am_onyx", "speed": 1.0, "role": "Lead strategist. Deep, authoritative."},
    "falcon": {"voice": "am_michael", "speed": 0.95, "role": "Intelligence analyst. Measured, precise."},
    "pixi": {"voice": "af_heart", "speed": 1.25, "role": "Creative director. Expressive, enthusiastic."},
}

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")


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

# ─── Models (load once) ───

_whisper = None
_kokoro = None


def get_whisper():
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        model_dir = os.path.join(MODELS_DIR, "models--Systran--faster-whisper-small", "snapshots")
        if os.path.exists(model_dir):
            snaps = os.listdir(model_dir)
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


# ─── FastAPI ───

app = FastAPI(title="VII")


@app.get("/", response_class=HTMLResponse)
async def index():
    return FRONTEND_HTML


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()

            if data.get("type") == "audio":
                # Received audio from browser mic
                audio_b64 = data["audio"]
                audio_bytes = base64.b64decode(audio_b64)
                sample_rate = data.get("sampleRate", 16000)

                # Convert to float32
                audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
                audio_f32 = audio_int16.astype(np.float32) / 32768.0

                # Transcribe
                await ws.send_json({"type": "status", "text": "Listening..."})
                model = get_whisper()
                segments, _ = model.transcribe(audio_f32, language="en", beam_size=3)
                text = " ".join(s.text.strip() for s in segments).strip()

                if not text or len(text) < 2:
                    await ws.send_json({"type": "status", "text": ""})
                    continue

                # Filter hallucinations
                lower = text.lower().strip()
                if lower in ("thank you", "thanks", "bye", "you", "the end", ""):
                    await ws.send_json({"type": "status", "text": ""})
                    continue

                await ws.send_json({"type": "transcript", "text": text})

                # Detect agent
                agent = "vii"
                clean_text = text
                for name in AGENTS:
                    for prefix in [name + ", ", name + " ", "hey " + name]:
                        if lower.startswith(prefix):
                            agent = name
                            clean_text = text[len(prefix):].strip()
                            break

                # Stream response + generate TTS
                await stream_response(ws, agent, clean_text)

            elif data.get("type") == "text":
                text = data.get("text", "")
                agent = data.get("agent", "vii")
                await stream_response(ws, agent, text)

    except WebSocketDisconnect:
        pass


async def stream_response(ws: WebSocket, agent: str, text: str):
    """Stream Claude response and send TTS audio chunks."""
    import httpx

    cfg = AGENTS.get(agent, AGENTS["vii"])

    system = (
        f"You are VII, a voice AI by The 747 Lab. "
        f"Personality: {cfg['role']} "
        f"Respond in 2-3 concise spoken sentences. "
        f"No markdown. No lists. Speak naturally. "
        f"Be warm, direct, and genuinely helpful."
    )

    headers = {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": CLAUDE_MODEL, "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": text}],
        "stream": True,
    }

    await ws.send_json({"type": "thinking", "agent": agent})

    full_response = ""
    buffer = ""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", "https://api.anthropic.com/v1/messages",
                                      headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    d = line[6:]
                    if d == "[DONE]":
                        break
                    try:
                        event = json.loads(d)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "content_block_delta":
                        chunk = event.get("delta", {}).get("text", "")
                        if chunk:
                            full_response += chunk
                            buffer += chunk
                            await ws.send_json({"type": "text_chunk", "text": chunk})

                            # Check for complete sentence
                            for i, ch in enumerate(buffer):
                                if ch in '.!?' and i + 2 < len(buffer) and buffer[i+1] == ' ' and buffer[i+2].isupper():
                                    sentence = buffer[:i+1].strip()
                                    buffer = buffer[i+1:].strip()
                                    if sentence and len(sentence) > 5:
                                        audio_b64 = await generate_tts_b64(sentence, cfg["voice"], cfg["speed"])
                                        if audio_b64:
                                            await ws.send_json({
                                                "type": "audio",
                                                "audio": audio_b64,
                                                "sampleRate": 24000,
                                            })
                                    break

    except Exception as e:
        await ws.send_json({"type": "error", "text": str(e)})
        return

    # Flush remaining as final audio
    remaining = (buffer + "").strip() if buffer else full_response.strip()
    if remaining and len(remaining) > 3:
        # Clean
        remaining = re.sub(r'\*\*?', '', remaining)
        audio_b64 = await generate_tts_b64(remaining, cfg["voice"], cfg["speed"])
        if audio_b64:
            await ws.send_json({"type": "audio", "audio": audio_b64, "sampleRate": 24000})

    await ws.send_json({"type": "done"})


async def generate_tts_b64(text: str, voice: str, speed: float) -> str:
    """Generate TTS and return base64 encoded int16 PCM."""
    loop = asyncio.get_event_loop()

    def _gen():
        kokoro = get_kokoro()
        clean = re.sub(r'[`#*]', '', text)
        clean = clean.replace('%', ' percent').replace('&', ' and ')
        clean = clean.replace('\u2019', "'").replace('\u2018', "'")
        samples, sr = kokoro.create(clean, voice=voice, speed=speed, lang="en-us")
        int16 = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
        return base64.b64encode(int16.tobytes()).decode("ascii")

    return await loop.run_in_executor(None, _gen)


# ─── Frontend ─────────────────────────────────────────────

FRONTEND_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>VII — Just Speak</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;overflow:hidden}
body{
  background:#0a0a0f;color:#e8e8ed;
  font-family:'Outfit',sans-serif;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
}

.brand{position:fixed;top:24px;left:50%;transform:translateX(-50%);
  font-size:11px;letter-spacing:6px;text-transform:uppercase;color:#444;font-weight:500}

.response-area{
  position:fixed;top:15%;left:50%;transform:translateX(-50%);
  max-width:600px;width:90%;text-align:center;
  font-size:18px;font-weight:300;line-height:1.7;color:#b8b8c8;
  min-height:60px;transition:opacity .3s;
}
.response-area .agent-name{
  font-size:11px;letter-spacing:4px;text-transform:uppercase;
  color:#666;margin-bottom:12px;font-weight:500;
}

.transcript{
  position:fixed;bottom:180px;left:50%;transform:translateX(-50%);
  font-size:13px;color:#555;font-weight:400;max-width:500px;text-align:center;
}

.mic-area{position:fixed;bottom:60px;left:50%;transform:translateX(-50%);text-align:center}

.mic-btn{
  width:88px;height:88px;border-radius:50%;border:none;
  background:radial-gradient(circle at 40% 35%, #1a1a2e, #0d0d15);
  box-shadow:0 0 0 1px rgba(255,255,255,.06), 0 0 40px rgba(100,100,255,.05);
  cursor:pointer;position:relative;
  transition:all .2s;outline:none;
}
.mic-btn::after{
  content:'';position:absolute;inset:-8px;border-radius:50%;
  border:1px solid rgba(255,255,255,.04);
  animation:breathe 4s ease-in-out infinite;
}
.mic-btn.recording{
  background:radial-gradient(circle at 40% 35%, #2a1525, #150d15);
  box-shadow:0 0 0 1px rgba(255,100,100,.15), 0 0 60px rgba(255,50,50,.1);
}
.mic-btn.recording::after{border-color:rgba(255,100,100,.15)}
.mic-btn.thinking{
  background:radial-gradient(circle at 40% 35%, #15152a, #0d0d18);
  box-shadow:0 0 0 1px rgba(100,100,255,.15), 0 0 60px rgba(100,100,255,.1);
}

.mic-icon{width:24px;height:24px;opacity:.5}
.mic-btn.recording .mic-icon{opacity:.9;filter:drop-shadow(0 0 8px rgba(255,100,100,.5))}

.status{font-size:11px;color:#444;margin-top:14px;letter-spacing:2px;text-transform:uppercase;min-height:16px}

@keyframes breathe{0%,100%{opacity:.3;transform:scale(1)}50%{opacity:.6;transform:scale(1.02)}}

.hint{position:fixed;bottom:16px;font-size:10px;color:#333;letter-spacing:1px}
</style>
</head>
<body>

<div class="brand">VII</div>

<div class="response-area" id="responseArea">
  <div class="agent-name" id="agentName"></div>
  <div id="responseText"></div>
</div>

<div class="transcript" id="transcript"></div>

<div class="mic-area">
  <button class="mic-btn" id="micBtn">
    <svg class="mic-icon" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
      <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
    </svg>
  </button>
  <div class="status" id="status">Hold to speak</div>
</div>

<div class="hint">Developed by The 747 Lab</div>

<script>
const ws = new WebSocket('ws://' + location.host + '/ws');
const micBtn = document.getElementById('micBtn');
const status = document.getElementById('status');
const responseArea = document.getElementById('responseArea');
const responseText = document.getElementById('responseText');
const agentName = document.getElementById('agentName');
const transcript = document.getElementById('transcript');

let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let audioContext = null;

// Audio playback queue
const audioQueue = [];
let isPlaying = false;

function playNextAudio() {
  if (audioQueue.length === 0) { isPlaying = false; return; }
  isPlaying = true;
  const {audio, sampleRate} = audioQueue.shift();

  if (!audioContext) audioContext = new AudioContext({sampleRate: sampleRate});

  const int16 = new Int16Array(audio.buffer);
  const float32 = new Float32Array(int16.length);
  for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768.0;

  const buf = audioContext.createBuffer(1, float32.length, sampleRate);
  buf.copyToChannel(float32, 0);
  const source = audioContext.createBufferSource();
  source.buffer = buf;
  source.connect(audioContext.destination);
  source.onended = playNextAudio;
  source.start();
}

ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);

  if (msg.type === 'transcript') {
    transcript.textContent = '"' + msg.text + '"';
  }
  else if (msg.type === 'thinking') {
    micBtn.className = 'mic-btn thinking';
    status.textContent = 'Thinking...';
    agentName.textContent = msg.agent ? msg.agent.toUpperCase() : 'VII';
    responseText.textContent = '';
  }
  else if (msg.type === 'text_chunk') {
    responseText.textContent += msg.text;
  }
  else if (msg.type === 'audio') {
    const raw = atob(msg.audio);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    audioQueue.push({audio: bytes, sampleRate: msg.sampleRate});
    if (!isPlaying) playNextAudio();
    micBtn.className = 'mic-btn';
    status.textContent = 'Speaking...';
  }
  else if (msg.type === 'done') {
    if (!isPlaying) {
      status.textContent = 'Hold to speak';
      micBtn.className = 'mic-btn';
    }
  }
  else if (msg.type === 'status') {
    if (msg.text) status.textContent = msg.text;
  }
};

// Hold to record
async function startRecording() {
  if (isRecording) return;
  isRecording = true;
  audioChunks = [];
  responseText.textContent = '';
  agentName.textContent = '';
  transcript.textContent = '';
  micBtn.className = 'mic-btn recording';
  status.textContent = 'Listening...';

  const stream = await navigator.mediaDevices.getUserMedia({audio: {sampleRate: 16000, channelCount: 1}});
  mediaRecorder = new MediaRecorder(stream, {mimeType: 'audio/webm'});
  mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
  mediaRecorder.start();
}

async function stopRecording() {
  if (!isRecording || !mediaRecorder) return;
  isRecording = false;
  micBtn.className = 'mic-btn thinking';
  status.textContent = 'Processing...';

  mediaRecorder.stop();
  mediaRecorder.stream.getTracks().forEach(t => t.stop());

  mediaRecorder.onstop = async () => {
    const blob = new Blob(audioChunks, {type: 'audio/webm'});
    const arrayBuf = await blob.arrayBuffer();

    // Decode to PCM using AudioContext
    const ctx = new AudioContext({sampleRate: 16000});
    const decoded = await ctx.decodeAudioData(arrayBuf);
    const pcm = decoded.getChannelData(0);

    // Convert to int16
    const int16 = new Int16Array(pcm.length);
    for (let i = 0; i < pcm.length; i++) {
      int16[i] = Math.max(-32768, Math.min(32767, Math.round(pcm[i] * 32768)));
    }

    // Send as base64
    const b64 = btoa(String.fromCharCode(...new Uint8Array(int16.buffer)));
    ws.send(JSON.stringify({type: 'audio', audio: b64, sampleRate: 16000}));
  };
}

// Mouse/touch events
micBtn.addEventListener('mousedown', startRecording);
micBtn.addEventListener('mouseup', stopRecording);
micBtn.addEventListener('mouseleave', () => { if (isRecording) stopRecording(); });
micBtn.addEventListener('touchstart', (e) => { e.preventDefault(); startRecording(); });
micBtn.addEventListener('touchend', (e) => { e.preventDefault(); stopRecording(); });

// Keyboard: hold space
document.addEventListener('keydown', (e) => { if (e.code === 'Space' && !e.repeat) { e.preventDefault(); startRecording(); }});
document.addEventListener('keyup', (e) => { if (e.code === 'Space') { e.preventDefault(); stopRecording(); }});
</script>
</body>
</html>
"""


# ��── Run ──────────────────────────────────────────────────

if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: No Anthropic API key found.")
        sys.exit(1)

    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║     VII — Just Speak.                ║")
    print("  ║     http://localhost:7747             ║")
    print("  ║     Developed by The 747 Lab         ║")
    print("  ╚══════════════════════════════════════╝")
    print()
    print("  Loading models...")

    # Pre-load models
    t = time.time()
    get_whisper()
    print(f"  Whisper ready ({time.time()-t:.1f}s)")
    t = time.time()
    get_kokoro()
    print(f"  Kokoro ready ({time.time()-t:.1f}s)")
    print(f"\n  Open http://localhost:{PORT} in your browser.\n")

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
