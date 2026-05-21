# JARVIS — Setup Guide

Full installation and configuration from zero to running.

---

## Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| macOS | 12+ | Required for screen control & AppleScript |
| Python | 3.11+ | 3.11 recommended |
| pip | latest | `pip install --upgrade pip` |

---

## Step 1 — Clone the Repository

```bash
git clone git@github.com:ElnatanAnbelu/jarvis.git
cd jarvis
```

---

## Step 2 — Virtual Environment

```bash
python3.11 -m venv venv
source venv/bin/activate
```

---

## Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Step 4 — Environment Variables

Copy the example file and fill in your keys:

```bash
cp .env.example .env
```

Open `.env` and add your API keys:

```bash
# ─── Core AI (required) ──────────────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...          # JARVIS — get from console.anthropic.com
GOOGLE_API_KEY=AIza...                # FRIDAY — get from aistudio.google.com
GROQ_API_KEY=gsk_...                  # VERONICA — get from console.groq.com
MISTRAL_API_KEY=...                   # KAREN — get from console.mistral.ai

# ─── Voice (optional) ────────────────────────────────────────────────────────
ELEVENLABS_API_KEY=...                # Fallback TTS — elevenlabs.io

# ─── Communication (optional) ────────────────────────────────────────────────
GMAIL_ADDRESS=you@gmail.com           # Gmail sender address
TELEGRAM_BOT_TOKEN=...               # Create via @BotFather on Telegram

# ─── Google Services (optional) ──────────────────────────────────────────────
GOOGLE_CALENDAR_ID=primary            # Your calendar ID
```

---

## Step 5 — Launch

```bash
./start.sh
```

This will:
1. Kill any existing JARVIS server on port 8080
2. Start the Flask web server in the background
3. Open the HUD at `http://localhost:8080`
4. Open a side control terminal with the voice daemon

---

## Optional: Voice Cloning

JARVIS uses Chatterbox for local voice cloning. To set up:

1. Place reference audio files in `voice/`:
   - `voice/jarvis_ref.wav` — Paul Bettany voice sample (10–30s clean speech)
   - `voice/friday_ref.wav` — Kerry Condon voice sample
   - `voice/karen_ref.wav` — Jennifer Connelly voice sample

2. Start the voice daemon:
```bash
source venv/bin/activate
python voice_daemon.py
```

Voice fallback chain: Chatterbox clone → Kokoro preset → ElevenLabs → edge-tts

---

## Optional: Google Calendar

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable Google Calendar API
3. Create OAuth 2.0 credentials → Download `credentials.json`
4. Place `google_credentials.json` in the project root
5. Run once to authorize: `python control/calendar.py`

---

## Optional: Telegram Bot

1. Message `@BotFather` on Telegram → `/newbot`
2. Copy the bot token into `TELEGRAM_BOT_TOKEN` in `.env`
3. Start the bot: `python telegram_bot.py`

---

## Optional: Gmail

1. Enable Gmail API in Google Cloud Console
2. Add `GMAIL_ADDRESS` to `.env`
3. Use the same `google_credentials.json` from the Calendar setup

---

## Running Without the HUD

Terminal-only mode (no browser required):

```bash
source venv/bin/activate
python jarvis.py
```

---

## Troubleshooting

**Port 8080 already in use:**
```bash
lsof -ti:8080 | xargs kill -9
```

**Voice not working:**
- Check that `voice_daemon.py` is running
- Verify reference audio files exist in `voice/`
- ElevenLabs key in `.env` as fallback

**Token expired mid-session:**
- JARVIS automatically refreshes OAuth tokens on 401 errors
- If it persists, re-run the auth flow: `claude setup-token`
