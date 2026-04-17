#!/bin/bash
# VII — One-Line Installer
# curl -fsSL https://vii.747lab.ai/install.sh | bash
#
# Installs VII Voice Intelligence Interface on macOS.
# Developed by The 747 Lab

set -e

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║  VII — Voice Intelligence Interface  ║"
echo "  ║  The 747 Lab                         ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# Check macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "  VII currently supports macOS only."
    echo "  Windows and Linux support coming soon."
    exit 1
fi

INSTALL_DIR="$HOME/.vii"

echo "  Installing to: $INSTALL_DIR"
echo ""

# Check Python 3.11+
PYTHON=""
for py in python3.13 python3.12 python3.11 python3; do
    if command -v "$py" &>/dev/null; then
        VER=$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        MAJOR=$(echo "$VER" | cut -d. -f1)
        MINOR=$(echo "$VER" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 11 ]; then
            PYTHON="$py"
            echo "  Python: $VER ($py)"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "  Python 3.11+ required. Install with:"
    echo "    brew install python@3.13"
    exit 1
fi

# Check ffmpeg
if ! command -v ffmpeg &>/dev/null; then
    echo "  Installing ffmpeg..."
    brew install ffmpeg 2>/dev/null || echo "  Please install ffmpeg manually: brew install ffmpeg"
fi

# Create install directory
mkdir -p "$INSTALL_DIR"

# Clone or update
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "  Updating VII..."
    cd "$INSTALL_DIR" && git pull --quiet
else
    echo "  Downloading VII..."
    # For now, copy from local. When on GitHub, this becomes git clone
    if [ -d "$HOME/.openclaw/workspace/projects/vii-two" ]; then
        cp -r "$HOME/.openclaw/workspace/projects/vii-two/"* "$INSTALL_DIR/"
        cp -r "$HOME/.openclaw/workspace/projects/vii-two/."* "$INSTALL_DIR/" 2>/dev/null || true
    else
        echo "  ERROR: VII source not found. Please clone from GitHub first."
        exit 1
    fi
fi

cd "$INSTALL_DIR"

# Create venv
if [ ! -d "venv" ]; then
    echo "  Creating Python environment..."
    "$PYTHON" -m venv venv
fi

# Install dependencies
echo "  Installing dependencies..."
./venv/bin/pip install -q PyQt6 sounddevice soundfile numpy httpx kokoro-onnx \
    faster-whisper fastapi uvicorn pynput Pillow sqlalchemy 2>/dev/null

# Download models if not present
MODELS_DIR="$INSTALL_DIR/models"
mkdir -p "$MODELS_DIR/kokoro"

if [ ! -f "$MODELS_DIR/kokoro/kokoro-v1.0.onnx" ]; then
    echo "  Downloading Kokoro TTS model (310MB)..."
    curl -L -# -o "$MODELS_DIR/kokoro/kokoro-v1.0.onnx" \
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
    curl -L -# -o "$MODELS_DIR/kokoro/voices-v1.0.bin" \
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
fi

if [ ! -d "$MODELS_DIR/models--Systran--faster-whisper-small" ]; then
    echo "  Downloading Whisper STT model..."
    ./venv/bin/python3 -c "
from faster_whisper import WhisperModel
print('  Downloading Whisper small model...')
m = WhisperModel('small', device='cpu', compute_type='int8')
print('  Whisper model ready.')
" 2>&1 | grep -v "^$"
fi

# Create config
mkdir -p "$INSTALL_DIR/config"
if [ ! -f "$INSTALL_DIR/config/vii-settings.json" ]; then
    cat > "$INSTALL_DIR/config/vii-settings.json" << 'JSON'
{
  "llm_provider": "anthropic",
  "llm_model": "claude-sonnet-4-20250514",
  "tts_provider": "kokoro",
  "tts_voice": "am_onyx",
  "tts_speed": 1.0,
  "mic_gain": 10.0,
  "hands_free": false,
  "skin": "orb"
}
JSON
fi

# Create launcher
cat > "$INSTALL_DIR/vii" << 'LAUNCHER'
#!/bin/bash
cd "$(dirname "$0")"
exec ./venv/bin/python3 desktop.py "$@"
LAUNCHER
chmod +x "$INSTALL_DIR/vii"

# Create global command
if [ -d "/usr/local/bin" ]; then
    ln -sf "$INSTALL_DIR/vii" /usr/local/bin/vii 2>/dev/null || true
fi

# macOS permissions reminder
echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║  VII installed successfully!         ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
echo "  IMPORTANT — Grant these permissions when prompted:"
echo "    1. Microphone access (for voice input)"
echo "    2. Accessibility (for computer control)"
echo "    3. Screen Recording (for vision features)"
echo ""
echo "  To start VII:"
echo "    vii"
echo ""
echo "  Or:"
echo "    ~/.vii/vii"
echo ""
echo "  First run: Right-click the orb → Preferences"
echo "  to set your API key (Anthropic or use Ollama for free)."
echo ""
echo "  The 747 Lab — Just speak."
echo ""
