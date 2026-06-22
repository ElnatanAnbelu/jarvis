# Alfred — Owner Setup (the things only you can do)

Everything in the finish plan that *code* could do is done. These steps need **you** —
credentials, enrollment, and OS permissions. None of this touches the UI.

## 1. Identity (so Alfred only acts for you)
- **PIN** — set it: `./venv/bin/python -c "from security import identity; identity.set_pin('YOUR_PIN')"`
- **Face** — enroll from the app (camera) or `identity.enroll_face()`. Falls back to PIN if dlib isn't installed.
- **Voice (optional)** — `identity.enroll_voice()` records a reference sample; verification now does a real
  speaker-embedding match (resemblyzer). Without it, voice-verify cleanly returns False and PIN/face cover you.

## 2. Comms credentials (in `.env`)
- **Gmail** — `GMAIL_ADDRESS` + a Google **app password** (or OAuth). Enables email triage/send.
- **Telegram** — `TELEGRAM_BOT_TOKEN` + `OWNER_CHAT_ID` (your chat id). The bot is **owner-locked**: it ignores
  everyone but `OWNER_CHAT_ID`. This is the away-channel for approvals + digests.
- **WhatsApp** — `WHATSAPP_TOKEN` + the local bridge. Until set, `read_whatsapp` returns a clear
  "not connected" note (no fake data); send/read light up once the token + bridge exist.

## 3. macOS permissions
- **Microphone + Camera** — already granted to the bundled app (`dist/JARVIS.app`). **Always launch via the
  bundle** (`open dist/JARVIS.app`), never `python app/main.py` — bare Python has no camera/mic entitlement.
- **Full Disk Access** — grant it to the app so `read_imessages` can read `~/Library/Messages/chat.db`
  (System Settings → Privacy & Security → Full Disk Access). Without it, iMessage-read returns a clear hint.

## 4. Seed who matters (contacts)
- Add your **VIP / family / blocked** contacts via `memory/people.py` so the safety gate treats them right
  (VIP/family/blocked → always confirm). Example:
  `./venv/bin/python -c "from memory import people; people.add_person('Mom', relationship='family', vip=True)"`

## 5. Vision model (P1)
- Alfred sees offline via a local VLM. Pull it once: `ollama pull llava:7b` (downloading now).
  (Tested moondream — it returns gibberish on this Ollama build, so stick with `llava:7b`; your 32 GB / M5
  handles it fine, and it only loads into RAM when you actually ask Alfred to see something.)

## 6. The brain (P2) — how it grows now
- When you tell Alfred a real fact, it **checks the Second Brain and registers it if missing** (deduped, never
  repeated). Low-risk facts auto-write; **family / money / health are proposed for your review** (in
  `~/Desktop/SecondBrain/_JARVIS/Proposals/`). Review those occasionally — that's where sensitive learnings wait
  for your yes. Nothing is ever invented or test-seeded.

## Notes
- Fully local by default; cloud is opt-in only (`JARVIS_ALLOW_CLOUD_BRAIN=1`).
- The UI (`app/alfred.html`) is frozen and snapshotted at `app/alfred.html.golden` — the protected restore point.
