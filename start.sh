#!/bin/bash
# VII — Start Everything
# Launches: Desktop orb + Remote server + Cloudflare tunnel
# Developed by The 747 Lab

DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$DIR/tts-venv/bin/python3"
LOG_DIR="$DIR/logs"
mkdir -p "$LOG_DIR"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║  VII — Voice Intelligence Interface  ║"
echo "  ║  The 747 Lab                         ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# Start remote server
echo "  Starting remote server..."
"$PYTHON" "$DIR/remote_server.py" > "$LOG_DIR/remote.log" 2>&1 &
REMOTE_PID=$!
echo "  Remote server PID: $REMOTE_PID"
sleep 2

# Start Cloudflare tunnel if available
if command -v cloudflared &> /dev/null; then
    echo "  Starting Cloudflare tunnel..."
    cloudflared tunnel --url http://localhost:7747 > "$LOG_DIR/tunnel.log" 2>&1 &
    TUNNEL_PID=$!
    sleep 3
    # Extract the public URL
    TUNNEL_URL=$(grep -o "https://.*trycloudflare.com" "$LOG_DIR/tunnel.log" 2>/dev/null | head -1)
    if [ -n "$TUNNEL_URL" ]; then
        echo "  ┌─────────────────────────────────────┐"
        echo "  │ REMOTE ACCESS (from anywhere):       │"
        echo "  │ $TUNNEL_URL │"
        echo "  └─────────────────────────────────────┘"
        # Send URL to Telegram if possible
        BOT_TOKEN="8593543492:AAG4F2I-wPH4TiyU_28jUes5SvqR0G70maQ"
        CHAT_ID="1217359466"
        curl -s "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
            -d "chat_id=${CHAT_ID}" \
            -d "text=VII Remote is live: ${TUNNEL_URL}" \
            -d "parse_mode=HTML" > /dev/null 2>&1
        echo "  Remote URL sent to Telegram."
    else
        echo "  Tunnel starting... check logs/tunnel.log"
    fi
else
    echo "  [cloudflared not found — local access only: http://localhost:7747]"
    echo "  Install: brew install cloudflared"
fi

# Start desktop orb
echo "  Starting desktop orb..."
"$PYTHON" "$DIR/desktop.py" > "$LOG_DIR/desktop.log" 2>&1 &
DESKTOP_PID=$!
echo "  Desktop orb PID: $DESKTOP_PID"

echo ""
echo "  VII is running."
echo "  Desktop: Click the orb to speak"
echo "  Remote:  http://localhost:7747 (or tunnel URL above)"
echo "  Ctrl+C to stop everything"
echo ""

# Save PIDs for cleanup
echo "$REMOTE_PID" > "$DIR/.vii-pids"
echo "$DESKTOP_PID" >> "$DIR/.vii-pids"
[ -n "$TUNNEL_PID" ] && echo "$TUNNEL_PID" >> "$DIR/.vii-pids"

# Wait and handle Ctrl+C
cleanup() {
    echo ""
    echo "  Stopping VII..."
    kill $REMOTE_PID $DESKTOP_PID $TUNNEL_PID 2>/dev/null
    rm -f "$DIR/.vii-pids"
    echo "  VII stopped."
}
trap cleanup EXIT INT TERM

wait
