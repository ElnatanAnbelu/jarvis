# JARVIS — "Make It Feel Human" Overnight Spec

> Date: 2026-05-30 · Owner: Elnatan · Executor: overnight session

---

## Context — why we're doing this

JARVIS is **already a large, mostly-built system** (verified: 128 registered `@tool`s, 13 test
suites, full 4-agent routing, Second Brain, observer/proactive loops, multi-engine voice). The
problem is **not** missing capability. The problem is that the system **feels like a robot**, the
voice is broken, and Elnatan doesn't trust what actually works — so he keeps building instead of
finishing. He wants to **finish JARVIS tonight** and move on to other projects.

The four lived complaints:
1. **Voice is dead** — agents can't talk.
2. **UI feels like a chatbot** — the orb expanding into a chat window kills the magic.
3. **Agents feel scripted / work-obsessed** — only talk about Nexel & Addis Market; he wants a real
   life assistant that talks like a person (school, work, life — everything).
4. **JARVIS isn't using the brain** — replies aren't grounded in his real life/memory.

Root cause is shared: the **experience** is broken, and the **prompts literally instruct work-bot
behavior** (e.g. JARVIS persona: *"You run the Nexel empire…"*). It's a fix/wiring/tuning job, not
a rebuild.

**Intended outcome by morning:** talking to JARVIS feels like talking to a real person — voice-first,
ambient, grounded in his life — plus an honest map of what across the system actually works.

---

## Mission (locked with user)

**Experience + Audit/Repair.** Make the core experience genuinely human, AND run a functionality
audit that fixes quick breaks and reports honest status of the rest. This is the combination that
lets Elnatan walk away.

### Phase 1 — IN scope tonight (7 workstreams)
1. 🎙️ **Real voice conversation** — wake word "JARVIS"/"Hey JARVIS" → hands-free flowing
   conversation (VAD turn-taking, barge-in, echo guard, natural ElevenLabs voice).
2. 🔮 **Ambient orb** — orb stays in the corner, works in the background, **never auto-expands into
   a chat**. The chatbot feel is removed at the root.
3. 🖥️ **Show-on-demand surface** — a display surface appears **only when asked** ("show me / open /
   look this up") for: web/search, files/images, JARVIS's own visual content, apps/links.
4. 🧠 **Smarter + human** — JARVIS persona rewritten to a natural life assistant; all agents
   de-work-obsessed + human-sounding; **Second Brain/memory actually fires and grounds replies**.
5. 👁️ **Vision on request** — "JARVIS, what do you see?" → captures the camera, analyzes it, and
   answers out loud (camera permission already granted).
6. 🔍 **Functionality audit** — automated map of what works (✅/🔴/⚠️) across the 128 tools +
   subsystems, fixing quick, safe breaks.
7. 🧹 **House-cleaning** — delete dead/duplicate code (old UIs, redundant voice engines, build
   artifacts) so the repo stops feeling endless.

*(Workstream sections below are numbered WS1–WS7; the order they're built in is in "Execution order"
at the end.)*

## Roadmap beyond tonight (documented, NOT built tonight)

Phase 1 (tonight) = the 7 workstreams below. Everything else is grouped into three later phases by
theme and dependency. Each item lists its goal, the foundation already in the repo, and what the
phase adds. Phases are ordered so each builds on the last.

---

### Phase 2 — "The companion wakes up" (proactivity, memory, trust)

*Theme: JARVIS stops being purely reactive and starts to feel present, remembers your life, and
earns trust by being reliable. This is the layer that turns a voice assistant into a companion.*

**2.1 🤖 Proactive intelligence suite.** JARVIS decides on its own *when* to speak up.
- Interest/hobby model (learned from the Second Brain) → "hey, look at this new release / this news."
- Morning briefings (weather + news + priorities + calendar) — `brain/briefing.py` exists.
- Midday + evening accountability ("what did you ship today?", habits + calendar check).
- Calendar event alerts (~30 min before).
- A **"should I interrupt?" judgment layer** so it's helpful, not annoying (rate limits, quiet mode,
  surface/normal/collapsed visibility — partly present in `observer.py`).
- *Foundation:* `/api/proactive` + `proactive.py` + `observer.py`. Adds the interest model + judgment
  layer on top. **Everything else proactive in later phases depends on this layer.**

