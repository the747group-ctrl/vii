#!/bin/bash
# VII — Setup auto-start on macOS login
# Creates a LaunchAgent that starts VII when you log in.
# Run: bash setup_autostart.sh

PLIST="$HOME/Library/LaunchAgents/ai.747lab.vii.plist"
VII_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$VII_DIR/tts-venv/bin/python3"

if [ ! -f "$PYTHON" ]; then
    PYTHON="$VII_DIR/venv/bin/python3"
fi

if [ ! -f "$PYTHON" ]; then
    echo "Python not found. Run install.sh first."
    exit 1
fi

cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>ai.747lab.vii</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$VII_DIR/desktop.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$VII_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$VII_DIR/logs/desktop.log</string>
    <key>StandardErrorPath</key>
    <string>$VII_DIR/logs/desktop-error.log</string>
</dict>
</plist>
EOF

mkdir -p "$VII_DIR/logs"

echo "VII auto-start configured."
echo "VII will launch when you log in."
echo ""
echo "To start now:  launchctl load $PLIST"
echo "To disable:    launchctl unload $PLIST"
echo "To remove:     rm $PLIST"
