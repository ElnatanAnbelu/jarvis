# JARVIS — project brief (for Claude Code sessions)

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
- Tests: `./venv/bin/python -m pytest -q`  (297 passing)
- Local-brain eval gate: `./venv/bin/python eval/run.py`
- Requires: Ollama running with `qwen2.5:7b` (+ optionally `qwen3:14b`); Python 3.9 venv.

## Safety model (non-negotiable)
Every tool call is gated. Money/irreversible/VIP/family/blocked/public → **always confirm** via Telegram. Default mode is **supervised** (proposes everything); flip per-domain to **auto** when trusted. Everything logged + reversible (ledger + undo); `pause`/`panic` halt instantly.

## Status (as of this build)
Done + committed on `feat/autonomous-life-operator`: Order 0 security · P0 run · P1 local brain · P4 observability · P5 autonomy engine · P6 comms domain + people registry · P3 identity · P2 local STT · P7 control room + rituals · P8 privacy/backup. **297 tests green.**

Still needs the user: a **mic test** (P2 TTS/clone end-to-end), **camera enrollment** (P3 biometrics), **live account creds + VIP/family/blocklist data + `WHATSAPP_TOKEN`** (P6 live execution). The plan + behavior spec live in `specs.md` and `~/.claude/plans/elegant-snuggling-ladybug.md`; gap report in `GAP_REPORT.md`; sign-offs in `SIGN_OFFS.md`.
