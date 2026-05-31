# JARVIS — Autonomous Life Operator + MCU HUD
### Master Specification

**Owner:** Elnatan Anbelu
**Status:** Approved plan → spec
**Last updated:** 2026-05-30
**Supersedes:** `spec.md` ("Make It Feel Human" overnight spec) as the project's north-star document. That spec remains valid for the voice/orb/HUD work it described, which is now treated as *built foundation* here.

---

## ⏰ DEADLINE & COMMITMENT — SHIP TONIGHT (by 2026-05-30 midnight)

**We are finishing the app tonight.** By midnight, JARVIS is a working, usable autonomous life operator — not a prototype.

### "Done tonight" = every box checked (the bar):
- [ ] **Boots clean** on Claude (health-gate confirms; no silent fallback).
- [ ] **Away-mode toggle works** — turning it on starts autonomous operation; `pause` stops it instantly.
- [ ] **Autonomous comms proven** — in away-mode, JARVIS triages incoming mail/messages, auto-replies the routine, escalates the rest. Demonstrated live, not just unit-tested.
- [ ] **Red-list holds** — every money/irreversible action is blocked and sent to Telegram for approval; nothing fires without a tap.
- [ ] **Telegram loop works** — `approve` / `reject` / `pause` / `status` all function end-to-end.
- [ ] **Everything reversible** — every autonomous action is in the ledger and `undo` works (UI + tool).
- [ ] **"While you were away" report** — JARVIS reports what it did via Telegram and the HUD view.
- [ ] **Always-on orb** — small, blue, corner-pinned, survives HUD open/close + app switches + full-screen.
- [ ] **Green** — full `pytest` suite + `scripts/audit.py` + new unit/integration/safety tests all pass.

That bar = Midnight Push Blocks A–D (§5). **If a box isn't checked, we're not done.**

### Explicitly NOT required tonight (do not block "done"):
Claude Agent SDK migration · money/browser *autonomous execution* (tools wired but confirm-only) · calendar/school/business domains (Block E stretch) · deeper "knows-me" learning.

### Non-negotiable under deadline:
**Money + irreversible actions never auto-fire — always Telegram-gated. Fast ≠ unsafe.** A block is not "done" until its tests are green.

---

## 1. Vision & Definition of Done

### 1.1 What we're building
JARVIS today is a **reactive** assistant: you talk, it responds, it calls tools, it has a voice-first orb + multi-agent HUD. The product we want is fundamentally different:

> **An autonomous life operator that runs Elnatan's life while he's away** — handling comms, calendar, school, business (Addis Market / Nexel), and money/browser tasks on its own — acting first and reporting after, with Telegram as the remote channel, all behind a voice-first MCU "Iron Man" HUD with a small blue orb that is *always present*.

### 1.2 Definition of "done done"
The system is complete when, with Elnatan away:
1. It **autonomously handles routine work** across all five domains (comms, calendar, school, business, money/browser).
2. It **asks before anything catastrophic or irreversible** (the red-list).
3. **Every action is logged and reversible** (black-box recorder + undo).
4. It **reports via Telegram** ("here's what I did") and accepts remote approve/reject.
5. It **continuously learns** Elnatan (observations → vault).
6. It presents as a **voice-first MCU HUD** with a persistent, always-on-top corner orb.

### 1.3 Current completeness (baseline, verified)
- Core plumbing: ~95% (159 tests pass, 125 tools register, all endpoints/imports OK).
- Voice + orb + HUD UI: production-ready (built).
- Memory infra (vault, proposals, staging): built and **populated**; the *gate* is wired.
- **The gap:** the system never *acts on its own*, has no safety net for autonomous action, the learning loop's synthesis worker is missing, and the brain is hand-rolled rather than on the Claude Agent SDK.

---

## 2. Architectural Decisions (locked)

