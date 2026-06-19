# JARVIS — iMessage Presence (design spec)

**Date:** 2026-06-19
**Status:** approved (brainstorming) → ready for implementation plan
**Sub-project:** A of the "MCU JARVIS" roadmap (see Context)

---

## Context — the bigger goal

The owner (Elnatan) wants the full **MCU JARVIS**: it runs his life, is always present,
does hard multi-step jobs, and truly knows him — fully **local, free, private** on his Mac
(the Mac stays awake), and **very forward** in behavior (anticipates, gets ahead of him).

That vision is ~5 independent sub-projects, each its own spec → plan → ship:

| # | Sub-project | Delivers |
|---|---|---|
| **A** | **iMessage presence** (THIS spec) | Always-there phone reach: text JARVIS, it acts, you approve over iMessage |
| B | Go-live activation | Runs real accounts; flip a domain to auto (needs creds + mic test) |
| C | Proactivity engine | "Very forward" — watches his world, surfaces/acts ahead of him |
| D | Real-web execution | Actually does things on real sites (order/book/pay) — highest risk, last |
| E | Knows-me synthesis | Continuously learns him into the Second Brain |

This spec covers **A only**. B–E are recorded for sequencing, not designed here.

---

## A — iMessage Presence

### Goal
Replace Telegram with **iMessage** as JARVIS's away-channel, so the owner reaches and
commands JARVIS from his phone, fully locally (macOS sends/reads iMessage natively; no
cloud, no mobile app, no bridge service). JARVIS becomes "present in his pocket."

