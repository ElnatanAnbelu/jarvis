#!/bin/bash
# Start Jarvis — web server + Cloudflare tunnel for phone access

JARVIS_DIR="$HOME/jarvis"
cd "$JARVIS_DIR"
source venv/bin/activate

# Kill any existing instances
pkill -f "ui/server.py" 2>/dev/null
pkill -f "cloudflared" 2>/dev/null
sleep 1

# Start web server
echo "Starting JARVIS web interface..."
python3 ui/server.py &
sleep 2

# Start Cloudflare tunnel
echo "Opening tunnel for phone access..."
cloudflared tunnel --url http://localhost:8080 2>&1 | grep -o 'https://[^ ]*\.trycloudflare\.com' | while read url; do
    echo ""
    echo "════════════════════════════════════════"
    echo "  JARVIS PHONE ACCESS URL:"
    echo "  $url"
    echo "  Open this on your phone from anywhere"
    echo "════════════════════════════════════════"
    # Copy to clipboard
    echo "$url" | pbcopy
    # Show notification
    osascript -e "display notification \"$url\" with title \"JARVIS Online\""
done &

wait
