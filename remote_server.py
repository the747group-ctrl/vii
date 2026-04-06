#!/usr/bin/env python3
"""
VII Remote — Control your Mac from your phone.
Open http://<your-mac-ip>:7747 on your phone (same WiFi).
Run: ./tts-venv/bin/python3 remote_server.py
Developed by The 747 Lab
"""

import asyncio
import base64
import io
import json
import os
import re
import subprocess
import tempfile
import time

import numpy as np
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAC_CONTROL = os.path.expanduser("~/.747lab/mac-control.sh")
PORT = 7747


def load_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    auth = os.path.expanduser("~/.openclaw/agents/main/agent/auth-profiles.json")
    if os.path.exists(auth):
        with open(auth) as f:
            data = json.load(f)
            return data.get("profiles", {}).get("anthropic:manual", {}).get("token", "")
    return ""


API_KEY = load_api_key()
app = FastAPI(title="VII Remote")
conversation = []


def run_mac(cmd, args=""):
    """Run a mac-control command safely."""
    cmd_list = [MAC_CONTROL, cmd]
    if args:
        cmd_list.append(args)
    result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=10)
    return result.stdout.strip()


@app.get("/", response_class=HTMLResponse)
async def index():
    return MOBILE_UI


@app.get("/api/screen")
async def screenshot():
    png = tempfile.mktemp(suffix=".png")
    proc = await asyncio.create_subprocess_exec(
        "screencapture", "-x", "-C", png,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    await proc.wait()
    if not os.path.exists(png):
        return JSONResponse({"error": "failed"})
    from PIL import Image
    img = Image.open(png)
    if img.width > 1280:
        ratio = 1280 / img.width
        img = img.resize((1280, int(img.height * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=60)
    b64 = base64.b64encode(buf.getvalue()).decode()
    os.unlink(png)
    return JSONResponse({"image": b64, "width": img.width, "height": img.height})


@app.post("/api/click")
async def click(data: dict):
    x, y = int(data["x"]), int(data["y"])
    run_mac("key-press", f"{x},{y}")  # placeholder — actual click via osascript
    proc = await asyncio.create_subprocess_exec(
        "osascript", "-e",
        f'tell application "System Events" to click at {{{x}, {y}}}',
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    await proc.wait()
    await asyncio.sleep(0.3)
    return await screenshot()


@app.post("/api/type")
async def type_text(data: dict):
    text = data.get("text", "")
    safe = "".join(c for c in text if 32 <= ord(c) <= 126 and c not in ('"', '\\'))
    if safe:
        run_mac("type-text", safe)
    return JSONResponse({"ok": True})


@app.post("/api/key")
async def press_key(data: dict):
    combo = data.get("combo", "")
    parts = combo.lower().split("+")
    key = parts[-1].strip()
    mod_map = {"cmd": "command down", "ctrl": "control down",
               "alt": "option down", "shift": "shift down"}
    key_codes = {"space": 49, "return": 36, "tab": 48, "escape": 53, "delete": 51}
    mods = [mod_map[p.strip()] for p in parts[:-1] if p.strip() in mod_map]
    using = f" using {{{', '.join(mods)}}}" if mods else ""
    if key in key_codes:
        script = f'tell application "System Events" to key code {key_codes[key]}{using}'
    elif len(key) == 1:
        script = f'tell application "System Events" to keystroke "{key}"{using}'
    else:
        return JSONResponse({"error": "unknown key"})
    proc = await asyncio.create_subprocess_exec(
        "osascript", "-e", script,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    await proc.wait()
    return JSONResponse({"ok": True})


@app.post("/api/ask")
async def ask(data: dict):
    text = data.get("text", "")
    if not text:
        return JSONResponse({"error": "empty"})
    import httpx
    conversation.append({"role": "user", "content": text})
    system = (
        "You are VII, a voice-controlled AI by The 747 Lab. "
        "You can control the user's Mac. "
        "Actions: [ACTION: open-app Name], [ACTION: open-url URL], "
        "[ACTION: type-text Text], [ACTION: key-combo cmd+key], "
        "[ACTION: screenshot], [ACTION: volume N], [ACTION: notify Title Msg]\n"
        "After actions, confirm briefly. For conversation, 2-3 sentences. No markdown.")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": CLAUDE_MODEL, "max_tokens": 250, "system": system,
                  "messages": conversation[-20:]})
        resp.raise_for_status()
        response_text = resp.json().get("content", [{}])[0].get("text", "")
    conversation.append({"role": "assistant", "content": response_text})
    actions = []
    for action in re.findall(r'\[ACTION:\s*(.+?)\]', response_text):
        parts = action.strip().split(None, 1)
        cmd = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        try:
            out = run_mac(cmd, args)
            actions.append({"cmd": cmd, "result": out or "done"})
        except Exception as e:
            actions.append({"cmd": cmd, "result": str(e)})
    spoken = re.sub(r'\[ACTION:\s*.+?\]', '', response_text).strip()
    return JSONResponse({"response": spoken or "Done.", "actions": actions})


@app.post("/api/command")
async def mac_command(data: dict):
    cmd = data.get("cmd", "")
    args = data.get("args", "")
    if not cmd:
        return JSONResponse({"error": "no cmd"})
    try:
        out = run_mac(cmd, args)
        return JSONResponse({"result": out, "ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)})


MOBILE_UI = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>VII Remote</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a10;color:#d0d0d8;font-family:-apple-system,system-ui,sans-serif;
  display:flex;flex-direction:column;height:100vh;height:100dvh;overflow:hidden}
.hdr{padding:12px 16px;display:flex;align-items:center;justify-content:space-between;
  border-bottom:1px solid #1a1a28}
.hdr h1{font-size:14px;letter-spacing:4px;color:#06b6d4;font-weight:600}
.hdr .st{font-size:10px;color:#444}
.scr{flex:1;overflow:hidden;position:relative;background:#050508}
.scr img{width:100%;height:100%;object-fit:contain}
.scr .hint{position:absolute;bottom:8px;left:50%;transform:translateX(-50%);
  font-size:10px;color:#333;letter-spacing:1px}
.resp{padding:8px 16px;font-size:13px;color:#8b8b9b;min-height:20px;
  border-top:1px solid #1a1a28;max-height:60px;overflow-y:auto}
.ctrls{padding:10px;border-top:1px solid #1a1a28;display:flex;flex-direction:column;gap:8px}
.row{display:flex;gap:8px}
.row input{flex:1;background:#12121e;border:1px solid #252535;border-radius:8px;
  padding:10px 14px;color:#ccc;font-size:14px;outline:none}
.row input:focus{border-color:#06b6d4}
.row button{background:#06b6d4;color:#000;border:none;border-radius:8px;
  padding:10px 16px;font-weight:600;font-size:13px}
.row button:active{opacity:.7}
.qb{display:flex;gap:6px;flex-wrap:wrap}
.q{background:#1a1a28;border:1px solid #252535;border-radius:6px;padding:8px 10px;
  color:#888;font-size:11px;flex:1;text-align:center;min-width:55px}
.q:active{background:#252535;color:#fff}
.ft{text-align:center;padding:6px;font-size:9px;color:#222;letter-spacing:2px}
</style>
</head>
<body>
<div class="hdr"><h1>VII REMOTE</h1><span class="st" id="st">Loading</span></div>
<div class="scr" id="sw"><img id="si" style="display:none"><div class="hint">Tap to click</div></div>
<div class="resp" id="rsp"></div>
<div class="ctrls">
  <div class="row">
    <input id="inp" placeholder="Ask VII or type command...">
    <button id="btn">Send</button>
  </div>
  <div class="qb">
    <div class="q" data-c="screenshot">Screen</div>
    <div class="q" data-k="cmd+space">Spotlight</div>
    <div class="q" data-k="cmd+tab">Switch</div>
    <div class="q" data-k="cmd+w">Close</div>
    <div class="q" data-k="space">Play</div>
    <div class="q" data-a="volume 50">Vol</div>
  </div>
</div>
<div class="ft">THE 747 LAB</div>
<script>
const si=document.getElementById('si'),sw=document.getElementById('sw'),
  inp=document.getElementById('inp'),btn=document.getElementById('btn'),
  rsp=document.getElementById('rsp'),st=document.getElementById('st');
let sW=0,sH=0;

async function scr(){
  st.textContent='Capturing...';
  const r=await fetch('/api/screen');const d=await r.json();
  if(d.image){si.src='data:image/jpeg;base64,'+d.image;si.style.display='block';}
  const s=await(await fetch('/api/command',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({cmd:'screen-size'})})).json();
  if(s.result){const p=s.result.split(/[x,]/);sW=+p[0];sH=+p[1];}
  st.textContent='Connected';
}

sw.onclick=async e=>{
  if(!si.src||!sW)return;
  const r=si.getBoundingClientRect();
  const x=Math.round((e.clientX-r.left)/r.width*sW);
  const y=Math.round((e.clientY-r.top)/r.height*sH);
  st.textContent='Click '+x+','+y;
  const d=await(await fetch('/api/click',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({x,y})})).json();
  if(d.image){si.src='data:image/jpeg;base64,'+d.image;}
  st.textContent='Connected';
};

btn.onclick=async()=>{
  const t=inp.value.trim();if(!t)return;inp.value='';
  rsp.textContent='Thinking...';st.textContent='Processing...';
  const d=await(await fetch('/api/ask',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({text:t})})).json();
  rsp.textContent=d.response||'Done.';
  if(d.actions&&d.actions.length)await scr();
  st.textContent='Connected';
};

inp.onkeydown=e=>{if(e.key==='Enter')btn.click();};

document.querySelectorAll('.q').forEach(b=>{
  b.onclick=async()=>{
    if(b.dataset.c==='screenshot'){await scr();return;}
    if(b.dataset.k){
      await fetch('/api/key',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({combo:b.dataset.k})});
      setTimeout(scr,500);
    }
    if(b.dataset.a){
      const p=b.dataset.a.split(' ');
      await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({cmd:p[0],args:p.slice(1).join(' ')})});
    }
  };
});
scr();
</script>
</body>
</html>"""

if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: No API key");sys.exit(1)
    import socket
    try:
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(("8.8.8.8",80))
        ip=s.getsockname()[0];s.close()
    except:ip="localhost"
    print(f"\n  VII Remote — The 747 Lab")
    print(f"  Phone: http://{ip}:{PORT}\n")
    uvicorn.run(app,host="0.0.0.0",port=PORT,log_level="warning")
