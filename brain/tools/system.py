"""System tools — app control, screen, volume, music, focus."""
import subprocess
from brain.tools.registry import tool


@tool(
    description="Open a Mac application",
    parameters={
        "app": {"type": "string", "description": "Application name e.g. Safari, Spotify, Xcode"},
    }
)
def open_app(app: str) -> str:
    subprocess.Popen(["open", "-a", app])
    return f"Opened {app}."


@tool(
    description="Take a screenshot of the current screen",
    parameters={}
)
def take_screenshot() -> str:
    import time
    from control.mac import screenshot
    time.sleep(1.5)
    path = screenshot()
    return f"Screenshot taken. [SHOW: {path}] Tell me what you see on screen and whether it looks correct."


@tool(
    description="Get the current battery level",
    parameters={}
)
def get_battery() -> str:
    from control.mac import get_battery as _get
    return f"Battery: {_get()}"


@tool(
    description="Control the Mac screen — click, type, navigate apps, open websites. Use for multi-step tasks.",
    parameters={
        "task": {"type": "string", "description": "Full description of what to do on screen"},
    }
)
def control_screen(task: str) -> str:
    from control.agent import get_agent
    return get_agent().run(task)


@tool(
    description="Set the Mac system volume (0-100) or mute/unmute",
    parameters={
        "level": {"type": "integer", "description": "Volume level 0-100, or -1 to toggle mute"},
    }
)
def set_volume(level: int) -> str:
    level = int(level)
    if level == -1:
        subprocess.run(["osascript", "-e", "set volume output muted not (output muted of (get volume settings))"])
        return "Volume toggled."
    subprocess.run(["osascript", "-e", f"set volume output volume {max(0, min(100, level))}"])
    return f"Volume set to {level}."


@tool(
    description="Enable or disable focus mode — monitors for distracting websites and warns via Telegram",
    parameters={
        "action": {"type": "string", "description": "Turn focus mode on or off"},
    }
)
def focus_mode(action: str) -> str:
    from control.focus import enable_focus, disable_focus
    return enable_focus() if action == "on" else disable_focus()


@tool(
    description="Take a screenshot and read all text visible on screen using OCR. Use when asked 'what's on my screen' or to read something visible.",
    parameters={}
)
def read_screen() -> str:
    import tempfile, os
    tmp = tempfile.mktemp(suffix=".png")
    subprocess.run(["screencapture", "-x", tmp], timeout=5)
    try:
        import pytesseract
        from PIL import Image
        text = pytesseract.image_to_string(Image.open(tmp)).strip()
        os.unlink(tmp)
        return text[:2000] if text else "No readable text found on screen."
    except Exception as e:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        return f"OCR error: {e}"


@tool(
    description="Control Apple Music — play, pause, skip to next or previous track",
    parameters={
        "action": {"type": "string", "description": "Music action: play, pause, next, prev, toggle"},
    }
)
def control_music(action: str) -> str:
    scripts = {
        "play":   'tell application "Music" to play',
        "pause":  'tell application "Music" to pause',
        "next":   'tell application "Music" to next track',
        "prev":   'tell application "Music" to previous track',
        "toggle": 'tell application "Music" to playpause',
    }
    if action in scripts:
        subprocess.run(["osascript", "-e", scripts[action]], timeout=3)
    return {"play": "Playing.", "pause": "Paused.", "next": "Next track.",
            "prev": "Previous track.", "toggle": "Toggled."}.get(action, "Done.")
