#!/usr/bin/env bash
# scripts/setup_new_mac.sh
# One-command setup on a fresh Apple Silicon Mac.
# Usage: cd ~/jarvis && bash scripts/setup_new_mac.sh
set -euo pipefail

JARVIS_HOME="${JARVIS_HOME:-$HOME/jarvis}"
VENV="$JARVIS_HOME/venv"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║    JARVIS New-Mac Setup              ║"
echo "╚══════════════════════════════════════╝"
echo "  Target: $JARVIS_HOME"
echo ""

# ── 1. Homebrew ───────────────────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
    echo "[1/4] Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add Homebrew to PATH for this session (Apple Silicon default)
    eval "$(/opt/homebrew/bin/brew shellenv)"
else
    echo "[1/4] Homebrew already installed — skipping."
fi

# ── 2. ffmpeg ─────────────────────────────────────────────────────────────────
if ! command -v ffmpeg &>/dev/null; then
    echo "[2/4] Installing ffmpeg..."
    brew install ffmpeg
else
    echo "[2/4] ffmpeg already installed — skipping."
fi

# ── 3. Python venv ────────────────────────────────────────────────────────────
echo "[3/4] Creating arm64 venv and installing dependencies..."

if [ ! -d "$VENV" ]; then
    echo "  Creating venv at $VENV..."
    arch -arm64 python3 -m venv "$VENV"
fi

"$VENV/bin/pip" install --upgrade pip --quiet

if [ ! -f "$JARVIS_HOME/requirements.txt" ]; then
    echo "ERROR: requirements.txt not found at $JARVIS_HOME/requirements.txt"
    echo "Generate it on the old Mac: cd ~/jarvis && ./venv/bin/pip freeze > requirements.txt"
    exit 1
fi

echo "  Installing from requirements.txt (this takes a few minutes)..."
"$VENV/bin/pip" install -r "$JARVIS_HOME/requirements.txt" --quiet

# Ensure PyInstaller is present (may not be in requirements.txt)
"$VENV/bin/pip" install pyinstaller --quiet

echo "  Dependencies installed OK"

# ── 4. Build the app ──────────────────────────────────────────────────────────
echo "[4/4] Building JARVIS.app..."
bash "$JARVIS_HOME/scripts/build_app.sh"
