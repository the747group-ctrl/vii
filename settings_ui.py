"""
VII Settings — Web-based preferences panel.
Opens in browser when you right-click orb → Preferences.
Configures: LLM provider, TTS voice, audio devices, API keys, skin.

Run standalone: ./tts-venv/bin/python3 settings_ui.py
Or integrated: desktop.py opens it on right-click → Preferences

Developed by The 747 Lab
"""

import json
import os
import subprocess

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(PROJECT_ROOT, "config", "vii-settings.json")
SKINS_FILE = os.path.join(PROJECT_ROOT, "config", "skins.json")

DEFAULT_SETTINGS = {
    "llm_provider": "anthropic",
    "llm_model": "claude-sonnet-4-20250514",
    "tts_provider": "kokoro",
    "tts_voice": "am_onyx",
    "tts_speed": 1.0,
    "stt_provider": "whisper",
    "stt_model": "small",
    "input_device": "default",
    "output_device": "default",
    "mic_gain": 30.0,
    "hands_free": False,
    "vad_sensitivity": 50,
    "startup_listening": False,
    "skin": "orb",
    "api_keys": {
        "anthropic": "",
        "openai": "",
        "elevenlabs": "",
        "openrouter": "",
        "groq": "",
    },
    "ollama_url": "http://127.0.0.1:11434",
}


def load_settings():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            saved = json.load(f)
            merged = {**DEFAULT_SETTINGS, **saved}
            merged["api_keys"] = {**DEFAULT_SETTINGS["api_keys"], **saved.get("api_keys", {})}
            return merged
    return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(settings, f, indent=2)


app = FastAPI(title="VII Settings")


@app.get("/", response_class=HTMLResponse)
async def settings_page():
    return SETTINGS_HTML


@app.get("/api/settings")
async def get_settings():
    return JSONResponse(load_settings())


@app.post("/api/settings")
async def update_settings(data: dict):
    current = load_settings()
    for key, val in data.items():
        if key == "api_keys" and isinstance(val, dict):
            current["api_keys"].update(val)
        else:
            current[key] = val
    save_settings(current)
    return JSONResponse({"ok": True})


@app.get("/api/audio-devices")
async def audio_devices():
    try:
        import sounddevice as sd
        devices = []
        for i, d in enumerate(sd.query_devices()):
            devices.append({
                "id": i,
                "name": d["name"],
                "inputs": d["max_input_channels"],
                "outputs": d["max_output_channels"],
                "default_input": i == sd.default.device[0],
                "default_output": i == sd.default.device[1],
            })
        return JSONResponse({"devices": devices})
    except Exception as e:
        return JSONResponse({"error": str(e)})


@app.get("/api/ollama-models")
async def ollama_models():
    settings = load_settings()
    try:
        import httpx
        resp = httpx.get(f"{settings['ollama_url']}/api/tags", timeout=5)
        models = [m["name"] for m in resp.json().get("models", [])]
        return JSONResponse({"models": models, "ok": True, "status": "connected"})
    except Exception:
        return JSONResponse({"models": [], "ok": False,
                             "status": "not running",
                             "help": "Install: brew install ollama && ollama serve && ollama pull llama3.2"})


@app.get("/api/conversations")
async def conversations():
    from core.db import get_recent_conversations, get_messages
    convos = get_recent_conversations(limit=20)
    result = []
    for c in convos:
        msgs = get_messages(c["id"], limit=50)
        result.append({
            "id": c["id"],
            "created": c["created_at"],
            "title": c["title"],
            "messages": msgs,
        })
    return JSONResponse({"conversations": result})


@app.get("/api/tts-voices")
async def tts_voices():
    voices = {
        "kokoro": [
            {"id": "am_onyx", "name": "Onyx (deep male)"},
            {"id": "am_michael", "name": "Michael (measured male)"},
            {"id": "am_puck", "name": "Puck (energetic male)"},
            {"id": "af_heart", "name": "Heart (expressive female)"},
            {"id": "bf_emma", "name": "Emma (British female)"},
            {"id": "af_nicole", "name": "Nicole (warm female)"},
        ],
    }
    return JSONResponse(voices)


