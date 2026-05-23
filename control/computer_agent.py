"""
Computer use agent — screenshot → Claude vision → actions → loop.
"""
import base64
import json
import time
import io
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pyautogui
pyautogui.PAUSE = 0.4
pyautogui.FAILSAFE = True

SCREEN_W, SCREEN_H = pyautogui.size()

ALLOWED_ACTIONS = {
    "click", "double_click", "right_click", "move",
    "type", "key", "scroll", "drag", "wait", "done",
}

DESTRUCTIVE_KEYS = {
    "cmd+q", "cmd+w", "cmd+delete", "cmd+shift+delete",
    "ctrl+c", "ctrl+z",
}

SYSTEM_PROMPT = f"""You are JARVIS, an AI controlling a macOS computer screen ({SCREEN_W}x{SCREEN_H}).
You receive screenshots and a task. You output a JSON array of actions to perform.

ACTIONS (output as JSON array):
[
  {{"action": "click", "x": 100, "y": 200}},
  {{"action": "double_click", "x": 100, "y": 200}},
  {{"action": "right_click", "x": 100, "y": 200}},
  {{"action": "type", "text": "hello world"}},
  {{"action": "key", "key": "enter"}},
  {{"action": "key", "key": "cmd+t"}},
  {{"action": "key", "key": "cmd+a"}},
  {{"action": "scroll", "x": 500, "y": 400, "direction": "down", "amount": 3}},
  {{"action": "move", "x": 100, "y": 200}},
  {{"action": "drag", "x1": 100, "y1": 100, "x2": 400, "y2": 400}},
  {{"action": "wait", "seconds": 1}},
  {{"action": "done", "message": "Task complete — here's what I did."}}
]

RULES:
- Output ONLY valid JSON. No markdown, no explanation outside the array.
- Look at the screenshot carefully. Identify exact pixel coordinates of UI elements.
- When clicking buttons or links, aim for the center of the element.
- After typing in a field, use {{"action":"key","key":"enter"}} if needed.
- Use "wait" after actions that trigger animations or page loads (1-2 seconds).
- Use "done" as the LAST action when the task is complete.
- If something unexpected is on screen, adapt — don't repeat failed actions.
- If you need to open an app, use Spotlight: cmd+space, type app name, enter.
- Screen coordinates: top-left is (0,0), bottom-right is ({SCREEN_W},{SCREEN_H}).
"""


def _screenshot_b64() -> str:
    img = pyautogui.screenshot()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


def _save_screenshot(label: str = "") -> str:
    path = os.path.expanduser(f"~/Desktop/jarvis_screen{'_' + label if label else ''}.png")
    img = pyautogui.screenshot()
    img.save(path)
    return path


def _execute_action(action: dict) -> str:
    t = action.get("action", "")
    if not t:
        return "No action specified."
    if t not in ALLOWED_ACTIONS:
        return f"Action '{t}' is not allowed."
    if t == "click":
        pyautogui.click(action["x"], action["y"])
    elif t == "double_click":
        pyautogui.doubleClick(action["x"], action["y"])
    elif t == "right_click":
        pyautogui.rightClick(action["x"], action["y"])
    elif t == "move":
        pyautogui.moveTo(action["x"], action["y"], duration=0.3)
    elif t == "type":
        pyautogui.write(str(action["text"]), interval=0.05)
    elif t == "key":
        key = action["key"]
        if key.lower() in DESTRUCTIVE_KEYS:
            confirm = input(f"\n[JARVIS] About to press '{key}'. This may be irreversible. Confirm? (yes/no): ").strip().lower()
            if confirm != "yes":
                return f"Action '{key}' cancelled by user."
        if "+" in key:
            parts = key.lower().split("+")
            pyautogui.hotkey(*parts[:-1], parts[-1])
        else:
            pyautogui.press(key)
    elif t == "scroll":
        pyautogui.moveTo(action.get("x", SCREEN_W//2), action.get("y", SCREEN_H//2))
        clicks = action.get("amount", 3)
        if action.get("direction") == "down":
            clicks = -clicks
        pyautogui.scroll(clicks)
    elif t == "drag":
        pyautogui.dragTo(action["x2"], action["y2"], duration=0.6,
                          startX=action["x1"], startY=action["y1"])
    elif t == "wait":
        time.sleep(action.get("seconds", 1))
    elif t == "done":
        return action.get("message", "Done.")
    else:
        return f"Unknown action: {t}"
    time.sleep(0.3)
    return ""


def _call_claude(task: str, screenshot_b64: str, history: list) -> list:
    """Send screenshot + task to Claude, get back list of actions."""
    import anthropic
    from brain.think import _get_auth_key, CLAUDE_MODELS

    key = _get_auth_key()
    client = anthropic.Anthropic(api_key=key)

    messages = history + [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": screenshot_b64,
                    },
                },
                {
                    "type": "text",
                    "text": f"TASK: {task}\n\nOutput the next batch of actions as a JSON array.",
                },
            ],
        }
    ]

    resp = client.messages.create(
        model=CLAUDE_MODELS["sonnet"],
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    raw = resp.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        actions = json.loads(raw)
        if isinstance(actions, dict):
            actions = [actions]
        return actions, raw
    except json.JSONDecodeError:
        # Try extracting JSON array from the text
        import re
        match = re.search(r'\[.*?\]', raw, re.DOTALL)
        if match:
            return json.loads(match.group()), raw
        print(f"  [parse error] Claude returned: {raw[:200]}")
        return [], raw


def run(task: str, max_steps: int = 20, verbose: bool = True) -> str:
    """
    Run the computer agent on a task.
    Returns a summary of what was done.
    """
    if verbose:
        print(f"\n[JARVIS Computer Agent]")
        print(f"Task: {task}")
        print(f"Screen: {SCREEN_W}x{SCREEN_H}")
        print(f"{'─'*50}")

    history = []
    step = 0
    final_message = ""

    while step < max_steps:
        step += 1
        if verbose:
            print(f"\nStep {step}: Taking screenshot...")

        shot = _screenshot_b64()
        _save_screenshot(f"step{step}")

        if verbose:
            print(f"Step {step}: Asking Claude...")

        try:
            actions, raw = _call_claude(task, shot, history)
        except Exception as e:
            print(f"  [Claude error] {e}")
            break

        if not actions:
            print("  [no actions returned — stopping]")
            break

        if verbose:
            print(f"Step {step}: {len(actions)} action(s):")

        step_done = False
        for action in actions:
            t = action.get("action", "")
            if verbose:
                print(f"  → {json.dumps(action)}")

            if t == "done":
                final_message = action.get("message", "Task complete.")
                step_done = True
                break

            result = _execute_action(action)
            if result:
                print(f"    {result}")

        # Add this exchange to history so Claude has context
        history.append({
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": shot}},
                {"type": "text", "text": f"TASK: {task}\n\nOutput the next batch of actions as a JSON array."},
            ]
        })
        history.append({"role": "assistant", "content": raw})

        # Keep history manageable
        if len(history) > 10:
            history = history[-10:]

        if step_done:
            break

        time.sleep(0.5)

    if verbose:
        print(f"\n{'─'*50}")
        print(f"Done in {step} step(s).")
        if final_message:
            print(f"Result: {final_message}")

    return final_message or f"Completed in {step} steps."
