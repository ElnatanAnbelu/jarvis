# JARVIS — project brief (for Codex sessions)

> ## 🔒 UI IS LOCKED — DO NOT TOUCH
> The owner loves the Alfred environment UI exactly as it is. **`app/alfred.html` (the
> fullscreen living environment — holo core, awareness HUD, panels, layout, look & feel)
> is FROZEN.** Do not modify its design, layout, styling, or animations. Backend wiring
> *underneath* it (connecting accounts, voice, panel data) is fine **as long as it does
> not change a single pixel of what's rendered**. If a task seems to require touching the
> visible UI, STOP and ask the owner first.

**What this is:** Elnatan's personal **autonomous life operator** — a free, **fully-local**, offline-capable AI (the MCU "JARVIS", addresses him as "sir") that runs his comms / business / school / personal life, acting on its own and reporting after, behind a hard safety net. Voice-first + Telegram + a cinematic control room.

## Architecture (fully-local)
- **Brain:** one JARVIS = a local **LLM-with-tools loop** (`brain/agent.py`) on **Ollama** via `brain/llm.py`. Tier router: `qwen2.5:7b` (fast, default) ↔ `qwen3:14b` (complex). Lean system prompt + tool routing keep it snappy (~3–7s, no cloud). `brain/think.py` delegates to the local agent (cloud path remains as a disabled fallback).
- **Tools:** `brain/tools/` — `@tool` registry (~136 tools) + `execute_tool` dispatch. Every call goes through the safety gate.
- **Safety gate:** `brain/autonomy.py` `gate()` → execute / confirm / deny. Red-list (money/irreversible/send), **away-mode**, **supervised↔auto** shakeout, **pause** kill-switch, **panic** (halt+reject+revert-window), contact-aware (VIP/family/blocked via `memory/people.py`), source tagging (`external` inbound always confirms).
- **Memory:** `memory/memory.py` (sqlite `jarvis.db`: conversations/facts/meta/**actions_performed ledger**/scheduled_tasks/**pending_confirmations**) + `memory/migrations.py` (PRAGMA user_version) + `memory/vault.py` (Obsidian Second Brain at `~/Documents/SecondBrain`, risk-tiered proposals, offline FAISS RAG).
- **Autonomy:** `brain/runner.py` (goal runner, source=autonomous) + `brain/proactive.py` scheduler + `brain/presence.py` (Mac idle/lock → away-mode).
- **Voice:** `voice/local_stt.py` (faster-whisper, offline, local-first w/ Groq fallback) + Kokoro local TTS. Wake word "Hey JARVIS".
- **Identity:** `security/identity.py` (PIN + Telegram + graceful face/voice biometrics + trusted session).
- **Surfaces:** `app/control.html` = the **MCU control room** (live `/control`), `app/bubble.html` orb, `app/jarvis.html` HUD, `app/main.py` pywebview shell + JsApi. Server `ui/server.py` (Flask, token-gated; `/api/pending|approve|reject|undo|panic|mode|away|identity|lock|activity|status`).
- **Away-channel:** `telegram_bot.py` — approve/reject/pause/resume/away/home/auto/supervised/panic/digest/lock/unlock/setpin/goodnight/goodmorning + owner allowlist.
- **Observability:** `obs/log.py` (structured JSON + correlation IDs + heartbeat).
- **Privacy:** `brain/privacy.py` `forget_subject` (db + vault archive). Backup: `scripts/backup.sh` (encrypted).

## Run it
- Server + control room: `bash scripts/start.sh` → http://localhost:8080/control  (localhost-only, token-gated)
- Desktop app: `./venv/bin/python app/main.py`
- Tests: `./venv/bin/python -m pytest -q`  (350 passing)
- Health check: `./venv/bin/python scripts/audit.py`  (local brain · gate · firewall · token-gate · vault RAG · voice)
- Local-brain eval gate: `./venv/bin/python eval/run.py`
- Requires: Ollama running with `qwen2.5:7b` (+ optionally `qwen3:14b`); Python 3.9 venv.

## Safety model (non-negotiable)
Every tool call is gated. Money/irreversible/VIP/family/blocked/public → **always confirm** via Telegram. Default mode is **supervised** (proposes everything); flip per-domain to **auto** when trusted. Everything logged + reversible (ledger + undo); `pause`/`panic` halt instantly.

## Status (as of this build)
Done + committed on `feat/autonomous-life-operator`: Order 0 security · P0 run · P1 local brain · P4 observability · P5 autonomy engine · P6 comms domain + people registry · P3 identity · P2 local STT · P7 control room + rituals · P8 privacy/backup. **334 tests green.**

**Post-audit safety hardening** (two multi-agent audits → 32 verified defects, all fixed). Audit 1: gate **fails closed** (was silently bypassed via a `people`-schema collision); **self-write firewall** (JARVIS can't overwrite its own code/`.env`); **computer-use gated** + honors panic/pause; **AppleScript injection** in iMessage closed; **inbound tagged `external`** + Telegram owner-gated; cloud-auth `make_client`; **panic/undo truly reverts** file ops; **offline purity** (no cloud LLM in the reasoning path by default; opt-in via `JARVIS_ALLOW_CLOUD_BRAIN=1`). Audit 2: **red-list always confirms** for autonomous/external even at home (the "loaded gun" gap); **prompt-injection containment** (source taint-escalates after reading untrusted content); **blocking think() never cascades to cloud** on a local hiccup; **forget_subject purges ALL stores** (wiki+FAISS, observations.db, people, life, normalized keys); **consolidate_facts** non-destructive + offline-gated; **approve()** atomic-claim + pause-guard (no double-pay / post-panic exec); **panic doesn't oscillate** on double-press; loop/queue dedup; persona injection clause; FAISS lock-snapshot.

Still needs the user: a **mic test** (P2 TTS/clone end-to-end), **camera enrollment** (P3 biometrics), **live account creds + VIP/family/blocklist data + `WHATSAPP_TOKEN`** (P6 live execution). The plan + behavior spec live in `specs.md` and `~/.Codex/plans/elegant-snuggling-ladybug.md`; gap report in `GAP_REPORT.md`; sign-offs in `SIGN_OFFS.md`.