SETTINGS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VII Settings</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a12;color:#c8c8d4;font-family:-apple-system,system-ui,sans-serif;padding:20px;max-width:680px;margin:0 auto}
h1{font-size:18px;letter-spacing:4px;color:#06b6d4;font-weight:600;margin-bottom:4px}
.sub{font-size:11px;color:#444;margin-bottom:24px}
.section{background:#12121e;border:1px solid #1e1e30;border-radius:10px;padding:16px 20px;margin-bottom:16px}
.section h2{font-size:13px;letter-spacing:2px;color:#888;text-transform:uppercase;margin-bottom:12px;font-weight:500}
.field{margin-bottom:14px}
.field label{display:block;font-size:12px;color:#777;margin-bottom:4px;letter-spacing:0.5px}
.field select,.field input[type=text],.field input[type=password],.field input[type=number]{
  width:100%;background:#0a0a14;border:1px solid #252538;border-radius:6px;
  padding:9px 12px;color:#ccc;font-size:13px;outline:none}
.field select:focus,.field input:focus{border-color:#06b6d4}
.field input[type=range]{width:100%;accent-color:#06b6d4}
.range-val{font-size:11px;color:#555;float:right}
.row{display:flex;gap:12px}
.row .field{flex:1}
.toggle{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.toggle input[type=checkbox]{accent-color:#06b6d4;width:16px;height:16px}
.toggle label{font-size:13px;color:#aaa}
.btn{background:#06b6d4;color:#000;border:none;border-radius:6px;padding:10px 20px;
  font-weight:600;font-size:13px;cursor:pointer;letter-spacing:1px}
.btn:hover{background:#0ea5e9}
.btn:active{opacity:.7}
.btn-outline{background:transparent;border:1px solid #252538;color:#888}
.btn-outline:hover{border-color:#06b6d4;color:#06b6d4}
.save-bar{position:fixed;bottom:0;left:0;right:0;background:#12121e;border-top:1px solid #1e1e30;
  padding:12px 20px;display:flex;justify-content:flex-end;gap:10px}
.status{font-size:11px;color:#3fb950;margin-right:auto;align-self:center}
.key-row{display:flex;gap:8px;align-items:center}
.key-row input{flex:1}
.key-row .btn{padding:8px 12px;font-size:11px}
.footer{text-align:center;font-size:9px;color:#222;margin:40px 0 60px;letter-spacing:2px}
</style>
</head>
<body>
<h1>VII SETTINGS</h1>
<p class="sub">The 747 Lab</p>

<div class="section">
  <h2>Language Model</h2>
  <div class="row">
    <div class="field">
      <label>Provider</label>
      <select id="llm_provider">
        <option value="anthropic">Anthropic (Claude)</option>
        <option value="ollama">Ollama (Local)</option>
        <option value="openai">OpenAI</option>
        <option value="openrouter">OpenRouter</option>
        <option value="groq">Groq</option>
      </select>
    </div>
    <div class="field">
      <label>Model</label>
      <select id="llm_model">
        <option value="claude-sonnet-4-20250514">Claude Sonnet 4</option>
        <option value="claude-haiku-4-5-20251001">Claude Haiku 4.5</option>
      </select>
    </div>
  </div>
  <div class="field" id="ollama_section" style="display:none">
    <label>Ollama URL</label>
    <input type="text" id="ollama_url" value="http://127.0.0.1:11434">
    <button class="btn btn-outline" style="margin-top:6px" onclick="checkOllama()">Check Connection</button>
  </div>
</div>

<div class="section">
  <h2>Voice</h2>
  <div class="row">
    <div class="field">
      <label>TTS Engine</label>
      <select id="tts_provider">
        <option value="kokoro">Kokoro (Local)</option>
        <option value="elevenlabs">ElevenLabs (Cloud)</option>
        <option value="openai">OpenAI TTS (Cloud)</option>
      </select>
    </div>
    <div class="field">
      <label>Voice</label>
      <select id="tts_voice"></select>
    </div>
  </div>
  <div class="field">
    <label>Speed <span class="range-val" id="speed_val">1.0x</span></label>
    <input type="range" id="tts_speed" min="0.5" max="2.0" step="0.05" value="1.0">
  </div>
</div>

<div class="section">
  <h2>Audio</h2>
  <div class="row">
    <div class="field">
      <label>Input Device</label>
      <select id="input_device"></select>
    </div>
    <div class="field">
      <label>Output Device</label>
      <select id="output_device"></select>
    </div>
  </div>
  <div class="field">
    <label>Mic Gain <span class="range-val" id="gain_val">30x</span></label>
    <input type="range" id="mic_gain" min="1" max="50" step="1" value="30">
  </div>
  <div class="toggle">
    <input type="checkbox" id="hands_free">
    <label for="hands_free">Hands-free mode (always listening)</label>
  </div>
  <div class="field">
    <label>VAD Sensitivity <span class="range-val" id="vad_val">50%</span></label>
    <input type="range" id="vad_sensitivity" min="10" max="100" step="5" value="50">
  </div>
</div>

<div class="section">
  <h2>API Keys</h2>
  <div class="field">
    <label>Anthropic</label>
    <div class="key-row">
      <input type="password" id="key_anthropic" placeholder="sk-ant-...">
      <button class="btn btn-outline" onclick="toggleKey('key_anthropic')">Show</button>
    </div>
  </div>
  <div class="field">
    <label>OpenAI</label>
    <div class="key-row">
      <input type="password" id="key_openai" placeholder="sk-...">
      <button class="btn btn-outline" onclick="toggleKey('key_openai')">Show</button>
    </div>
  </div>
  <div class="field">
    <label>ElevenLabs</label>
    <div class="key-row">
      <input type="password" id="key_elevenlabs" placeholder="...">
      <button class="btn btn-outline" onclick="toggleKey('key_elevenlabs')">Show</button>
    </div>
  </div>
  <div class="field">
    <label>OpenRouter</label>
    <div class="key-row">
      <input type="password" id="key_openrouter" placeholder="sk-or-...">
      <button class="btn btn-outline" onclick="toggleKey('key_openrouter')">Show</button>
    </div>
  </div>
</div>

<div class="section">
  <h2>Appearance</h2>
  <div class="field">
    <label>Skin</label>
    <select id="skin"></select>
  </div>
  <div class="toggle">
    <input type="checkbox" id="startup_listening">
    <label for="startup_listening">Start listening on launch</label>
  </div>
</div>

<p class="footer">VII — THE 747 LAB</p>

<div class="save-bar">
  <span class="status" id="saveStatus"></span>
  <button class="btn btn-outline" onclick="loadAll()">Reset</button>
  <button class="btn" onclick="saveAll()">Save Settings</button>
</div>

<script>
let settings = {};

async function loadAll() {
  const r = await fetch('/api/settings');
  settings = await r.json();

  // Populate fields
  document.getElementById('llm_provider').value = settings.llm_provider || 'anthropic';
  document.getElementById('llm_model').value = settings.llm_model || '';
  document.getElementById('ollama_url').value = settings.ollama_url || '';
  document.getElementById('tts_provider').value = settings.tts_provider || 'kokoro';
  document.getElementById('tts_speed').value = settings.tts_speed || 1.0;
  document.getElementById('speed_val').textContent = (settings.tts_speed || 1.0) + 'x';
  document.getElementById('mic_gain').value = settings.mic_gain || 30;
  document.getElementById('gain_val').textContent = (settings.mic_gain || 30) + 'x';
  document.getElementById('hands_free').checked = settings.hands_free || false;
  document.getElementById('vad_sensitivity').value = settings.vad_sensitivity || 50;
  document.getElementById('vad_val').textContent = (settings.vad_sensitivity || 50) + '%';
  document.getElementById('startup_listening').checked = settings.startup_listening || false;

  // API keys
  const keys = settings.api_keys || {};
  document.getElementById('key_anthropic').value = keys.anthropic || '';
  document.getElementById('key_openai').value = keys.openai || '';
  document.getElementById('key_elevenlabs').value = keys.elevenlabs || '';
  document.getElementById('key_openrouter').value = keys.openrouter || '';

  // Audio devices
  const dr = await fetch('/api/audio-devices');
  const dd = await dr.json();
  const inp = document.getElementById('input_device');
  const out = document.getElementById('output_device');
  inp.textContent = ''; out.textContent = '';
  (dd.devices || []).forEach(d => {
    if (d.inputs > 0) {
      const o = document.createElement('option');
      o.value = d.id; o.textContent = d.name + (d.default_input ? ' (default)' : '');
      inp.appendChild(o);
    }
    if (d.outputs > 0) {
      const o = document.createElement('option');
      o.value = d.id; o.textContent = d.name + (d.default_output ? ' (default)' : '');
      out.appendChild(o);
    }
  });

  // TTS voices
  const vr = await fetch('/api/tts-voices');
  const vd = await vr.json();
  const voiceSelect = document.getElementById('tts_voice');
  voiceSelect.textContent = '';
  const provider = settings.tts_provider || 'kokoro';
  (vd[provider] || []).forEach(v => {
    const o = document.createElement('option');
    o.value = v.id; o.textContent = v.name;
    if (v.id === settings.tts_voice) o.selected = true;
    voiceSelect.appendChild(o);
  });

  // Skins
  try {
    const sr = await fetch('/api/settings');
    const skinSelect = document.getElementById('skin');
    skinSelect.textContent = '';
    ['orb', 'minimal', '747'].forEach(s => {
      const o = document.createElement('option');
      o.value = s; o.textContent = s.charAt(0).toUpperCase() + s.slice(1);
      if (s === settings.skin) o.selected = true;
      skinSelect.appendChild(o);
    });
  } catch(e) {}

  // Ollama section toggle
  toggleOllama();
}

function toggleOllama() {
  const show = document.getElementById('llm_provider').value === 'ollama';
  document.getElementById('ollama_section').style.display = show ? 'block' : 'none';
}
document.getElementById('llm_provider').addEventListener('change', toggleOllama);

async function checkOllama() {
  const r = await fetch('/api/ollama-models');
  const d = await r.json();
  if (d.ok) {
    alert('Connected. Models: ' + d.models.join(', '));
  } else {
    alert('Cannot connect to Ollama. Make sure it is running.');
  }
}

async function saveAll() {
  const data = {
    llm_provider: document.getElementById('llm_provider').value,
    llm_model: document.getElementById('llm_model').value,
    ollama_url: document.getElementById('ollama_url').value,
    tts_provider: document.getElementById('tts_provider').value,
    tts_voice: document.getElementById('tts_voice').value,
    tts_speed: parseFloat(document.getElementById('tts_speed').value),
    input_device: document.getElementById('input_device').value,
    output_device: document.getElementById('output_device').value,
    mic_gain: parseFloat(document.getElementById('mic_gain').value),
    hands_free: document.getElementById('hands_free').checked,
    vad_sensitivity: parseInt(document.getElementById('vad_sensitivity').value),
    startup_listening: document.getElementById('startup_listening').checked,
    skin: document.getElementById('skin').value,
    api_keys: {
      anthropic: document.getElementById('key_anthropic').value,
      openai: document.getElementById('key_openai').value,
      elevenlabs: document.getElementById('key_elevenlabs').value,
      openrouter: document.getElementById('key_openrouter').value,
    }
  };
  await fetch('/api/settings', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data)
  });
  document.getElementById('saveStatus').textContent = 'Saved';
  setTimeout(() => document.getElementById('saveStatus').textContent = '', 2000);
}

function toggleKey(id) {
  const el = document.getElementById(id);
  el.type = el.type === 'password' ? 'text' : 'password';
}

// Range sliders
document.getElementById('tts_speed').addEventListener('input', e => {
  document.getElementById('speed_val').textContent = e.target.value + 'x';
});
document.getElementById('mic_gain').addEventListener('input', e => {
  document.getElementById('gain_val').textContent = e.target.value + 'x';
});
document.getElementById('vad_sensitivity').addEventListener('input', e => {
  document.getElementById('vad_val').textContent = e.target.value + '%';
});

loadAll();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    print("\n  VII Settings — http://localhost:7748\n")
    uvicorn.run(app, host="127.0.0.1", port=7748, log_level="warning")
