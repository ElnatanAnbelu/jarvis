#!/usr/bin/env bash
# scripts/build_app.sh
# Builds, signs, installs, and TCC-resets JARVIS.app.
# Run: bash scripts/build_app.sh
# Re-run any time you change app/main.py or jarvis.spec.
set -euo pipefail

JARVIS_HOME="${JARVIS_HOME:-$HOME/jarvis}"
VENV="$JARVIS_HOME/venv"
PYINSTALLER="$VENV/bin/pyinstaller"
ENTITLEMENTS="$JARVIS_HOME/app/jarvis.entitlements"
DIST="$JARVIS_HOME/dist/JARVIS.app"
DEST="$JARVIS_HOME/JARVIS.app"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║     JARVIS App Builder               ║"
echo "╚══════════════════════════════════════╝"
echo "  Project:  $JARVIS_HOME"
echo "  venv:     $VENV"
echo ""

# ── 1. Prerequisites ──────────────────────────────────────────────────────────
if [ ! -x "$PYINSTALLER" ]; then
    echo "ERROR: PyInstaller not found at $PYINSTALLER"
    echo "Run:  $VENV/bin/pip install pyinstaller"
    exit 1
fi
if [ ! -f "$JARVIS_HOME/app/main.py" ]; then
    echo "ERROR: $JARVIS_HOME/app/main.py not found."
    echo "Is JARVIS_HOME set correctly? (current: $JARVIS_HOME)"
    exit 1
fi
if [ ! -f "$ENTITLEMENTS" ]; then
    echo "ERROR: Entitlements file not found at $ENTITLEMENTS"
    exit 1
fi

# ── 2. Build ──────────────────────────────────────────────────────────────────
echo "[1/5] Building frozen app with PyInstaller..."
cd "$JARVIS_HOME"
"$PYINSTALLER" --clean -y jarvis.spec
echo "      Build complete → $DIST"

# ── 3. Sign ───────────────────────────────────────────────────────────────────
echo ""
echo "[2/5] Code-signing with entitlements (ad-hoc)..."
codesign --force --deep --sign - \
    --entitlements "$ENTITLEMENTS" \
    --identifier com.elnatan.jarvis \
    "$DIST"
echo "      Signed OK"

# ── 4. Install ────────────────────────────────────────────────────────────────
echo ""
echo "[3/5] Installing JARVIS.app to $DEST..."
rm -rf "$DEST"
cp -R "$DIST" "$DEST"
echo "      Installed OK"

# ── 5. Reset TCC ──────────────────────────────────────────────────────────────
echo ""
echo "[4/5] Resetting TCC entries for com.elnatan.jarvis..."
tccutil reset Camera      com.elnatan.jarvis 2>/dev/null || true
tccutil reset Microphone  com.elnatan.jarvis 2>/dev/null || true
echo "      TCC reset OK"

# ── 6. Done ───────────────────────────────────────────────────────────────────
echo ""
echo "[5/5] Done!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  NEXT STEP: Launch JARVIS.app and grant permissions"
echo ""
echo "  Option A (GUI):  double-click ~/jarvis/JARVIS.app"
echo "  Option B (CLI):  open '$DEST'"
echo ""
echo "  When macOS asks, click ALLOW for:"
echo "    • Camera"
echo "    • Microphone"
echo ""
echo "  Both prompts should say 'JARVIS wants access to...'."
echo "  If they say 'Python wants access', something went wrong —"
echo "  re-run this script."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
