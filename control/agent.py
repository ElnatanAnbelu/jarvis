"""
JARVIS Computer Use Agent — 100% free, no extra API keys.
Uses: claude CLI (already auth'd) for planning + AppleScript/PyAutoGUI for execution.

Flow per step:
  1. Get current screen state via Accessibility API (app name, window title, URL)
  2. Ask claude CLI: given the task and screen state, what is the next action?
  3. Execute that action via AppleScript or PyAutoGUI
  4. Repeat until done
"""
import sys
import os
import re
import json
import time
import subprocess
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from control.computer import (
    left_click, double_click, right_click,
    mouse_move, type_text, press_key, scroll, get_screen_size
)

MAX_STEPS = 25

PLANNER_PROMPT = """You are JARVIS controlling a Mac for Elnatan Anbelu.

Current screen state:
{state}

Task: {task}

Steps taken so far:
{history}

What is the single next action to take? Respond with JSON only:
{{
  "action": "applescript" | "click" | "type" | "key" | "scroll" | "wait" | "done",
  "applescript": "<osascript code — only if action is applescript>",
  "x": <int — only for click/scroll>,
  "y": <int — only for click/scroll>,
  "text": "<string — only for type or key>",
  "direction": "up" | "down" — only for scroll,
  "summary": "<what you are doing and why>"
}}

Rules:
- Prefer applescript for opening apps, navigating browsers, typing URLs — it is more reliable than clicking pixels
- Use click/type/key for things AppleScript can't reach
- For browser navigation: use applescript to set the URL directly
- For keyboard shortcuts: use key action with e.g. "cmd+t", "cmd+l", "return"
- When task is done, use action "done"
- Respond with JSON only, no markdown"""


def _get_screen_state() -> str:
    """Get text description of current screen using Accessibility API."""
    parts = []
    w, h = get_screen_size()
    parts.append(f"Screen: {w}x{h}")

    # Active app
    try:
        r = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of first application process whose frontmost is true'],
            capture_output=True, text=True, timeout=5)
        app = r.stdout.strip()
        if app:
            parts.append(f"Active app: {app}")
    except Exception:
        pass

    # Safari URL
    try:
        r = subprocess.run(
            ["osascript", "-e",
             'tell application "Safari" to if (count of windows) > 0 then return URL of current tab of front window'],
            capture_output=True, text=True, timeout=5)
        url = r.stdout.strip()
        if url:
            parts.append(f"Safari URL: {url}")
    except Exception:
        pass

    # Chrome URL
    try:
        r = subprocess.run(
            ["osascript", "-e",
             'tell application "Google Chrome" to return URL of active tab of front window'],
            capture_output=True, text=True, timeout=5)
        url = r.stdout.strip()
        if url and not url.startswith("execution error"):
            parts.append(f"Chrome URL: {url}")
    except Exception:
        pass

    return " | ".join(parts) if parts else "No screen state available"


def _plan_next_action(task: str, history: list, state: str) -> dict:
    """Ask claude CLI what the next action should be."""
    history_text = "\n".join(f"  {i+1}. {h}" for i, h in enumerate(history)) if history else "  None yet"
    prompt = PLANNER_PROMPT.format(task=task, state=state, history=history_text)

    result = subprocess.run(
        ["claude", "-p", prompt, "--model", "claude-haiku-4-5-20251001"],
        capture_output=True, text=True, timeout=30
    )
    raw = result.stdout.strip()

    # Strip markdown fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except Exception:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return {"action": "done", "summary": f"Could not parse plan: {raw[:100]}"}


def _run_applescript(code: str) -> str:
    """Execute AppleScript and return output."""
    try:
        r = subprocess.run(["osascript", "-e", code], capture_output=True, text=True, timeout=15)
        return r.stdout.strip() or r.stderr.strip()
    except Exception as e:
        return str(e)


class ComputerUseAgent:
    def __init__(self):
        self._abort = False
        self._abort_lock = threading.Lock()

    def abort(self):
        with self._abort_lock:
            self._abort = True

    def _should_abort(self):
        with self._abort_lock:
            if self._abort:
                return True
        # Honor the global kill-switch: panic() and pause set autonomy.is_paused.
        # This is a second action channel that drives the real mouse/keyboard/
        # AppleScript, so it MUST stop instantly when the user halts everything.
        try:
            from brain import autonomy
            return autonomy.is_paused()
        except Exception:
            return False

    def run(self, task: str, on_progress=None, source: str = "user") -> str:
        # Refuse to even start while paused/panicked. (away-mode + red-list
        # confirmation are enforced upstream at the gate, since control_screen
        # is risk="red"; this is the kill-switch backstop for the direct path.)
        try:
            from brain import autonomy
            if autonomy.is_paused():
                return "🚫 Computer control is paused (panic/pause active). Resume first."
        except Exception:
            pass

        self._abort = False
        history = []

        for step in range(MAX_STEPS):
            if self._should_abort():
                return "Task aborted (halted by pause/panic or stop)."

            state = _get_screen_state()
            action_obj = _plan_next_action(task, history, state)

            action = action_obj.get("action", "done")
            summary = action_obj.get("summary", action)

            if on_progress:
                on_progress(step + 1, summary)
            history.append(summary)

            if action == "done":
                return summary

            try:
                if action == "applescript":
                    code = action_obj.get("applescript", "")
                    if code:
                        _run_applescript(code)

                elif action == "click":
                    x, y = int(action_obj.get("x", 0)), int(action_obj.get("y", 0))
                    left_click(x, y)

                elif action == "double_click":
                    x, y = int(action_obj.get("x", 0)), int(action_obj.get("y", 0))
                    double_click(x, y)

                elif action == "type":
                    type_text(action_obj.get("text", ""))

                elif action == "key":
                    press_key(action_obj.get("text", ""))

                elif action == "scroll":
                    x, y = int(action_obj.get("x", 0)), int(action_obj.get("y", 0))
                    scroll(x, y, action_obj.get("direction", "down"))

                elif action == "wait":
                    time.sleep(1.5)

            except Exception as e:
                history.append(f"Error: {e}")

            time.sleep(0.8)

        return "Reached maximum steps."


_agent = ComputerUseAgent()


def get_agent() -> ComputerUseAgent:
    return _agent
