#!/bin/bash
# Start Jarvis — local web server only (localhost-only by default)

JARVIS_DIR="$HOME/jarvis"
cd "$JARVIS_DIR"
source venv/bin/activate

# Kill any existing instances
pkill -f "ui/server.py" 2>/dev/null
# Tear down stale TTS daemons too — they used to orphan across restarts and pile
# up (each holds its model in RAM), leaving stale sockets that cause /api/tts
# connection-refused. The server self-heals the socket, but reap the processes.
pkill -f "kokoro_daemon.py" 2>/dev/null
pkill -f "clone_daemon.py" 2>/dev/null
# Hygiene: tear down any stray cloudflared from a previous (now-removed) tunnel.
pkill -f "cloudflared" 2>/dev/null
sleep 1

# Start web server
echo "Starting JARVIS web interface..."
python3 ui/server.py &
sleep 2

# Local access only — the server is reachable on this machine and nowhere else.
echo ""
echo "════════════════════════════════════════"
echo "  JARVIS LOCAL ACCESS URL:"
echo "  http://localhost:8080"
echo "════════════════════════════════════════"

# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC TUNNEL — DISABLED ON PURPOSE. DO NOT RE-ENABLE AS-IS.
# ─────────────────────────────────────────────────────────────────────────────
# This used to run `cloudflared tunnel --url http://localhost:8080`, which
# published the Flask server to the public internet via a *.trycloudflare.com
# URL. The server's ONLY access control is a loopback (localhost) check, so a
# tunnel makes every endpoint world-reachable and COMPLETELY UNAUTHENTICATED —
# including:
#     /api/execute  -> arbitrary code execution on this host
#     /api/agent    -> remote screen / mouse / keyboard control
#     /api/chat, /api/history
# In other words: an open tunnel == unauthenticated remote code execution and
# full takeover of this machine by anyone who learns (or guesses) the URL.
#
# This block must STAY commented out until BOTH of the following are in place:
#   1. Per-session token authentication on every endpoint (finding C2) — the
#      loopback check is NOT auth and is bypassed the moment traffic arrives
#      over a tunnel.
#   2. Cloudflare Access (or equivalent) enforcing identity in front of the
#      tunnel, so the origin is never directly exposed.
# Re-enabling without BOTH is a critical security regression. Don't.
#
# # echo "Opening tunnel for phone access..."
# # cloudflared tunnel --url http://localhost:8080 2>&1 | grep -o 'https://[^ ]*\.trycloudflare\.com' | while read url; do
# #     echo ""
# #     echo "════════════════════════════════════════"
# #     echo "  JARVIS PHONE ACCESS URL:"
# #     echo "  $url"
# #     echo "  Open this on your phone from anywhere"
# #     echo "════════════════════════════════════════"
# #     # Copy to clipboard
# #     echo "$url" | pbcopy
# #     # Show notification
# #     osascript -e "display notification \"$url\" with title \"JARVIS Online\""
# # done &
# ─────────────────────────────────────────────────────────────────────────────

wait