**2.2 🧠 People & relationship memory.** Talks about people like a real friend.
- Remembers friends/family/colleagues; tracks context, last-talked, birthdays, important events.
- Brings people up naturally in conversation ("how'd the thing with X go?").
- *Foundation:* Second Brain Relationships vault (`memory/vault.py`). Adds retrieval + natural
  surfacing into conversation.

**2.3 🩺 Self-healing / reliability.** JARVIS keeps itself alive and honest about its own state.
- Monitors its subsystems (voice daemons, observer, server), **auto-restarts** dead ones, and
  **tells you** when something breaks instead of failing silently.
- Directly addresses the "I don't trust it works" problem — the continuous version of the WS5 audit
  (which is a one-time snapshot).

**2.4 🔔 Notification aggregation.** Turns the macOS notification firehose into a calm briefing.
- Reads notifications, filters noise, **speaks only the important ones** ("your meeting starts in 5").
- *Depends on* the 2.1 judgment layer to decide what's worth interrupting for.

**2.5 📧 Email-driven speech.** JARVIS speaks up when important emails arrive.
- *Foundation:* `brain/tools/ingest_emails.py`. Turns ingestion into a proactive trigger gated by the
  2.1 "should I interrupt?" layer.

---

### Phase 3 — "Senses & reach" (extend perception and access)

*Theme: JARVIS perceives more than the camera + mic, and follows you beyond the Mac. Tonight it can
see through the camera (WS6); this phase gives it screen sight, your documents, your music, and a
presence on your phone.*

**3.1 🖥️ Screen awareness.** JARVIS sees what's on your screen (not just the camera).
- "What's this error?", "summarize this page", context-aware help based on the active window.
- *Foundation:* `control/screen.py` (screenshot + vision). Adds on-request + optional ambient screen
  understanding, reusing the WS6 vision plumbing.

**3.2 📱 Phone / remote access.** Talk to JARVIS from your phone when away from the Mac.
- Voice + full capability remotely, not just text.
- *Foundation:* `telegram_bot.py` (text + brain alerts). Extends to voice + parity with the desktop.

**3.3 📄 Document intelligence.** Drop in PDFs/notes/screenshots → JARVIS reads, files, and recalls.
- "What did that contract say?", "find my notes on X." Auto-files into the Second Brain.
- *Foundation:* ingestion pipelines (`brain/tools/ingest_*`) + vault. Adds doc parsing + retrieval.

**3.4 🎵 Media & music.** Voice control of Spotify/Apple Music + recommendations tied to your taste.
- "Play something focused", "what's that new album you mentioned?"
- *Foundation:* `control/mac.py` AppleScript app control. Adds a media tool + taste model.

**3.5 🗺️ Maps & directions.** "Show me directions to X", "where is Y?" → a map on the show-surface.
- *Not in the codebase yet* — new capability. Easiest path: a `[SHOW:map=<place>]` directive that
  opens Apple/Google Maps via `open_in_browser`, or embeds a map in the WS3 show-surface.
- *Foundation:* `open_in_browser` (`brain/tools/web.py`) + the WS3 show-surface. Adds the map
  directive + intent detection.

---

### Phase 4 — "Autonomy & life ops" (it does things for you, full domains)

*Theme: the heaviest, highest-risk capabilities — JARVIS acting on its own and owning whole life/work
domains. Deliberately last because each needs the trust (Phase 2) and guardrails to be safe.*

**4.1 🦾 Autonomous agent actions (computer use).** JARVIS does multi-step things on the Mac on its own.
- Navigates apps, fills forms, books things, completes tasks end-to-end with a browser/vision
  verification loop.
- **Needs strict guardrails** (confirmation on destructive/outward actions, scoped permissions).
- *Foundation:* `control/computer_agent.py`, `control/computer.py`, `control/browser.py`, 100+ tools.
  Hardens the autonomous loop + safety.

**4.2 ⏰ Routines & automation.** Scheduled, multi-step routines that chain tools automatically.
- "Every morning do X", "when I get home Y" — cron-style triggers that run tool chains on their own.
- *Foundation:* the proactive scheduler. Adds a user-definable routine engine. *Builds on* 4.1 for
  the action chains and 2.1 for timing/judgment.

**4.3 💰 Personal finance.** Separate from the Business OS — Elnatan's own money.
- Budgeting, spending tracking, bills, subscription watch. "How much did I spend this month?",
  "what subscriptions can I cut?"

