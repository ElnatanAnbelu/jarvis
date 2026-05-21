import subprocess
import threading
import time
import os
from pathlib import Path
from datetime import datetime

DISTRACTION_APPS = [
    "youtube", "netflix", "tiktok", "instagram", "twitter", "facebook",
    "reddit", "twitch", "hulu", "discord", "snapchat", "x.com"
]

FOCUS_STATE_FILE = Path(__file__).parent.parent / ".focus_mode"
_monitor_thread = None
_running = False


def is_focus_on() -> bool:
    return FOCUS_STATE_FILE.exists()


def enable_focus():
    FOCUS_STATE_FILE.write_text("on")
    _start_monitor()
    return "Focus mode on. I'm watching."


def disable_focus():
    FOCUS_STATE_FILE.unlink(missing_ok=True)
    return "Focus mode off."


def get_active_url() -> str:
    try:
        script = '''
tell application "Google Chrome"
    if (count of windows) > 0 then
        return URL of active tab of front window
    end if
end tell
'''
        result = subprocess.run(["osascript", "-e", script],
                                capture_output=True, text=True, timeout=5)
        return result.stdout.strip().lower()
    except Exception:
        return ""


def get_active_app() -> str:
    try:
        script = 'tell application "System Events" to return name of first application process whose frontmost is true'
        result = subprocess.run(["osascript", "-e", script],
                                capture_output=True, text=True, timeout=5)
        return result.stdout.strip().lower()
    except Exception:
        return ""


def _send_telegram_warning(message: str):
    try:
        env_path = Path(__file__).parent.parent / ".env"
        token, chat_id = "", ""
        for line in env_path.read_text().splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                token = line.split("=", 1)[1].strip()
            if line.startswith("TELEGRAM_CHAT_ID="):
                chat_id = line.split("=", 1)[1].strip()
        if token and chat_id:
            import requests
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": f"⚠️ *FOCUS MODE*\n{message}", "parse_mode": "Markdown"},
                timeout=5,
            )
    except Exception:
        pass


def _monitor_loop():
    global _running
    last_warned = {}
    while _running and is_focus_on():
        url = get_active_url()
        for distraction in DISTRACTION_APPS:
            if distraction in url:
                now = time.time()
                if distraction not in last_warned or now - last_warned[distraction] > 600:
                    _send_telegram_warning(f"You're on {distraction}. Get back to work.")
                    last_warned[distraction] = now
                break
        time.sleep(60)


def _start_monitor():
    global _monitor_thread, _running
    _running = True
    _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
    _monitor_thread.start()


def resume_if_active():
    """Call on startup to resume focus mode if it was previously enabled."""
    if is_focus_on():
        _start_monitor()
