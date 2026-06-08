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
## Block B — Telegram away-channel — NOT STARTED
## Block C — Autonomy engine + Comms — NOT STARTED
## Block D — Always-on orb + away-report — NOT STARTED