**4.4 📊 Full Business OS.** The work side, done properly (kept *out* of JARVIS's core personality).
- Live revenue / expenses / P&L, KPIs, CRM pipeline, tax estimates, competitor analysis, investor
  pitches, social/marketing calendars — real data + dashboards.
- *Foundation:* `brain/tools/business.py` + `control/business_tools.py`. Wires real data sources +
  visual dashboards.

---

## Current state — what already exists (verified, do not rebuild)

**Launch path:** `JARVIS.app` → `app/main.py` → spawns `ui/server.py` (Flask :8080) →
opens **bubble window** (`/bubble` = `app/bubble.html`, always-on-top, frameless, 150px corner) +
**HUD window** (`/` = `app/jarvis.html`, hidden by default).

**The orb (`app/bubble.html`) already does most of the dream:**
- Click → `start_recording()` (native mic via `JsApi`) → `stop_recording()` → **Groq
  `whisper-large-v3-turbo`** transcription → `/api/stream` (SSE) → **speaks reply aloud** via
  `/api/tts`.
- **Barge-in** (tap while speaking stops TTS), **caption fade**, orb **states**
  (listening/thinking/speaking/has/active), and a **proactive poll** of `/api/proactive` every 10s
  that speaks `surface` messages.
- `[SHOW:...]` directives are already parsed/stripped from spoken text.

**Native bridge (`app/main.py` `JsApi`):** `start_recording`/`stop_recording` (sounddevice→Groq),
`capture_frame` (camera), `show_hud`/`hide_hud`/`toggle_hud`, `quit_app`, mic/camera permission
helpers. ARM64 re-exec guard + TCC handling already in place.

**Server (`ui/server.py`):** `/api/stream`, `/api/tts`, `/api/proactive`, `/api/chat`,
`/api/voice`, `/api/upload`, `/api/agent`, `/api/execute`, `/api/active_agent`, `/api/status`,
`/api/end_session`. Routing via `brain/router.py` (`route`, `route_stream`); thinking via
`brain/think.py` (`think_stream`, Second Brain context injection, `VaultManager.search_vault`).

**Voice engines:** `voice/speak.py` = ElevenLabs turbo → edge-tts → `say`. `/api/tts` server path
warms **Kokoro daemon** + edge. `voice/listen.py` has `listen_until_silence()` (VAD) + local
Whisper. **Two stale Kokoro daemons currently running** (PIDs to be cleaned).

**Not a voice wake word yet:** `control/wake.py` is **Mac sleep/wake** (pmset) for morning
briefings — NOT speech wake word. The voice wake word must be **built**.

---

## Workstream 1 — Real voice conversation (PRIORITY #1)

**Goal:** Say "JARVIS" / "Hey JARVIS" → it opens a live conversation → you just talk, it talks back,
hands-free, until silence ends it. Feels like a person, not a transcriber.

**System-wide, always-on (user requirement):** The sphere (`app/bubble.html`) is the small orb that
**lives on the desktop permanently, floating over every app** (always-on-top, all spaces). You must
be able to **talk to JARVIS from any app** — so the **wake-word listener runs continuously in the
background process regardless of which app has focus**, and **JARVIS is always running**. The mic
listener does not depend on the bubble or HUD window being focused/visible. (Stretch: launch at
login + keep-alive so it's always there after reboot.)

**Design (conversation-mode pattern):**
- **Wake word arms it.** Add an offline wake-word listener (recommended: `openwakeword`, fully
  offline; fallback: lightweight energy-gate + Groq keyword check). Runs as a background thread in
  the `JsApi`/main process so it shares the existing mic plumbing.
- **Conversation mode.** On wake → orb enters `listening` → VAD captures the turn (reuse
  `listen_until_silence` logic) → existing `streamReply()` path → **TTS reply aloud** → **auto
  re-open mic** for the next turn (no re-wake needed) → repeat.
- **Barge-in.** Already present in `bubble.html` `talk()`; extend so speaking during a reply stops
  TTS and starts a new turn.
- **Echo guard (critical).** Mic listening is **suppressed while/just-after TTS plays** so JARVIS
  never transcribes its own voice (the classic always-on self-talk loop). Gate on the orb's
  `speaking` state + a short cooldown after `onended`.
- **Auto-close.** After ~20–30s of silence, conversation mode closes → back to wake-word-armed.
- **Latency honesty:** minimize (Groq turbo STT + ElevenLabs turbo TTS + streamed thinking) but a
  small gap will remain; that's expected and acceptable.

**Files:** `app/main.py` (`JsApi`: add continuous-listen + wake thread + state coordination),
`app/bubble.html` (conversation-mode state machine, echo guard, auto-turn), possibly a new
`voice/wake.py` (speech wake word — distinct from `control/wake.py`), reuse `voice/listen.py` VAD.
Dependency add: `openwakeword` (offline) — note in `requirements.txt`.

**"Voice is down" repair:** diagnose & fix the broken speech chain — kill/rationalize the duplicate
Kokoro daemons, verify `/api/tts` returns audio end-to-end from the orb, confirm ElevenLabs key path
works, ensure mic permission/Groq transcription returns text. Must end with: **say something → hear
a spoken reply.**

---

## Workstream 2 — Ambient orb (kill the chatbot)

**Goal:** The orb is home base. It never expands into a chat window. The HUD becomes a **display
surface** summoned only to show things, not a conversation log.

**Changes:**
- **Remove the auto-expand-to-chat behavior.** In `app/bubble.html`, the `⤢ expand` button
  currently calls `toggle_hud()` to open `jarvis.html` (the chat). Repurpose: the HUD only appears
  when there's **content to show** (WS3 SHOW pipeline), not as a manual chat toggle. Keep a minimal
  escape hatch (e.g. long-press / tiny toggle) for typing if Elnatan ever wants it, but it is **not
  the default and not chat-styled**.
- **HUD (`app/jarvis.html`) → display surface.** Strip the chatbot framing (message bubbles, avatars,
  persistent transcript, "Message JARVIS…" text box) from the default view. When summoned it shows
  **the thing** (web page / image / file / generated content) cleanly, then can be dismissed back to
  just-the-orb. Conversation stays in voice; the surface is for visuals only.
- Keep the orb's existing states/animations/captions — they're good.

**Files:** `app/bubble.html` (expand wiring), `app/jarvis.html` (de-chatbot the layout + add a
display-surface mode), `app/main.py` (window show/hide already supports this via `show_hud`/`hide_hud`).

---

## Workstream 3 — Show-on-demand surface

**Goal:** "show me / open / look this up / pull up X" → a surface appears with that content, driven
by JARVIS's `[SHOW:...]` directive (already parsed in `bubble.html`).

**Supported show types (all four, user-confirmed):**
- **Web / search** — open a URL or search results in the surface.
- **Files / images** — open a local file / image / document.
- **JARVIS's own content** — when a reply is inherently visual (list, code, table, draft), render it
  on the surface instead of (or alongside) speaking it.
- **Apps / links** — launch a Mac app or open a URL (reuse `control/mac.py` / `control/browser.py`
  app-open tools that already exist).

**Design:** Extend the `[SHOW:...]` directive vocabulary so the model can emit
`[SHOW:url=…]`, `[SHOW:file=…]`, `[SHOW:image=…]`, `[SHOW:app=…]`, `[SHOW:html=…]`. `bubble.html`
already detects `[SHOW:...]`; on detection it calls `show_hud()` and passes the payload to
`jarvis.html`'s display surface (WS2). Prompts (WS4) teach agents **when** to emit a SHOW directive
("when the user says show/open/look up, or when seeing it beats hearing it").

**Files:** `app/bubble.html` (parse SHOW payload → drive surface), `app/jarvis.html` (render each
show type), prompt updates so agents emit SHOW directives appropriately. Reuse existing
web/file/app tools rather than writing new ones.

---

## Workstream 4 — Smarter + human + brain-grounded

**Goal:** Stop sounding scripted/work-obsessed. JARVIS = natural daily-driver life assistant; all 4
agents human-sounding and grounded in Elnatan's real life via the Second Brain.

**Changes:**
- **Rewrite JARVIS persona** (`prompts/personas/jarvis.md` + the persona block in `brain/think.py`):
  remove the "you run the Nexel empire / track KPIs" framing as the *core identity*. New identity:
  a warm, sharp, natural life assistant for **everything** — school, work, life — that talks like a
  real person. Business is **one domain among many**, available when relevant, not the personality.
- **De-work-obsess all agents** (`friday.md`, `karen.md`, `veronica.md`): keep their distinct
  personalities/specialties but make them human-sounding and not Nexel-fixated. Update the
  memory/example prompts that hardcode "Addis Market last week" style.
- **Conversational tone for voice:** prompts must produce **spoken-natural** replies (short, warm,
  no markdown/bullet-dumps when speaking) — voice replies already strip markdown, but the model
  should also *write* for the ear.
- **Make the brain actually fire:** verify Second Brain grounding (`VaultManager.search_vault`,
  `load_second_brain_modules`, per-agent brain context) is invoked on conversational turns — not
  just tool calls — and that retrieved context is injected into the prompt. Fix the routing/gating
  if it's being skipped. Confirm with a question only answerable from his vault.
- Keep the anti-hallucination rule (never invent personal facts) — it stays.

**Files:** `prompts/personas/*.md`, `brain/think.py` (persona blocks + Second Brain routing),
`prompts/core/*.md` (tone/output rules), `memory/vault.py` (only if grounding is genuinely broken).

---

## Workstream 5 — Functionality audit & repair

**Goal:** An honest, automated map of what works so Elnatan can stop guessing — plus quick fixes.

**Deliverable:** `AUDIT_REPORT.md` at repo root with every subsystem + tool category marked
✅ works / 🔴 broken / ⚠️ stubbed-or-unverified, with the failing error captured.

**Method:**
- Run the existing **13 test suites** (`tests/`), capture pass/fail.
- **Smoke-test each of the 128 tools** via the registry: introspect `@tool` registry, call read-only
  / safe tools with representative args, record success/error. **Never** auto-run destructive/write
  tools (respect existing per-agent access control); mark those "manual-verify."
- Verify each subsystem boots: server endpoints (`/api/status`, `/api/stream`, `/api/tts`,
  `/api/proactive`), observer loop, proactive scheduler, Second Brain vault read, memory DBs,
  voice daemons.
- **Fix only quick, safe breaks** (imports, stale daemons, obvious wiring). Anything risky or deep
  is **logged in the report**, not fixed, so the night stays focused on the experience.

**Files:** new `scripts/audit.py` (audit harness) + generated `AUDIT_REPORT.md`. Reuse the tool
registry in `brain/tools/registry.py`.

---

## Workstream 6 — Vision / environment inspection on request (user requirement)

**Goal:** When Elnatan asks, JARVIS can **see his environment** through the camera and describe/answer
out loud. e.g. "JARVIS, what do you see?", "look at this", "inspect my room", "what am I holding?",
"read this label."

**Permissions:** Camera + microphone are **already granted** by the user (TCC attributed to the
frozen `JARVIS.app`). No permission work needed — just wire the capability.

**Design:**
- The native bridge already has **`JsApi.capture_frame()`** (`app/main.py`) — OpenCV primary, ffmpeg
  fallback, returns base64 JPEG.
- On a vision intent (voice command contains "see / look / show you / what's this / inspect / room /
  camera / what am I holding" etc.), the conversation loop: **capture a frame → send the image to a
  vision-capable model** (Gemini 2.0 Flash or Claude vision — both keys present) → **speak the
  description/answer** aloud via the normal TTS path.
- Route this through the existing model/agent flow rather than a one-off path, so the answer is
  grounded and conversational (not a robotic caption).
- The captured frame may also be surfaced visually via the WS3 `[SHOW:image=…]` path if Elnatan says
  "show me what you see."

**Files:** `app/bubble.html` / conversation loop (detect vision intent → call `capture_frame` →
attach image to the turn), `brain/think.py` or `brain/router.py` (accept an image with the prompt
and route to a vision model), reuse existing vision tooling in `control/computer.py` / `control/screen.py`
if it already does image analysis. No new permission code.

**Verify:** Say "JARVIS, what do you see?" with something in front of the camera → it captures and
**describes it accurately out loud** within a few seconds.

---

## Workstream 7 — House-cleaning (delete dead/duplicate code)

**Goal:** Remove the dead and duplicate code that makes the repo confusing to navigate — a real
contributor to "this project feels endless." **A git checkpoint commit happens first, so every
deletion is reversible.**

**Delete dead UIs (confirmed dead by user's own trace):**
- `app/hud.html` (served nowhere), `JARVISApp/` (Swift, unwired), `jarvis.py` +
  `jarvis-launch.sh` (old terminal loop), `start.sh` (old browser-tab launcher).

**Consolidate voice engines (5 → 2):**
- Standardize on **ElevenLabs (primary) + one offline fallback** (keep edge-tts *or* a single Kokoro
  daemon — pick the more reliable during WS1; remove the other).
- Remove **Chatterbox cloning**: `voice/clone_daemon.py`, `voice/clone_env/` (heavy, unused).
- Remove old **`voice_daemon.py`** (terminal always-listen loop — replaced by WS1 wake-word loop).
- Kill the two stale Kokoro daemons; ensure only one (if any) is managed by the server.

**Clean build artifacts (and gitignore them):**
- Remove `build/`, `dist/`, untracked `JARVIS.app/` from the repo; add to `.gitignore` (they
  regenerate via `scripts/build_app.sh`).

**Remove stray debug scripts:**
- `fix_mic_permission.py`, `test_media_layers.py` (one-off root debug files — mic handling now lives
  in `app/main.py` `JsApi`).

**Safety:** checkpoint commit before any deletion; verify the app still launches + talks after
cleanup (WS1 verification) before committing the removals.

---

## Files: touch vs. delete

**Will modify:** `app/bubble.html`, `app/jarvis.html`, `app/main.py`, `ui/server.py` (only as needed
for SHOW/echo/voice), `brain/think.py`, `prompts/personas/*.md`, `prompts/core/*.md`,
`requirements.txt`; **new:** `voice/wake.py`, `scripts/audit.py`, `AUDIT_REPORT.md`.

**Deleting (WS7, after checkpoint):** `app/hud.html`, `JARVISApp/`, `jarvis.py`, `jarvis-launch.sh`,
`start.sh`, `voice/clone_daemon.py`, `voice/clone_env/`, `voice_daemon.py`, `build/`, `dist/`,
`JARVIS.app/`, `fix_mic_permission.py`, `test_media_layers.py`.

**Pre-existing uncommitted work:** the repo already has modified/untracked files (HUD, brain agents,
prompts, `JARVIS.app/`, `fix_mic_permission.py`, `test_media_layers.py`). Before starting, **stash or
commit a checkpoint** so overnight changes are isolated and reversible.

---

## Verification (how we know it worked)

1. **Voice conversation (system-wide):** Launch `JARVIS.app`. **Switch focus to another app**
   (e.g. browser, editor). Say "Hey JARVIS" — orb goes to listening **even though JARVIS isn't the
   focused app**. Ask a question out loud. Hear a spoken, natural reply. Ask a follow-up **without**
   re-waking. Interrupt it mid-sentence (barge-in) — it stops and listens. Stay silent ~25s — it
   closes. **No self-talk loop** while it speaks. Orb stays visible on the desktop the whole time.
2. **Ambient orb:** Orb stays in the corner; nothing auto-expands into a chat during normal talking.
3. **Show-on-demand:** Say "show me the weather" / "open this file" / "look up X" → surface appears
   with the content → dismiss → back to just the orb. Each of the 4 show types works once.
4. **Smarter + human:** Ask something personal answerable only from the Second Brain → it grounds
   the answer in real vault content (not invented, not Nexel-deflected). Casual chat sounds human,
   not scripted.
5. **Audit:** `AUDIT_REPORT.md` exists with ✅/🔴/⚠️ per subsystem and per tool category; `tests/`
   results captured; quick breaks fixed.

---

## Risks & honest limits

- **Wake word reliability** is the hardest piece; offline models have false-accept/reject tradeoffs.
  Mitigation: tune threshold conservatively; barge-in + manual orb-tap remain as reliable fallbacks.
- **Echo/self-talk loop** is the top always-on failure mode — echo guard is mandatory, not optional.
- **128-tool audit** is breadth-first by design; it reports rather than deep-fixes, to protect the
  night's focus on experience.
- **Latency** in the voice loop will be non-zero; acceptable per user.
- Proactive companion (Phase 2) & business analytics (Phase 4) are **explicitly deferred** to later
  phases to guarantee the core ships tonight.

---

## Execution order (overnight)

1. Checkpoint repo (stash/commit current WIP).
2. WS1 voice repair first (get "say something → hear a reply" working), then wake word +
   conversation mode + echo guard.
3. WS4 prompts/brain (cheap, high-impact on "feels human").
4. WS2 ambient orb (de-chatbot).
5. WS3 show-on-demand surface.
6. WS6 vision / environment inspection on request.
7. WS7 house-cleaning (delete dead/duplicate code) — after verifying the app still launches + talks.
8. WS5 audit harness + report (runs last, captures final state of the cleaned system).
9. Save the spec, commit everything.
