#!/bin/bash
# JARVIS — One-command startup
# Opens: web server + side control terminal + browser UI

DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/venv/bin/activate"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║       J.A.R.V.I.S  STARTING UP      ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# Kill any existing JARVIS server on port 8080
lsof -ti:8080 | xargs kill -9 2>/dev/null

# Load env vars
export $(grep -v '^#' "$DIR/.env" | grep -v '^$' | xargs) 2>/dev/null

# Start web server in background
echo "  [1/3] Starting JARVIS web server..."
source "$VENV" && python "$DIR/ui/server.py" &
SERVER_PID=$!
sleep 2

# Open browser
echo "  [2/3] Opening JARVIS UI..."
open http://localhost:8080

# Open side control terminal in new window
echo "  [3/3] Opening control terminal..."
osascript -e "tell application \"Terminal\"
  activate
  do script \"source '$VENV' && python '$DIR/jarvis_ctl.py'\"
  delay 0.5
  do script \"source '$VENV' && python '$DIR/voice_daemon.py'\"
end tell" 2>/dev/null

echo ""
echo "  JARVIS is online."
echo "  Web UI:     http://localhost:8080"
echo "  Control:    side terminal window"
echo "  Press Ctrl+C here to shut everything down."
echo ""

# Wait and catch shutdown
trap "kill $SERVER_PID 2>/dev/null; echo 'JARVIS offline.'; exit" INT TERM
wait $SERVER_PID
