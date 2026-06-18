"""Presence detection — drives away-mode automatically (you chose presence-based).

Local + free: uses macOS HID idle time (via ioreg, no deps) and, best-effort,
screen-lock state (via Quartz if pyobjc is present). When you're away (screen
locked or idle past the threshold), autonomy's away-mode turns on so red-list
actions confirm; when you're back, it turns off.

Disable auto-sync with JARVIS_PRESENCE_AWAY=0. Threshold: JARVIS_AWAY_IDLE_SECS.
"""
import os
import re
import subprocess

AWAY_IDLE_SECS = int(os.environ.get("JARVIS_AWAY_IDLE_SECS", "300"))  # 5 min idle → away


def idle_seconds() -> float:
    """Seconds since the last keyboard/mouse input (macOS HIDIdleTime)."""
    try:
        out = subprocess.check_output(["ioreg", "-c", "IOHIDSystem"], text=True, timeout=5)
        m = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', out)
        if m:
            return int(m.group(1)) / 1_000_000_000.0
    except Exception:
        return 0.0
    return 0.0


def screen_locked() -> bool:
    """True if the screen is locked (best-effort; False if Quartz unavailable)."""
    try:
        from Quartz import CGSessionCopyCurrentDictionary
        d = CGSessionCopyCurrentDictionary()
        return bool(d and d.get("CGSSessionScreenIsLocked", 0))
    except Exception:
        return False


def is_away() -> bool:
    """Away when the screen is locked or input has been idle past the threshold."""
    return screen_locked() or idle_seconds() >= AWAY_IDLE_SECS


def auto_update_away() -> bool:
    """Sync autonomy away-mode from presence (no-op if disabled). Returns away state."""
    if os.environ.get("JARVIS_PRESENCE_AWAY", "1") == "0":
        from brain import autonomy
        return autonomy.is_away()
    away = is_away()
    try:
        from brain import autonomy
        if autonomy.is_away() != away:
            autonomy.set_away(away)
            from obs.log import log_event
            log_event("presence.away_changed", away=away)
    except Exception:
        pass
    return away
