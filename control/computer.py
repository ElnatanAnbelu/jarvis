import sys
import base64
import subprocess
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pyautogui
import io

pyautogui.PAUSE = 0.3
pyautogui.FAILSAFE = True  # move mouse to top-left corner to abort


def get_screen_size():
    return pyautogui.size()


def screenshot() -> str:
    """Take a screenshot and return as base64 PNG string."""
    img = pyautogui.screenshot()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


def left_click(x: int, y: int):
    pyautogui.click(x, y)
    time.sleep(0.5)


def double_click(x: int, y: int):
    pyautogui.doubleClick(x, y)
    time.sleep(0.5)


def right_click(x: int, y: int):
    pyautogui.rightClick(x, y)
    time.sleep(0.5)


def mouse_move(x: int, y: int):
    pyautogui.moveTo(x, y, duration=0.3)


def type_text(text: str):
    pyautogui.write(text, interval=0.04)
    time.sleep(0.3)


def press_key(key: str):
    """
    Supports single keys and combos like 'cmd+t', 'ctrl+c', 'cmd+shift+n'.
    """
    if "+" in key:
        parts = key.lower().split("+")
        mods = parts[:-1]
        k = parts[-1]
        pyautogui.hotkey(*mods, k)
    else:
        pyautogui.press(key)
    time.sleep(0.3)


def scroll(x: int, y: int, direction: str, amount: int = 3):
    pyautogui.moveTo(x, y)
    clicks = amount if direction == "up" else -amount
    pyautogui.scroll(clicks)
    time.sleep(0.3)


def drag(x1: int, y1: int, x2: int, y2: int):
    pyautogui.dragTo(x2, y2, duration=0.5, startX=x1, startY=y1)
    time.sleep(0.3)
