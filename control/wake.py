import subprocess
import threading
import time
from pathlib import Path
from datetime import date

WAKE_LOG_FILE = Path(__file__).parent.parent / ".last_wake_date"


def get_last_sleep_wake():
    """Get the last wake time from pmset log."""
    try:
        result = subprocess.run(
            ["pmset", "-g", "log"],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.splitlines()
        for line in reversed(lines):
            if "Wake from" in line or "DarkWake" not in line and "Wake" in line:
                return line.strip()
    except Exception:
        pass
    return None


def on_wake_callback():
    """Called when Mac wakes — trigger briefing if not sent today."""
    today = str(date.today())
    if WAKE_LOG_FILE.exists() and WAKE_LOG_FILE.read_text().strip() == today:
        return
    WAKE_LOG_FILE.write_text(today)

    try:
        from brain.briefing import generate_briefing, already_sent_today, mark_sent
        if already_sent_today():
            return
        text = generate_briefing()
        mark_sent()

        # Send to Telegram
        from pathlib import Path as _Path
        import requests, os
        env = _Path(__file__).parent.parent / ".env"
        token, chat_id = "", ""
        for line in env.read_text().splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                token = line.split("=", 1)[1].strip()
            if line.startswith("TELEGRAM_CHAT_ID="):
                chat_id = line.split("=", 1)[1].strip()
        if token and chat_id:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id,
                      "text": f"*JARVIS — Morning Briefing*\n\n{text}",
                      "parse_mode": "Markdown"},
                timeout=10,
            )
    except Exception as e:
        print(f"Wake briefing error: {e}")


def _watch_wake_events():
    """Monitor system wake events using pmset."""
    try:
        proc = subprocess.Popen(
            ["log", "stream", "--predicate",
             'eventMessage contains "Wake reason" OR eventMessage contains "System Wake"',
             "--style", "compact"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
        )
        for line in proc.stdout:
            if "Wake" in line:
                threading.Thread(target=on_wake_callback, daemon=True).start()
    except Exception:
        pass


def start_wake_monitor():
    """Start background thread monitoring Mac wake events."""
    t = threading.Thread(target=_watch_wake_events, daemon=True)
    t.start()