| Decision | Choice | Rationale |
|---|---|---|
| **Autonomy level** | Full — "act, then tell me" | The product is "runs my everything while away." |
| **Safety substrate** | Mandatory, non-negotiable | Every action logged + reversible; a **red-list** of catastrophic/irreversible actions (large money movement, sends to high-stakes contacts, deletions, legal/contractual) requires Telegram confirmation even in full-autonomy mode. Full autonomy ≠ a loaded gun. |
| **Away-channel** | Telegram | Already wired for send + receive; we add an approval/report protocol. |
| **Brain** | Migrate JARVIS path to **Claude Agent SDK** | Long-running agents, subagents, native tool loop + caching + compaction — exactly what autonomy needs. Keep tool registry, 4-agent routing, fallback chain, prompt composer. |
| **Other agents** | FRIDAY/VERONICA/KAREN stay on Gemini | Cost/latency; only JARVIS needs the SDK. |
| **UI** | MCU HUD, voice-first, persistent corner orb | Polish on an existing working UI, not a rebuild. |
| **Orb behavior** | Always-on-top, decoupled from HUD | Orb is a system-wide floating companion — visible over all apps and even when the full HUD is open. Never hides, moves, or embeds in the HUD. |

---

## 3. System Architecture

### 3.1 Subsystems (existing, mapped)
- **Brain** (`brain/think.py`, `brain/router.py`) — reasoning loop, model/agent routing, fallback chain. God-node: `VaultManager`.
- **Tools** (`brain/tools/` — registry + 11 domain modules, 125 tools) — model-agnostic `@tool` registry; `execute_tool` dispatch with per-agent access control + action logging.
- **Memory / Second Brain** (`memory/vault.py`, `memory/observations.py`, `memory/memory.py`) — Obsidian vault at `~/Documents/SecondBrain/`, risk-tiered proposal system, observation staging, SQLite (`jarvis.db`) for conversations/facts/actions/scheduled tasks.
- **Proactive** (`brain/proactive.py`, `brain/observer.py`, `brain/briefing.py`) — schedule-based background tasks (currently text-alert only), insight engine with quiet hours, daily briefings.
- **Away-channel** (`telegram_bot.py`) — send (text + voice briefings) + receive (routes to agents); no approval flow yet.
- **Control** (`control/computer_agent.py`, `control/code_executor.py`) — vision-loop computer use with action allowlist + destructive-key gate; multi-language code execution (no FS sandbox yet).
- **UI** (`app/bubble.html` orb, `app/jarvis.html` HUD, `app/main.py` pywebview shell + JsApi bridge) — voice-first, [SHOW:] surface, always-on orb window.
- **Voice** (`voice/wake.py`, `voice/listen.py`, `voice/speak.py`) — wake word (openwakeword + energy-gate fallback), VAD recording → Groq Whisper, TTS (ElevenLabs → edge-tts → Kokoro).
- **Prompts** (`prompts/` + `prompts/runtime/prompt_loader.py`) — modular, versioned, composed per agent.

### 3.2 New components introduced by this spec
- **Reversible action ledger** — extends `actions_performed` with an inverse/compensating action per entry; `revert_action(id)` + `tool_undo()`.
- **Risk gate** — `risk` level on every tool; red-list block-and-confirm in `execute_tool`.
- **Away-mode + quiet hours** — global state honored across proactive paths.
- **Autonomous task runner** — goal-driven agentic runner (SDK subagent) that plans → calls tools → completes, gated by the safety substrate.
- **Telegram approval/report protocol** — `approve/reject/pause/status` commands + "what I did" digests.
- **Observations synthesis worker** — reads staged observations → writes vault proposals.
- **"While you were away" control room** — HUD + Telegram view of ledger actions with per-action undo.

---

## 4. Phased Plan (full vision)

> Phases 0→1→2 are strictly ordered (safety before autonomy; SDK before building autonomy on it). Phases 3, 4, 5 can proceed in parallel once 2 lands.

### Phase 0 — Foundation & Safety Substrate
*Prerequisite for everything. Nothing autonomous ships until this exists.*

- **Guarantee Claude.** `_get_auth_key()` (`brain/think.py:730-738`) already supports API key + keychain OAuth. Add a **startup health-gate** (`app/main.py` boot ~647) that verifies the primary Claude path authenticates and **announces loudly** on fallback to Groq/Gemini instead of silently degrading.
- **Reversible action ledger.** Extend `actions_performed` (`memory/memory.py:364-373`, written from `brain/tools/registry.py:88-99`) to store an inverse action where one exists (sent-email → retract/follow-up; file write → backup path; vault note → proposal-reject). Add `revert_action(action_id)` + `tool_undo()`.
- **Risk tagging + red-list gate.** Add `risk` to the `@tool` decorator (`registry.py:14-47`). In `execute_tool`, `risk="red"` while away-mode is on → **block-and-confirm via Telegram** (reuse confirm pattern `control/computer_agent.py:92-97`).
- **Away-mode + quiet hours.** Global flag (`.env` / SQLite `meta`). `brain/proactive.py:_send` (24-42) + scheduler (229-252) must honor quiet hours (today only `brain/observer.py:86-101` does).

