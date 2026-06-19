#!/usr/bin/env bash
# scripts/build_app.sh — build Alfred.app as a thin native LAUNCHER.
#
# This does NOT freeze the code (the old PyInstaller freeze is exactly what rotted
# the previous JARVIS.app to 3-week-old code). Alfred.app simply double-clicks into
# the LIVE source — ./venv/bin/python app/main.py — so it is ALWAYS current, tiny,
# and reliable. Mic/camera prompts attribute to "Alfred" via the Info.plist usage
# strings + an ad-hoc signature.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/Alfred.app"

echo "Building Alfred.app (launcher) → $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Alfred</string>
  <key>CFBundleDisplayName</key><string>Alfred</string>
  <key>CFBundleExecutable</key><string>Alfred</string>
  <key>CFBundleIdentifier</key><string>com.elnatan.alfred</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSMicrophoneUsageDescription</key><string>Alfred listens for your voice so you can speak to him.</string>
  <key>NSCameraUsageDescription</key><string>Alfred sees you to recognise your presence and face.</string>
</dict>
</plist>
PLIST

cat > "$APP/Contents/MacOS/Alfred" <<LAUNCH
#!/bin/bash
# Alfred — launches the live source (never frozen, never stale).
cd "$ROOT" || exit 1
exec ./venv/bin/python app/main.py >> /tmp/alfred_app.log 2>&1
LAUNCH
chmod +x "$APP/Contents/MacOS/Alfred"

# Ad-hoc sign so macOS attributes mic/camera prompts to "Alfred".
codesign --force --deep --sign - --identifier com.elnatan.alfred "$APP" 2>/dev/null \
  && echo "  signed (ad-hoc)" || echo "  (codesign skipped)"
tccutil reset Camera      com.elnatan.alfred 2>/dev/null || true
tccutil reset Microphone  com.elnatan.alfred 2>/dev/null || true

echo "Done → double-click $APP (grant Camera + Microphone when asked)."