### Success criteria
1. Owner texts JARVIS from his phone → JARVIS routes it to the brain and **replies over iMessage**.
2. Owner issues control commands over iMessage (`approve N`, `pause`, `panic`, `status`, …) and they work, **owner-locked** to his handle.
3. A red-list action (money/send/irreversible) triggered while away → JARVIS **texts the owner for approval** and does not execute until approved.
4. `panic`/`pause` over iMessage halts everything instantly.
5. JARVIS can reply with a **voice note** (cloned voice) and **send attachments** (charts/reports/screenshots).
6. JARVIS **initiates** iMessages unprompted (urgent pings + digests).
7. JARVIS **triages all inbound iMessages** (not just the owner's): classify, summarize, draft, escalate — never auto-sending to a non-owner without the red-list gate.
8. Telegram is retired (code remains, dormant). Fully local; the existing safety model is unchanged.

### Non-negotiable invariants (inherited, must hold)
- Every tool call routes through `brain/autonomy.py:gate` (execute/confirm/deny).
- Inbound iMessage is `source="external"` → red-list **always** confirms.
- Only the **owner handle** can issue commands/approvals; all other senders are read-only/triage.
- `pause`/`panic` halt instantly; everything logged + reversible.
- No cloud LLM in the reasoning path (local brain only).

---

## Architecture

```
 your phone (iMessage)
        │
        ▼
 macOS Messages.app  ───────────────►  ~/Library/Messages/chat.db  (local SQLite)
                                              │  poll new rows since last-seen ROWID
                                              ▼
                     ┌──────────────  imessage_channel.py (daemon)  ──────────────┐
                     │  for each new message:                                      │
                     │    owner?  ─ command? → _handle_owner_command (REUSED)      │
                     │            └ chat?    → route(text, source="external")      │
                     │    non-owner →        → comms triage (classify/draft/esc.)  │
                     │  outbound: replies, approvals, proactive pings, digests     │
                     └───────────────────────────┬─────────────────────────────────┘
                                                  ▼
                       send: text / voice-note / attachment  (AppleScript via Messages)
                                                  │
                                                  ▼
                                          your phone (iMessage)
```

### Units (each: purpose / interface / dependencies)

**1. `imessage/inbox.py` — chat.db reader (NEW)**
- *Purpose:* return new inbound messages since a stored cursor (ROWID), each as
  `{rowid, handle, text, is_from_me, date, has_attachment}`.
- *Interface:* `poll_new(since_rowid) -> (list[Message], new_cursor)`; `latest_rowid() -> int`.
- *Depends on:* read access to `~/Library/Messages/chat.db` (**Full Disk Access**), sqlite3.
- *Gotcha (must handle):* on modern macOS the `message.text` column is often NULL and the
  body lives in `attributedBody` (a binary `NSAttributedString`/typedstream). The reader must
  decode `attributedBody` when `text` is NULL. Join `message.handle_id → handle.id` for the sender.
- *Isolation:* pure read; no side effects; testable against a fixture chat.db.

**2. `imessage/send.py` — outbound (NEW, wraps/extends existing)**
- *Purpose:* send text, a voice note, or a file attachment to a handle via Messages AppleScript.
- *Interface:* `send_text(handle, text)`, `send_audio(handle, wav_or_m4a_path)`, `send_file(handle, path)`.
- *Depends on:* `control/messages.py:send_imessage` (already injection-hardened) for text;
  AppleScript `send <file> to buddy …` for attachments; Kokoro TTS for audio generation.
- *Gotcha:* attachment/audio sends via Messages AppleScript are macOS-version-finicky →
  **prototype early**; fall back to text if unsupported.

**3. `imessage_channel.py` — the daemon/handler (NEW; mirrors `telegram_bot.py`)**
- *Purpose:* poll loop; per message, enforce owner-lock, dispatch commands vs chat vs triage; send replies.
- *Interface:* `run()` (blocking poll loop); `handle_message(msg)` (testable unit).
- *Depends on:* inbox, send, `brain.router.route`, `brain.autonomy` (approve/reject/pause/panic/pending),
  `memory`, the existing owner-command parser, the comms-triage tools, `security.identity`.
- *Reuses (do NOT duplicate):* the command grammar + `_handle_owner_command` logic from
  `telegram_bot.py` — refactor the shared parser into a channel-agnostic module both import.

**4. Owner identity**
- `OWNER_IMESSAGE` in `.env` (the owner's phone/Apple-ID handle, normalized). Only this handle
  is "owner". Extend `security/identity.py` so iMessage is a recognized trusted channel.
- First-run safety: if `OWNER_IMESSAGE` is unset, the channel runs in **read-only** mode (no
  commands honored) and tells the owner to set it — never auto-trust the first texter.

**5. Proactive → iMessage hookup**
- Route the existing proactive scheduler's outputs (urgent pings + "what I did" digests) to
  `imessage/send.py` instead of Telegram. (Deep anticipation = sub-project C.)

**6. Telegram retirement**
- `telegram_bot.py` stays in-tree but is no longer started by `start.sh`. The shared command
  parser is extracted so nothing is lost; Telegram can be re-enabled by config if ever wanted.

---

## The four enrichments (build in this order, after the spine)

1. **🔊 Voice-note replies** — generate TTS (Kokoro cloned voice) → send as audio attachment.
   Owner toggles text/voice via a command (e.g. `voice on`/`voice off`); default text.
2. **🖼️ Image/file attachments** — JARVIS attaches generated charts/reports/screenshots.
3. **📣 Texts-me-first** — proactive scheduler pings + digests go out over iMessage unprompted.
4. **📥 Triage everyone's texts** — read all inbound, classify (VIP/family/spam/routine via the
   people registry + comms triage), summarize, draft replies, escalate. Groups read-only.
   **Auto-replies to non-owners pass the red-list gate** (never silently send as the owner).

---

## Safety & identity

- **Owner-lock on every message** (command AND free-text), checked first — non-owner senders
  can never issue commands/approvals (the exact hardening applied to Telegram).
- **`source="external"`** for all inbound → red-list (money/sends/irreversible/OS-control)
  always enqueues a confirmation; nothing auto-fires.
- **Approval grammar:** JARVIS texts `⏳ #N: <summary> — reply 'yes N' / 'no N'`; owner replies
  `yes N` / `no N`; bare `pause` / `panic` / `resume` / `status` / `pending` also parse.
- **Spam/strangers:** unknown senders are triaged, never auto-replied to; blocked contacts
  (people registry) are never actioned.
- **Kill-switch:** `pause`/`panic` over iMessage call the existing `autonomy.set_paused`/`panic`.

---

## Setup / operational (owner-accepted costs)

- **Full Disk Access** granted to the venv Python (one-time macOS System Settings toggle) so
  the process can read `chat.db`. Without it, inbound reading fails — the channel logs a clear
  setup error and degrades to send-only.
- `OWNER_IMESSAGE=<handle>` in `.env` (gitignored).
- `start.sh` adds `caffeinate` (keep-awake) and launches `imessage_channel.py`; stops starting
  `telegram_bot.py`.

---

## Build order (internal phases — each independently testable)

1. **Spine:** inbox poller (+ attributedBody decode) → owner-lock → command/chat dispatch →
   text reply → reuse approve/reject/pause/panic/status. Retire Telegram start. **Ships usable.**
2. **Output richness:** voice-note replies + file/image attachments (with text fallback).
3. **Texts-me-first:** wire proactive pings + digests to iMessage.
4. **Triage-everyone:** full inbound classification/summary/draft/escalate via comms triage.

---

## Testing strategy

- **inbox.py:** unit tests against a **fixture `chat.db`** (built in a temp dir) covering: new-row
  detection since cursor, `attributedBody`-only messages, handle resolution, `is_from_me` filtering.
- **handle_message:** owner vs non-owner (non-owner command → ignored/triaged, never executed);
  owner command → dispatched; owner chat → `route(..., source="external")`; red-list → confirm.
- **approval grammar:** `yes N`/`no N`/`pause`/`panic` parse; malformed handled.
- **send.py:** mock AppleScript; assert correct invocation + text fallback when audio/attach unsupported.
- **safety:** red-list from iMessage enqueues + does not execute; panic halts; spam not auto-replied.
- **No real iMessage / no network** required in tests — all fixtures + mocks. Zero regression on
  the existing 350-test suite; the shared command parser refactor keeps Telegram tests green.

---

## Scope / YAGNI

**In v1:** everything above (spine + 4 enrichments).
**Out of v1 (later, if wanted):** group-chat *control* (groups stay read-only), read receipts /
typing indicators, reactions/tapbacks, multi-owner, RCS/SMS-only contacts. Deep anticipatory
"texts me first" intelligence is sub-project C.

---

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| `chat.db` schema varies across macOS versions; text in `attributedBody` | Decode attributedBody; pin tested macOS; fixture tests; defensive parsing |
| Audio/attachment sends finicky via Messages AppleScript | Prototype in phase 2 FIRST; text fallback always available |
| Full Disk Access not granted | Detect + clear setup error; degrade to send-only |
| Polling latency / CPU | Tunable interval (e.g. 2–4 s); only query rows past the cursor |
| Non-owner spoofing the owner handle | iMessage handle is the identity; document that Apple-ID/number trust is the boundary; red-list still gates irreversible actions regardless |
| Mac sleeps → not listening | `caffeinate` keep-awake in start.sh; daemon liveness on `/api/status` |

---

## Open / "and more" hook
The owner indicated "and more" beyond the four enrichments. Capture any additional v1 wants at
the spec-review gate before planning (candidates: reactions, scheduled-send, per-contact voice
style, "summarize this thread" command).
