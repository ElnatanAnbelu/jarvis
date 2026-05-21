# JARVIS — Architecture

How the system works under the hood.

---

## Overview

```
User Input (voice / text / Telegram)
         │
         ▼
   ┌─────────────┐
   │   Router    │  Score 1–5, zero API calls, pure local logic
   └──────┬──────┘
          │
   ┌──────▼──────────────────────────────────────┐
   │              Agent Dispatch                  │
   │  JARVIS(Claude) / FRIDAY(Gemini) /           │
   │  VERONICA(Groq) / KAREN(Mistral)             │
   └──────┬──────────────────────────────────────┘
          │
   ┌──────▼──────┐      ┌──────────────┐
   │  Tool Call? ├─Yes─▶│ Tool Execute │
   └──────┬──────┘      └──────┬───────┘
          │No                  │
          └────────┬───────────┘
                   │
   ┌───────────────▼──────────────┐
   │         Memory Layer          │
   │  Save to DB, load history     │
   └───────────────┬──────────────┘
                   │
   ┌───────────────▼──────────────┐
   │          Response             │
   │  Text + Voice (TTS)           │
   │  HUD / Terminal / Telegram    │
   └──────────────────────────────┘
```

---

## Routing Engine (`brain/router.py`)

The routing engine scores every message locally in milliseconds without touching any API.

**Scoring factors:**
- Message length and complexity
- Presence of tool keywords (forces Score 4)
- Presence of agent names (forces that agent)
- Question type (factual vs. analytical vs. personal)

**Score 3 split:** A secondary local classifier (`classify_score3`) reads the message intent and routes to VERONICA (analytical) or KAREN (guidance).

**Streaming support:** The router has both blocking (`route()`) and streaming (`route_stream()`) variants. The HUD uses blocking fetch; browser clients use SSE streaming.

---

## JARVIS Core (`brain/think.py`)

The main Claude agent. Runs on Haiku, Sonnet, or Opus depending on score.

**Message construction:**
1. Load last 15 messages from SQLite via `build_messages_for_prompt()`
2. Prepend system prompt with personality, tool list, and behavioral rules
3. Call Claude API with tool use enabled
4. If Claude calls a tool → dispatch via `execute_tool()` → inject result → continue
5. Save final response to memory DB

**Tool loop:** JARVIS can chain multiple tool calls in a single turn — e.g., write code → execute it → take screenshot → report what it sees.

**Token handling:** On 401 auth errors, automatically calls `_refresh_token()` and retries once silently.

---

## Tool System (`brain/tools.py`)

A single dispatcher function routes tool names to implementations:

```python
execute_tool(name: str, args: dict) -> str
```

Tools are implemented in the `control/` directory. Each tool returns a string result that is injected back into the Claude conversation as a tool result message.

**Flexible argument handling:** Tools accept multiple argument name variants — e.g., `open_in_browser` accepts `target`, `url`, or `path`.

---

## Memory (`memory/memory.py`)

SQLite-backed conversation history. Every message from every agent and user is saved with:
- Timestamp
- Agent name
- Role (user/assistant)
- Content

`build_messages_for_prompt()` loads the last N messages, maps all agent roles to `"assistant"` (so the model sees a consistent user/assistant alternation), merges consecutive same-role turns, and ensures the list starts with `"user"`.

Separate databases for:
- `memory/jarvis.db` — conversation history
- `memory/goals.db` — goal tracking
- `memory/life.db` — life data
- `memory/business.db` — business data

---

## Voice Pipeline

```
Microphone → listen.py (Whisper STT) → router → agent response → speak.py → TTS daemon
```

**TTS priority:**
1. Chatterbox clone daemon (`voice/clone_daemon.py`) — best quality, fully offline
2. Kokoro TTS daemon (`voice/kokoro_daemon.py`) — fast, offline fallback
3. ElevenLabs API — cloud fallback
4. edge-tts — last resort, always available

Each agent has a reference audio file. Chatterbox clones the voice from the reference audio in real time.

---

## HUD (`app/hud.html` + `app/main.py`)

The desktop app is a `pywebview` window rendering `hud.html`.

**Communication:**
- HUD → Flask server: blocking POST to `/api/chat`
- Flask server → HUD: JSON response with text, agent name, and image data
- Browser clients (non-pywebview): SSE streaming via `/api/stream`

**Note:** WKWebView (the macOS WebKit engine used by pywebview) does not support `ReadableStream` / `getReader()`. The HUD uses a blocking fetch with word-by-word text reveal animation instead of true streaming.

**HUD image display (`[SHOW:]` tag):**
When a response contains `[SHOW: query]`, the HUD fetches a real image from the web and renders it inline. This tag must only appear with real web image searches — never used to simulate showing something.

---

## Web Server (`ui/server.py`)

Flask application with these endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve the HUD HTML |
| `/api/chat` | POST | Blocking chat endpoint (pywebview) |
| `/api/stream` | POST | SSE streaming endpoint (browser) |
| `/api/tts` | POST | Text-to-speech synthesis |
| `/api/briefing` | GET | Morning briefing data |

---

## Security

- All API keys in `.env` — never committed
- Personal databases in `memory/*.db` — gitignored
- WhatsApp session in `whatsapp/.wwebjs_auth/` — gitignored
- Google credentials in `google_credentials.json` — gitignored
- Voice model files (`.onnx`, `.dylib`) — gitignored (too large for GitHub)
