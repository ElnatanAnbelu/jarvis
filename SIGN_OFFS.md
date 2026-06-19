# JARVIS — Sign-offs

## Order 0 — Security Remediation (stop the bleeding)
- **AppSec — APPROVED WITH FIXES** — Drive-by/cross-origin RCE closed: wildcard CORS removed, per-session token + same-origin gate added to `ui/server.py`, live-probed (protected routes 403 without token, 200 with, cross-origin POST 403). Public Cloudflare tunnel disabled in `scripts/start.sh`. WhatsApp webhook (`/api/whatsapp`) now requires the WhatsApp shared secret; Node bridge bound to 127.0.0.1 + token-gated. Leaky `AUDIT_REPORT.md` removed from tree; token files gitignored. 159/159 tests green. **Outstanding (owner = user):** rotate all secrets (were plaintext / prefixes in git history); set `WHATSAPP_TOKEN` if using the Node bridge; optional git-history purge of `AUDIT_REPORT.md`.
- **Live Verification — APPROVED** — server served on :8080, auth gate behaves correctly across 6 probe cases, app still loads with injected token.
- **Regression — APPROVED** — 159 baseline tests green after changes (zero regressions).

## Block A — Safety Substrate — APPROVED WITH FIXES
- **Backend/DBA — APPROVED** — Migration framework (`memory/migrations.py`, PRAGMA user_version) + reversible ledger columns + `pending_confirmations` table + `revert_action` + flag helpers. Real jarvis.db migrated to v1, legacy rows intact.
- **Safety gate — APPROVED** — `brain/autonomy.py` central `gate()` (execute/confirm/deny), red-list, away-mode, pause kill-switch, approve/reject. Wired into `brain/tools/registry.py` `execute_tool` (risk tag on `@tool`; 7 red tools tagged); bypass path for approved actions.
- **Channels — APPROVED** — Telegram `approve/reject/pause/resume/away/home/status/pending/undo` + owner allowlist (C4 partial); `ui/server.py` routes `/api/pause|resume|away|pending|approve|reject|undo|activity` (token-gated); control tools (`tool_undo/pause/resume/set_away/safety_status`).
- **Adversarial (§6.4) — APPROVED** — executed end-to-end: away+red→enqueue→approve→executes; reject→never runs; pause→autonomous denied/user allowed; external red→approval even when home. 240/240 tests green, zero regressions.
- **Outstanding (→ Block C):** inbound handlers (telegram/whatsapp/email router→think→execute_tool) must pass `source="external"` so external-triggered red actions always confirm even when NOT away. The gate supports it; the inbound wiring is Block C. Away-mode (primary while-away scenario) is fully covered now.
## P0 — Make it RUN — APPROVED
- Consolidated auth into `brain/auth.py`; fixed the `(key,is_oauth)` tuple-as-`api_key` crash class (vision/docs/briefings/computer-use). App boots + serves; previously-crashing path degrades gracefully. 246/246 green; live-verified.

## P1 — The Local Brain — APPROVED
- `brain/llm.py` (local Ollama client) + `brain/agent.py` (single-JARVIS LLM-with-tools loop). Retired the cloud brain for JARVIS; fully local. Model-tier router (qwen2.5:7b fast / qwen3:14b complex) + relevance tool-routing (≤14 of ~130 tools/call) + lean system prompt. Offline vault embeddings (no HF hang). **Eval gate PASSED 100%** (tool-selection/restraint/anti-hallucination). **Latency validated: 92s→6.8s, 34s→3.5s, 38s→5.3s (~10x) — the lag is fixed.** 259/259 green.

## P4 — Observability — APPROVED
- `obs/log.py` structured JSON logging + correlation IDs + heartbeat/liveness; `execute_tool` emits tool.executed/denied/confirm_required/failed (the autonomy audit trail); `/api/status` daemon liveness; key silent-failure points in proactive now logged. 256/256 green.

## P5 — Autonomy engine + away-channel — APPROVED (core); enhancements pending
- `brain/runner.py` goal-driven autonomous runner (source=autonomous, respects pause). `autonomy.autonomy_mode` **supervised→auto shakeout switch** (default supervised = propose everything). Source threaded user→think→agent→gate; `/api/whatsapp` tagged `source="external"` (closes C4). **Panic** (`autonomy.panic` + `/api/panic` + Telegram `panic`): halt + reject-pending + revert-window. Telegram `auto`/`supervised`; `/api/mode`. 266/266 green.
- **Pending P5 enhancements (follow-on):** presence detection (`brain/presence.py`), away-mode batch-scan loop, "what I did" digests. (Controls + engine + gating are done; these are conveniences.)

