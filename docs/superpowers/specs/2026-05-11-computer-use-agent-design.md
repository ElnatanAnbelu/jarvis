# JARVIS Computer Use Agent — Design Spec
Date: 2026-05-11

## Overview

JARVIS gains full screen control: Claude's computer use API drives PyAutoGUI to click, type, scroll, and interact with any Mac app. Orders come from voice, the side terminal, or the holographic web UI. JARVIS executes fully autonomously.

---

## Architecture

```
User input (voice / side terminal / web UI)
        ↓
   JARVIS router — detects agent task
        ↓
   ComputerUseAgent.run(task)
        ↓
   loop:
     screenshot() → base64 PNG
     Claude claude-sonnet-4-6 (computer-use-2024-10-22 beta)
     → tool_use actions (click / type / key / scroll)
     → PyAutoGUI executes action
     → 0.5s delay
   until: Claude returns text (done) or max_steps=30 reached
        ↓
   Result spoken via ElevenLabs
   Progress streamed via SocketIO to web UI
```

---

## New Files

### `control/computer.py`
Low-level Mac control primitives using PyAutoGUI:
- `screenshot() → str` — takes screenshot, returns base64 PNG
- `left_click(x, y)`
- `double_click(x, y)`
- `right_click(x, y)`
- `type_text(text)`
- `press_key(key)` — supports modifiers e.g. "cmd+t"
- `scroll(x, y, direction, amount)`
- `get_screen_size() → (w, h)`

### `control/agent.py`
Agentic loop using Anthropic SDK with computer use beta:
- `ComputerUseAgent` class
- `run(task: str, on_progress: callable) → str` — runs loop, calls on_progress(msg) on each step
- Uses `claude-sonnet-4-6` with `anthropic-beta: computer-use-2024-10-22`
- Computer tool: `{"type": "computer_20241022", "name": "computer", "display_width_px": screen_w, "display_height_px": screen_h, "display_number": 1}`
- Max 30 iterations; aborts cleanly on Escape key or "stop" voice command
- Each action has 0.5s post-delay for watchability

### `jarvis_ctl.py` (project root)
Side terminal controller:
- Runs in a separate terminal window
- Reads commands from stdin in a loop
- Calls the Flask `/api/agent` endpoint via HTTP POST
- Streams progress back as it arrives via SocketIO
- Shows: `JARVIS ctl > ` prompt, action updates, done message

### `ui/server.py` — new endpoint
`POST /api/agent`:
- Accepts `{"task": "..."}` JSON
- Runs `ComputerUseAgent.run()` in a background thread
- Emits `agent_progress` events via SocketIO: `{"step": n, "action": "...", "done": false}`
- Emits final `agent_done` event: `{"result": "...", "done": true}`
- Triggers ElevenLabs TTS for the final result

---

## Router Integration (`brain/router.py`)

New detection before existing control check:

```python
AGENT_KEYWORDS = [
    "go to and", "open and", "navigate to", "click on", "fill in",
    "find on my screen", "type into", "search for on", "log into",
    "compose", "submit", "drag", "select from", "download from",
]
```

If matched → route to `ComputerUseAgent` instead of brain or executor.

---

## Input Channels

| Channel | How it works |
|---|---|
| Side terminal (`jarvis_ctl.py`) | Separate window, type commands, HTTP → agent endpoint |
| Voice (web UI) | Existing Web Speech API → detect agent keywords → agent endpoint |
| Web UI text | Existing chat input → agent endpoint if agent keywords detected |

---

## Safety

- Max 30 steps per task — hard limit
- 0.5s delay between actions — watchable, interruptible
- Escape key aborts current agent run
- "stop" or "cancel" as voice/text command calls `agent.abort()`
- No file deletion or system-level destructive actions without "are you sure" in the task

---

## Dependencies

- `anthropic` SDK (already available via `claude` CLI, need Python package)
- `pyautogui` — mouse/keyboard control
- `Pillow` — already installed (screenshots)

---

## Success Criteria

- "Open Spotify and play something chill" → Spotify opens, music plays, JARVIS reports back
- "Go to gmail.com and read my latest email" → browser opens, Gmail loads, JARVIS reads subject/sender
- "Open Notes and write down: buy groceries tomorrow" → Notes opens, text typed, JARVIS confirms
- Agent handles unexpected UI states gracefully (retries or reports what it sees)
- Escape key reliably aborts mid-task