**Acceptance:** boot proves Claude is live; `tool_undo()` reverses a test file-write; a `risk="red"` tool in away-mode produces a Telegram confirm and does nothing until approved; 159 existing tests stay green.

### Phase 1 — Migrate JARVIS brain to the Claude Agent SDK
- **Replace:** the hand-rolled loop `_think_sdk` (`brain/think.py:783-833`), `_build_anthropic_tools` (750-766), `_build_cached_system` (769-780), and manual streaming/history in `think_stream` (1321-1417). The SDK handles the multi-round tool loop, caching, streaming, conversation state.
- **Keep & feed into the SDK:** tool registry + `execute_tool` (`registry.py`), `select_model`/`_jarvis_model` routing (`think.py:661-683`, `router.py:69-85`), `compose_full_system_prompt` (`prompt_loader.py:105-154`) as system prompt, and the full fallback chain (Grok→Groq→Mistral→Ollama, `think.py:1188-1319`) wrapping the SDK call.
- **Preserve auth flexibility** (`_make_client` 741-748): both API key and keychain OAuth.
- **Boundary:** only the JARVIS path moves; FRIDAY/VERONICA/KAREN stay on Gemini.

**Acceptance:** streaming chat through `route_stream` works via the SDK; tool calls execute through the same registry; killing the Claude key still engages fallbacks; think/router tests pass.

### Phase 2 — Autonomy Engine ("run my everything while away")
- **Autonomous task executor.** Replace text-only proactive tasks with a goal-driven agentic runner (SDK subagent) that plans → calls tools → completes, gated by Phase 0. Extend the `scheduled_tasks` schema (`memory/memory.py:49-58`) with `goal` + `autonomy_level`.
- **Telegram approval + report protocol.** Add `approve <id>` / `reject <id>` / `pause` / `status` parsing to `telegram_bot.py:handle_message` (119-143), wired to the red-list gate + vault proposals (`memory/vault.py:approve_proposal` 491-553). Push "what I did while you were away" digests via `_send_briefing` (79-109).
- **Away-session loop.** In away-mode, JARVIS scans each domain's queue on a cadence, acts on routine, queues red-list items for approval, logs everything to the ledger + vault `_Activity`.

**Acceptance:** away-mode + seeded routine email + a payment → routine handled autonomously, payment sent to Telegram for approval, end-of-window report produced; every action in the ledger and individually revertible.

### Phase 3 — Domain coverage
Tools largely exist; work = orchestration + per-domain red-list rules.
- **Comms** (`brain/tools/messaging.py`): triage, draft, auto-reply routine, escalate important. Red-list: sends to flagged VIP contacts.
- **Calendar** (`brain/tools/calendar.py`): book/reschedule/remind. Red-list: cancelling/declining external commitments.
- **School** *(new `brain/tools/school.py` + vault `School/` area)*: deadlines, assignment tracking, school-email triage, portal checks via the computer agent.
- **Business — Addis Market / Nexel** (`brain/tools/business.py`, 32 tools): follow-ups, CRM upkeep, financial briefings. Red-list: moving money / committing to deals.
- **Money + browser** (`control/computer_agent.py`): spending/bills tracking; browser task completion. **Highest risk** — requires FS sandbox in `code_executor.py`, coordinate-bounds checks in `computer_agent.py`, and red-list on **all** transactions.

**Acceptance:** one end-to-end autonomous scenario per domain, each showing routine-handled-silently vs red-list-confirmed, all reversible.

