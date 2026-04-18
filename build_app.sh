#!/bin/bash
# VII — Build macOS .app bundle
# Creates VII.app that you can drag to Applications
# Developed by The 747 Lab

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="VII"
APP_DIR="$DIR/dist/$APP_NAME.app"
CONTENTS="$APP_DIR/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"

echo "Building $APP_NAME.app..."

# Clean
rm -rf "$APP_DIR"
mkdir -p "$MACOS" "$RESOURCES"

# Info.plist
cat > "$CONTENTS/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>VII</string>
    <key>CFBundleDisplayName</key>
    <string>VII — Voice Intelligence Interface</string>
    <key>CFBundleIdentifier</key>
    <string>ai.747lab.vii</string>
    <key>CFBundleVersion</key>
    <string>2.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>2.0</string>
    <key>CFBundleExecutable</key>
    <string>vii-launcher</string>
    <key>CFBundleIconFile</key>
    <string>vii</string>
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSMicrophoneUsageDescription</key>
    <string>VII needs microphone access to hear your voice commands.</string>
    <key>NSAppleEventsUsageDescription</key>
    <string>VII needs accessibility to control your computer by voice.</string>
    <key>NSScreenCaptureUsageDescription</key>
    <string>VII needs screen access to see and analyze what's on your display.</string>
</dict>
</plist>
PLIST

# Launcher script
cat > "$MACOS/vii-launcher" << LAUNCHER
#!/bin/bash
DIR="\$(cd "\$(dirname "\$0")/../../.." && pwd)"
cd "\$DIR"
if [ -d "tts-venv" ]; then
    exec ./tts-venv/bin/python3 desktop.py
elif [ -d "venv" ]; then
    exec ./venv/bin/python3 desktop.py
else
    exec python3 desktop.py
fi
LAUNCHER
chmod +x "$MACOS/vii-launcher"

# Icon (convert PNG to ICNS)
if [ -f "$DIR/assets/vii-icon-256.png" ]; then
    ICONSET="$DIR/dist/vii.iconset"
    mkdir -p "$ICONSET"
    cp "$DIR/assets/vii-icon-256.png" "$ICONSET/icon_256x256.png"
    cp "$DIR/assets/vii-icon-128.png" "$ICONSET/icon_128x128.png" 2>/dev/null || \
        sips -z 128 128 "$DIR/assets/vii-icon-256.png" --out "$ICONSET/icon_128x128.png" 2>/dev/null
    cp "$DIR/assets/vii-icon-32.png" "$ICONSET/icon_32x32.png" 2>/dev/null || \
        sips -z 32 32 "$DIR/assets/vii-icon-256.png" --out "$ICONSET/icon_32x32.png" 2>/dev/null
    cp "$DIR/assets/vii-icon-64.png" "$ICONSET/icon_16x16@2x.png" 2>/dev/null
    iconutil -c icns "$ICONSET" -o "$RESOURCES/vii.icns" 2>/dev/null || true
    rm -rf "$ICONSET"
fi

# Create symlink so the .app can find project files
ln -sf "$DIR" "$CONTENTS/project"

echo ""
echo "  $APP_NAME.app built at: $APP_DIR"
echo ""
echo "  To install:"
echo "    cp -r $APP_DIR /Applications/"
echo ""
echo "  Or just double-click $APP_DIR to run."
echo ""