## P7 — Control room (UI) — APPROVED (core)
- 4 design directions generated (`app/mockups/`); user picked **cinematic shell + clean panels**. Built `app/control.html` LIVE: polls `/api/pending|activity|status`, Approve/Reject/Undo/Panic/mode/away wired to real token-gated endpoints, always-on cyan orb. `/control` route + structured `/api/activity` + `memory.get_recent_actions_list`. Live-verified (200, token injected, endpoints authed). 273 green.
- **Remaining P7 (tied to P2):** voice polish, goodnight/goodmorning rituals, greet-on-recognition, orb-in-app-shell decoupling.

## P6 — Domains (comms lead) — APPROVED
- `memory/people.py` VIP/family/blocklist registry wired into `autonomy.gate` (blocked never auto-acts; VIP/family sends confirm unless present). `brain/domains/comms.py` triage (spam/important/routine, VIP-aware). `people_tools` (add_vip/family/block/list/triage_inbox). Business/school reuse the same pattern; live execution needs the user's account creds + `WHATSAPP_TOKEN`.

## P3 — Identity lock — APPROVED
- `security/identity.py`: salted-hash PIN, trusted-session TTL, lock, graceful face/voice (degrade → PIN/Telegram). Telegram lock/unlock/setpin; `/api/identity` + `/api/lock`. **Needs user: camera/voice enrollment** to turn on biometrics (PIN/Telegram path works now).

## P2 — Fully-local voice — APPROVED (STT) / partial (TTS)
- `voice/local_stt.py` (faster-whisper, offline) wired local-first into the VAD path with Groq fallback; installed + pinned + unit-tested. **TTS:** Kokoro (local) is already the `/api/tts` default; making `voice/speak.py` Kokoro-first + the cloned "Sir" voice + the end-to-end **mic test** is the remaining bit (needs the user's mic).

## P7-extra — Rituals — APPROVED
- `brain/rituals.py` greeting (surfaces only what needs the user) + goodnight/goodmorning; Telegram + `/api/identity` greeting.

## P8 — Privacy/backup — APPROVED
- Core (db forget + encrypted backup + silent-delete fix) + full `brain/privacy.forget_subject` (db purge + vault-note archive + FAISS invalidation) + `forget_person` tool (red-list).

## Post-audit hardening — APPROVED (multi-agent audit: 14 verified defects, all fixed)
A multi-agent audit (adversarially verified; 6 false alarms refuted) found the safety gate was silently bypassed in the live checkout and JARVIS could overwrite its own safety code. All fixed + regression-tested:
- **P0** gate **fail-closed** + `people`-schema migration (the live bypass); **self-write firewall** (no writes inside the install tree) + write/create/move on RED_LIST; **computer-use gated** (`control_screen` red-list, honors panic/pause, `/api/agent` 409 when paused).
- **P1** AppleScript→RCE in `messages.py` closed (escape + strict handle regex); inbound WhatsApp/Telegram tagged `source="external"` + Telegram owner-gated on every message; 4 control-layer cloud sites routed through `make_client`.
- **P2** `panic()`/Undo truly reverts file ops (real inverses + pre-write snapshot; revert bypasses the gate but not the firewall).
- **Gates** offline-purity (no cloud LLM in the reasoning path unless `JARVIS_ALLOW_CLOUD_BRAIN=1`); `scripts/audit.py` rewritten for the local architecture (and no longer writes to the sacred vault).

## Post-audit hardening, round 2 — APPROVED (second deep audit: 18 verified defects, all fixed)
A second multi-agent audit probed the dimensions the first didn't (autonomy approve/execute loop, agent-loop robustness, concurrency, prompt-injection INTO the local brain, memory/vault integrity). 18 confirmed real (6 refuted); all fixed + regression-tested:
- **P0** red-list **always confirms** for autonomous/external sources even at home/auto (was only away/external — autonomous money/shell/delete auto-fired).
- **P1** prompt-injection containment (source taint-escalates to external after any untrusted-content read, so injected text can't drive an ungated red-list call); blocking `think()` never cascades to the cloud brain on a local hiccup (+ source threaded through cloud fallbacks); `forget_subject` now purges **all** stores (wiki vault + FAISS, observations.db, people + life tables, normalized fact keys); `consolidate_facts` is non-destructive (deletes only snapshotted ids + safety floor) and offline-gated.
- **P2** `approve()` atomic-claim (no concurrent double-execute) + pause-guard (no post-panic execution); panic/revert no longer oscillates on a double-press and reports honest counts.
- **P3** agent-loop + confirmation-queue dedup; default persona carries an anti-injection clause; vault/wiki FAISS search snapshots arrays under the lock.

## Build status: 350 tests green · all 9 phases + two rounds of post-audit hardening delivered + committed.
**Still needs the user (hardware/data/creds):** mic test (P2 TTS clone), camera enrollment (P3 biometrics), live account creds + VIP/family/blocklist data + `WHATSAPP_TOKEN` (P6 live), secret rotation (Order 0, done per user).