### Phase 4 — MCU HUD polish (voice-first, persistent corner orb)
- **Orb = persistent system-wide companion.** Its own always-on-top window (`app/main.py:677-693`, `on_top=True`, frameless, transparent), **decoupled from the HUD**. Stays pinned/visible over every app and **even when the full HUD is open**. The HUD (`app/jarvis.html`) is an *optional* panel summoned via the orb's expand button (`toggle_hud()`, main.py:103); opening/closing it must never hide, move, or absorb the orb.
- **Keep the orb small + blue** (~78px, window 150×150 bottom-left). Voice stays primary (conversation mode + VAD built). No full-screen orb, no embedding in the HUD.
- **MCU aesthetic pass** toward `docs/archive/original-vision/hud-multi-agent-design-spec.md`: agent-personality motion, workspace tint, holographic styling.
- **"While you were away" control room** (HUD + Telegram parity): what JARVIS did, what's pending approval, per-action **undo** (surfaces the Phase 0 ledger).
- **[SHOW:] surface** already exists — use it for autonomous-action summaries.

**Acceptance:** orb stays corner-pinned + blue across HUD open/close, focus changes, and full-screen apps; voice round-trip works; away-report view lists real ledger actions and undo works from the UI.

### Phase 5 — Continuous "knows me" learning
- **Observations synthesis worker (the missing piece).** `memory/observations.py` stages life-signals with a quality filter but nothing synthesizes them. Build a scheduled worker that reads pending observations, clusters them, and writes vault proposals via `VaultManager.propose_change` (`memory/vault.py:335-469`) — high-risk areas proposal-gated, low-risk auto-approve (tiers exist, vault.py:21-41).
- **Deepen personal-context decision.** `_should_query_personal` (`brain/think.py:497-516`) is shallow keyword scoring; upgrade to cheap semantic judgment using the vault's FAISS index (vault.py:682-721).
- **Seed `_PersonalModel.md`** (currently a 2.2KB stub) from the synthesis worker.

**Acceptance:** a multi-day signal (e.g. repeated mentions of an exam) produces a vault proposal; in a cold conversation JARVIS recalls a true, relevant fact unprompted and writes a new retrievable one.

---

## 5. TONIGHT — Midnight Push (execution order)

**Reality:** the full P0–P5 vision is a multi-week build. The **Claude Agent SDK migration (Phase 1) is DEFERRED** past tonight — too risky to rush under a brain that already works. Tonight drives the autonomy vision as far as 6 hours safely allows, on the *existing* hand-rolled brain. **Hard rule kept under deadline: money + irreversible actions stay Telegram-confirmation-gated — never auto-fired.**

Each block is independently shippable; if the clock runs out mid-block, everything before it still works and is tested. **Run the relevant tests after each step before moving on.**

**Block A — Safety substrate (~75 min)**
1. Claude health-gate at boot; set the key/OAuth so JARVIS runs on Claude.
2. Reversible action ledger + `tool_undo()` / `revert_action(id)`.
3. `risk` tag on `@tool` + red-list gate in `execute_tool`.
4. Away-mode flag + quiet hours honored by the proactive scheduler.

**Block B — Telegram away-channel (~45 min)**
5. `approve/reject/pause/status` parsing in `handle_message`, wired to red-list + vault proposals.
6. "What I did" digest via `_send_briefing`.

**Block C — Autonomy engine + Comms (~120 min)**
7. Goal-driven autonomous task runner (extends proactive dynamic tasks; `goal` + `autonomy_level`), gated by Block A.
8. Comms domain live: away-mode scans/triages email+messages, auto-replies routine, escalates VIP (red-list). The "it actually runs my stuff" proof.

**Block D — Always-on orb + away-report UI (~45 min)**
9. Make the orb's decoupled always-on-top behavior explicit (survives HUD open/close, focus, full-screen).
10. "While you were away" view (HUD + Telegram) with per-action undo.

**Block E — Stretch (only if A–D green): more domains**
11. Calendar, then School. **Money + browser autonomy NOT auto-enabled tonight** — wire the tools but leave every transaction/computer-action red-listed (confirm-only) until proper hardening.

**Continuous:** keep the full `pytest` suite green; commit each green block on the `feat/autonomous-life-operator` branch.

---

## 6. Testing Plan (everything)

Run via the project venv: `./venv/bin/python -m pytest`. Tests are written **alongside** each block, not after. Tiered: smoke → unit → integration → end-to-end → safety → manual.

