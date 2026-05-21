# JARVIS — Complete Testing Guide

Run all tests from the project root:
```bash
cd ~/jarvis && source venv/bin/activate
```

---

## 1. ENVIRONMENT CHECK

Before testing anything, verify setup:

```bash
python -c "import anthropic, pyautogui, flask, whisper, elevenlabs, fitz; print('All deps OK')"
echo "ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:0:10}..."
echo "ELEVENLABS_API_KEY: ${ELEVENLABS_API_KEY:0:10}..."
```

Expected: `All deps OK` and partial keys printed.

---

## 2. BRAIN / AI ROUTING

```bash
python brain/router.py
```

| Input | Expected model |
|---|---|
| "What time is it?" | VERONICA (Gemini) |
| "Help me build the login page for Addis Market" | JARVIS (Claude Sonnet) |
| "Should I expand to Ethiopia or Middle East first?" | JARVIS (Claude Opus) |
| "Tell me a joke" | VERONICA |
| "Search the web for Ethiopian fintech startups" | JARVIS:WEB |

---

## 3. VOICE OUTPUT (ElevenLabs TTS)

```bash
python voice/speak.py
```

Expected: Callum's voice says "Systems online, sir." through your speakers.

---

## 4. VOICE INPUT (Whisper STT)

```bash
python voice/listen.py
```

Speak a sentence when prompted. Expected: your words printed to terminal.

---

## 5. SYSTEM CONTROL (Mac commands)

```bash
python -c "
from control.executor import execute
print(execute('battery'))
print(execute('wifi'))
print(execute('screenshot'))
"
```

Expected: battery %, wifi name, screenshot path on Desktop.

---

## 6. WEB SEARCH

```bash
python -c "
from control.search import web_search, news_search
print(web_search('Addis Market Ethiopia e-commerce')[:300])
print('---')
print(news_search('AI agents 2025')[:300])
"
```

Expected: real search results printed with sources.

---

## 7. SCREEN AWARENESS

```bash
python -c "
from control.screen import analyze_screen, get_active_window
print('Active app:', get_active_window())
print(analyze_screen()[:200])
"
```

Expected: current app name + OCR text from your screen.

---

## 8. DOCUMENT READER

```bash
# Test with a text file
echo "Addis Market: African marketplace. Launch Q3 2025. Goal: 1M users." > /tmp/test.txt
python -c "
from control.docs import read_text, summarize_document
print(read_text('/tmp/test.txt'))
"

# Test PDF (if you have one)
# python -c "from control.docs import read_pdf; print(read_pdf('~/Desktop/something.pdf')[:500])"
```

---

## 9. MEMORY SYSTEM

```bash
python -c "
from memory.memory import save_message, format_history_for_prompt
save_message('user', 'Testing memory system')
save_message('jarvis', 'Memory confirmed, sir.')
print(format_history_for_prompt())
"
```

Expected: both messages printed back.

---

## 10. COMPUTER USE AGENT (primitives)

```bash
python -c "
from control.computer import screenshot, get_screen_size, left_click, type_text
w, h = get_screen_size()
print(f'Screen: {w}x{h}')
b64 = screenshot()
print(f'Screenshot: {len(b64)} chars base64')
"
```

Expected: screen dimensions and a long base64 string.

> **Do NOT test click/type_text here** — it will interact with your live screen.

---

## 11. COMPUTER USE AGENT (full loop — live test)

**Prerequisites:** JARVIS web server must be running first (see Section 12).

Open a second terminal:
```bash
cd ~/jarvis && source venv/bin/activate && python jarvis_ctl.py
```

Then type these commands one at a time and watch your screen:

| Command | What JARVIS should do |
|---|---|
| `open TextEdit` | TextEdit opens |
| `open safari and go to google.com` | Safari opens, navigates to Google |
| `type hello world into the search bar` | Types in Google search |
| `press escape` | Closes search / cancels |
| `stop` | Aborts any running task |

**Emergency stop:** Move mouse to top-left corner of screen.

---

## 12. WEB SERVER + HOLOGRAPHIC UI

Start the server:
```bash
python ui/server.py
```

Open in browser: **http://localhost:8080**

Test checklist:
- [ ] Holographic sphere appears and animates
- [ ] Click the microphone button — sphere changes state
- [ ] Say "hello JARVIS" — voice transcribes, JARVIS responds in text
- [ ] Callum's voice speaks the response through speakers
- [ ] Say "what's on my screen" — JARVIS describes the screen
- [ ] Say "search the web for Addis Ababa" — JARVIS returns search results

---

## 13. SIDE CONTROL TERMINAL

While server is running (Section 12), open a new terminal window:
```bash
cd ~/jarvis && source venv/bin/activate && python jarvis_ctl.py
```

Test:
```
JARVIS ctl > open textedit
JARVIS ctl > stop
JARVIS ctl > exit
```

Expected:
- TextEdit opens while you watch
- `stop` sends abort and JARVIS halts
- `exit` closes the terminal cleanly

---

## 14. MORNING BRIEFING

```bash
python scripts/morning.py
```

Expected: JARVIS speaks a morning briefing with your goals, tasks, and habits summary.

---

## 15. FULL END-TO-END VOICE FLOW

1. Start server: `python ui/server.py`
2. Open http://localhost:8080
3. Click mic, say: *"Open Safari and navigate to addismarket.com"*
4. Watch: Safari opens, navigates
5. JARVIS speaks back what happened

---

## QUICK SMOKE TEST (all at once)

Run this to check every module imports without errors:

```bash
python -c "
import sys; sys.path.insert(0, '.')
from brain.router import route
from brain.think import think
from brain.gemini import think_veronica
from control.executor import execute, is_control_command
from control.computer import get_screen_size, screenshot
from control.agent import get_agent
from control.search import web_search, news_search
from control.screen import analyze_screen, get_active_window
from control.docs import read_text, summarize_document
from memory.memory import save_message, format_history_for_prompt
from voice.speak import speak
print('All modules imported successfully.')
print('Screen size:', get_screen_size())
"
```

Expected: `All modules imported successfully.` + your screen resolution.

---

## COMMON ISSUES

| Problem | Fix |
|---|---|
| `ANTHROPIC_API_KEY not set` | `export ANTHROPIC_API_KEY=sk-ant-...` |
| `ELEVENLABS_API_KEY not set` | `export ELEVENLABS_API_KEY=...` |
| Port 8080 in use | `lsof -ti:8080 \| xargs kill` |
| PyAutoGUI fails | System Preferences → Privacy → Accessibility → add Terminal |
| Tesseract not found | `brew install tesseract` |
| Agent stuck | Move mouse to top-left corner (PyAutoGUI failsafe) |
