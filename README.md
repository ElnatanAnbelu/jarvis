<div align="center">

```
   ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
   ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
   ██║███████║██████╔╝██║   ██║██║███████╗
██ ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
      Just A Rather Very Intelligent System
```

**v3.0 — Personal AI Operating System**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-Haiku%20%7C%20Sonnet%20%7C%20Opus-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-2.0%20Flash-4285F4?style=flat-square&logo=google&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-Llama%2070B-F55036?style=flat-square)
![Mistral](https://img.shields.io/badge/Mistral-Medium-FF6B35?style=flat-square)
![License](https://img.shields.io/badge/License-Private-red?style=flat-square)

*Not a chatbot. Not an assistant. An operating system for your life.*

</div>

---

## What is JARVIS?

JARVIS is a fully autonomous personal AI system — four distinct agents with different personalities, models, and specialties, all routing seamlessly behind the scenes based on what you need. It controls your Mac, sends messages, reads emails, executes real code, manages your businesses, briefs you every morning, and builds software alongside you.

Tony Stark didn't have a better AI.

---

## The Agent Team

| Agent | Personality | Model | Best For |
|-------|------------|-------|----------|
| **JARVIS** | Formal, composed, dry humor. Calls you "sir." | Claude Haiku / Sonnet / Opus | Tools, code, strategy, everything |
| **FRIDAY** | Direct, warm, slightly sarcastic. | Gemini 2.0 Flash | Quick answers, casual chat |
| **VERONICA** | Clinical, tactical, no-nonsense. | Groq Llama 3.3 70B | Risk analysis, breakdowns |
| **KAREN** | Warm, patient, mentoring energy. | Mistral Medium | Decisions, personal guidance |

All four agents share full conversation history. Call any agent by name at any point — they pick up exactly where the last left off.

---

## Routing Engine

Every message is scored 1–5 instantly with zero API calls. Pure local logic determines which agent and model handles it.

```
Score 1-3  →  Casual / quick / analytical    →  JARVIS   (Haiku)        ~200ms
Score 2    →  Quick answer / direct Q        →  FRIDAY   (Gemini Flash)  ~300ms
Score 3a   →  Risk / analysis / breakdown    →  VERONICA (Groq 70B)     ~400ms
Score 3b   →  Decision / personal / advice   →  KAREN    (Mistral)      ~400ms
Score 4    →  Tools / coding / research      →  JARVIS   (Sonnet)       ~800ms
Score 5    →  Deep strategy / empire         →  JARVIS   (Opus)         ~2s
```

Any message containing a tool keyword (`send`, `email`, `search`, `build`, `run`, `screenshot`, …) is forced to Score 4 → JARVIS automatically.

---

## Tool Arsenal

JARVIS has **100+ tools** across every domain:

### Computer Control
- Full Mac control — mouse, keyboard, scroll, clicks, drag
- Screenshot + visual self-verification
- App launching and window management
- AppleScript execution

### Communication
- Send iMessages and WhatsApp messages
- Read and send emails (Gmail)
- Telegram bot integration

### Code & Development
- Execute Python, JavaScript, Bash in real sandboxes (no hallucinated output)
- Scaffold full web projects from scratch
- Git operations — commit, push, branch, status
- Open built projects in browser and autonomously verify the output

### Research & Intelligence
- Multi-source web search and aggregation
- Full article reading and summarization
- News feed with custom filtering
- Market intelligence and competitor research

### Personal Life OS
- Google Calendar — read, create, update events
- Morning briefing with weather, news, and daily priorities
- Goal tracking and milestone management
- Focus mode with Pomodoro timer

### Business OS
- Business analytics and KPI reporting
- Marketing copy generation
- Chart and data visualization
- Analyst-grade financial breakdowns

### Voice
- Voice cloning via Chatterbox (local, fully offline)
- Fallback chain: Kokoro TTS → ElevenLabs → edge-tts
- Wake word detection
- Real-time voice input with streaming response

---

## Interfaces

JARVIS runs three ways simultaneously:

### 1. HUD Desktop App
A `pywebview` native desktop window with a custom cyan-on-dark heads-up display. Animated JARVIS iris logo, spring-physics panel animations, per-agent color coding, word-by-word text reveal. Runs at `localhost:8080` inside a borderless native Mac window.

### 2. Terminal Mode
Full ANSI-colored terminal interface with per-agent color coding. Works standalone — no browser, no HUD, pure keyboard.

```
cyan    →  JARVIS
purple  →  FRIDAY
lime    →  VERONICA
yellow  →  KAREN
```

### 3. Telegram Bot
Full JARVIS access from your phone via Telegram. Same routing, same agents, same tools — from anywhere in the world.

---

## Architecture

```
jarvis/
├── jarvis.py              # Terminal entry point
├── jarvis_ctl.py          # Side control terminal
├── start.sh               # One-command full startup
├── voice_daemon.py        # Background voice pipeline
│
├── app/                   # HUD desktop app
│   ├── hud.html           # Frontend (pywebview)
│   └── main.py            # Native window wrapper
│
├── brain/                 # Intelligence layer
│   ├── router.py          # Score-based routing engine (no API calls)
│   ├── think.py           # Claude agent — main JARVIS logic
│   ├── gemini.py          # FRIDAY (Gemini 2.0 Flash)
│   ├── tools.py           # Tool dispatcher (100+ tools)
│   ├── team.py            # Agent team coordination
│   ├── briefing.py        # Morning briefing generator
│   ├── proactive.py       # Proactive suggestions engine
│   ├── reader.py          # Document/article reader
│   └── research.py        # Deep research pipeline
│
├── control/               # Tool implementations
│   ├── computer.py        # Mac control (mouse, keyboard, scroll)
│   ├── screen.py          # Screenshot + vision analysis
│   ├── browser.py         # Browser automation
│   ├── email.py           # Gmail integration
│   ├── whatsapp.py        # WhatsApp Web automation
│   ├── calendar.py        # Google Calendar
│   ├── code_executor.py   # Sandboxed code execution
│   ├── scaffold.py        # Full project scaffolding
│   ├── git_ops.py         # Git operations
│   ├── life_os.py         # Personal life tools
│   ├── business_tools.py  # Business OS tools
│   ├── charts.py          # Data visualization
│   ├── reports.py         # Report generation
│   ├── search.py          # Web search + aggregation
│   └── mac.py             # macOS system controls
│
├── memory/                # Persistence layer
│   ├── memory.py          # Conversation history (SQLite)
│   ├── goals.py           # Goal and milestone tracking
│   ├── life.py            # Life data store
│   ├── business.py        # Business data store
│   └── wiki.py            # Personal knowledge base
│
├── voice/                 # Voice pipeline
│   ├── listen.py          # Wake word + speech-to-text
│   ├── speak.py           # TTS routing and fallback chain
│   ├── kokoro_daemon.py   # Kokoro TTS background server
│   └── clone_daemon.py    # Chatterbox voice clone server
│
├── ui/                    # Web server
│   └── server.py          # Flask app + SSE streaming
│
└── scripts/               # Automation
    └── morning.py         # Morning briefing automation
```

---

## Quick Start

### Prerequisites

- macOS (required for screen control and AppleScript)
- Python 3.11+
- API keys: Anthropic, Google Gemini, Groq, Mistral

### Setup

```bash
# 1. Clone
git clone git@github.com:ElnatanAnbelu/jarvis.git
cd jarvis

# 2. Virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Dependencies
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Edit .env and add your API keys

# 5. Launch
./start.sh
```

See [`docs/SETUP.md`](docs/SETUP.md) for the full guide including voice cloning, Telegram, and Google Calendar.

---

## Environment Variables

```bash
# Core AI — required
ANTHROPIC_API_KEY=        # JARVIS (Claude)
GOOGLE_API_KEY=           # FRIDAY (Gemini)
GROQ_API_KEY=             # VERONICA (Groq Llama)
MISTRAL_API_KEY=          # KAREN (Mistral)

# Voice — optional
ELEVENLABS_API_KEY=       # Voice fallback

# Communication — optional
GMAIL_ADDRESS=            # Gmail sender
TELEGRAM_BOT_TOKEN=       # Telegram interface

# Google Services — optional
GOOGLE_CALENDAR_ID=       # Calendar integration
```

> **Security note:** `.env`, all credential files, personal databases (`memory/*.db`), and WhatsApp session data are excluded from this repository. Never commit them.

---

## Documentation

| Doc | Description |
|-----|-------------|
| [`docs/SETUP.md`](docs/SETUP.md) | Full installation and configuration guide |
| [`docs/AGENTS.md`](docs/AGENTS.md) | Agent personalities, routing logic, and capabilities |
| [`docs/TOOLS.md`](docs/TOOLS.md) | Complete tool reference with examples |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design and component breakdown |

---

<div align="center">

Built by **Elnatan Anbelu** — [Nexel Intelligence](https://github.com/ElnatanAnbelu)

*JARVIS is a private system. This repository is not open for public use or contribution.*

</div>