### 6.0 Pre-flight smoke (first + after every block)
- `./venv/bin/python -m pytest -q` → **159 baseline tests stay green** all night (zero regressions).
- `scripts/audit.py` passes: endpoints 200, core imports OK, 125 tools register, Claude key live (no longer "NOT SET"), voice chain + vault OK.
- App boots; orb appears; one voice round-trip (wake → listen → think → speak) succeeds.

### 6.1 Unit (mocked externals)
- **Ledger/undo:** every recorded action yields a valid inverse; `revert_action` reverses a file-write and a vault note; safe no-op when no inverse exists.
- **Risk gate:** `risk="red"` + away-mode → confirm-pending, does NOT execute; low risk → executes; `allowed_agents` still enforced.
- **Away-mode + quiet hours:** `_send` suppresses inside quiet window; scheduler respects flags.
- **Telegram parser:** `approve/reject/pause/status` parse; malformed/unknown id handled; reject leaves system unchanged.
- **Autonomous runner:** given a goal, produces a tool plan; honors max-step cap; routes red-list to confirm.
- **Observations synthesis** (if reached): pending observations → vault proposal in correct risk tier.

### 6.2 Integration (real components, fake outbound)
- Scheduler → runner → `execute_tool` → ledger: a scheduled goal runs end-to-end and lands in the ledger.
- Telegram `approve <id>` → executes held red-list action → ledger updated → confirmation sent (API mocked).
- Telegram `reject <id>` → action discarded, nothing executed.
- Kill the Claude key mid-run → fallback chain engages and the health-gate warns.

### 6.3 End-to-end per domain (away-mode, sandboxed/test accounts)
- **Comms:** routine email auto-replied (to a test address), VIP email escalated to Telegram, both in ledger.
- **Calendar:** conflict auto-resolved; external cancellation confirm-gated.
- **School:** deadline/portal item tracked + summarized.
- **Money/browser:** confirm-gate fires on **every** transaction/computer action — assert nothing auto-executes; undo available.

### 6.4 Safety / adversarial (the tests that matter most)
- Red-list cannot be bypassed by any away-mode path — prompt-injection in an email body must NOT trigger an unconfirmed money/send action.
- `pause` is an immediate kill-switch: no further autonomous actions fire.
- Every autonomous action is in the ledger AND reversible; undo from the UI works.
- Quiet hours fully silence proactive sends.

### 6.5 UI / voice (manual checklist)
- Orb stays pinned + blue across HUD open/close, switching apps, and full-screen apps; never hides or embeds in the HUD.
- Wake word → conversation mode → VAD auto-stop → streamed reply → TTS → re-arm.
- `[SHOW:]` surface renders; "while you were away" view lists real ledger entries; per-action undo works.

### 6.6 Regression gate (before declaring "done")
Full `pytest` green + `scripts/audit.py` clean + all new unit/integration tests green + the safety suite green + the manual UI/voice checklist signed off. **A block is not "done" until its tests pass — no green, no merge.**

---

## 7. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Autonomous action causes real-world harm (wrong email, money moved) | Red-list confirm gate + reversible ledger + `pause` kill-switch + away-mode scoping. Money/browser stay confirm-only until hardened. |
| Prompt injection via email/web content triggers an action | Red-list applies to *outbound/irreversible* actions regardless of trigger; adversarial test suite (6.4). |
| Code executor / computer agent escapes scope | FS sandbox (Phase 3) + coordinate-bounds checks + existing destructive-key gate. |
| SDK migration destabilizes a working brain | Deferred past tonight; fallback chain + registry preserved; done behind tests. |
| Silent degradation to weak models | Startup Claude health-gate announces loudly. |
| Doc drift / stale status | Single `STATUS.md` regenerated by `scripts/audit.py` (see §8). |

---

## 8. Cross-cutting Cleanup
- Collapse the 5+ overlapping status docs into one `STATUS.md` regenerated by `scripts/audit.py`; wire the audit into a pre-push hook.
- Keep the `JARVIS.app` rebuild out of source commits (currently a churning binary in git).

## 9. Sequencing Summary
`0 → 1 → 2` strictly ordered. `3, 4, 5` parallelizable after `2`. Fastest path to feeling the vision: **0 → 1 → 2 + one domain from 3**, then UI polish (4) and deeper learning (5). Tonight: **A → B → C → D**, with **E** as stretch.
