#!/bin/bash
set -euo pipefail

if [ "$(uname -s)" != "Darwin" ]; then
  echo "voice-speak currently requires macOS because playback uses afplay and fallback uses say." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.10+ is required. Install it first, for example: brew install python" >&2
  exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
  echo "Python 3.10+ is required. Current python3 is older." >&2
  exit 1
fi

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$HOME/.local/share/voice-speak"
BIN_DIR="$HOME/.local/bin"

mkdir -p "$APP_DIR" "$BIN_DIR"

if [ ! -x "$APP_DIR/venv/bin/python" ]; then
  python3 -m venv "$APP_DIR/venv"
fi

if ! "$APP_DIR/venv/bin/python" -c "import edge_tts" >/dev/null 2>&1; then
  "$APP_DIR/venv/bin/python" -m pip install --quiet --upgrade pip
  "$APP_DIR/venv/bin/python" -m pip install --quiet edge-tts
fi
"$APP_DIR/venv/bin/python" -c "import edge_tts" >/dev/null

cp "$SKILL_DIR/scripts/voice_speak.py" "$APP_DIR/voice_speak.py"
if [ ! -f "$APP_DIR/config.json" ]; then
  cp "$SKILL_DIR/scripts/config.json" "$APP_DIR/config.json"
fi

cat > "$BIN_DIR/voice-speak" <<'WRAPPER'
#!/bin/bash
exec "$HOME/.local/share/voice-speak/venv/bin/python" "$HOME/.local/share/voice-speak/voice_speak.py" "$@"
WRAPPER
chmod +x "$BIN_DIR/voice-speak"

"$BIN_DIR/voice-speak" --dry-run "voice-speak 安装完成。" >/dev/null

echo "installed: $BIN_DIR/voice-speak"
if ! printf '%s' "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
  echo "note: $BIN_DIR is not in PATH; call $BIN_DIR/voice-speak directly or add it to PATH."
fi
