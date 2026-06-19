# Alfred — Build Punch-List (deferred you-gates + follow-ups)

The nonstop build defers anything that needs Elnatan (or a model/training run, or a
coordinated risky pass) into this queue instead of stopping. Each item: what it is,
why it was deferred, and what unblocks it. Cleared at go-live.

## Needs YOU (human-in-the-loop — can't be built) — most now have a wizard
> Run `./venv/bin/python scripts/setup.py` — it walks you through PIN, iMessage handle,
> credentials (→ Keychain), and people. The *flow* is built; only your data is yours to enter.
- [ ] **Mic test** — speak end-to-end: wake ("Alfred") → STT → reply → voice. Confirms the loop on your hardware. *(P1)*
- [ ] **Caine/Alfred voice sample** — a clean clip to clone the butler voice locally. *(P1)*
- [ ] **Camera + voice enrollment** — enroll your face + voiceprint so biometric/presence identity works. *(identity / P5)*
- [ ] **Live credentials** — Gmail/Notion/WhatsApp tokens → enter via the wizard (into the Keychain; I never type your secrets). *(P7)*
- [ ] **People data** — VIP / family / blocklist → enter via the wizard. *(P2/P7)*
- [ ] **iMessage Full Disk Access** — grant Terminal/Python FDA in System Settings → Privacy so Alfred can read new owner messages (the primary away-channel). *(P6)*
- [ ] **Business descriptions / Goals** — what Addis Market + Nexel need + your goals, so the domains + proactivity are grounded. *(P7)*

## Needs a model / training run
- [ ] **"Hey Alfred" neural wake model** — OPTIONAL upgrade. The wake *word* is already "Alfred":
      the default offline path = energy-gate + local-Whisper keyword match, which wakes on "Alfred"
      today with no cloud. A custom openwakeword model only sharpens always-on neural detection —
      drop one in and set `ALFRED_WAKE_MODEL=/path/to/alfred.onnx`. *(P1)*
- [ ] **Model swap** — pull `qwen3:8b` (fast) + `qwen2.5-coder:14b` (coder), repoint `brain/llm.py`,
      `ollama rm qwen2.5:7b` (keep `qwen3:14b`). ~14GB download — only on your "do it". *(P1 / brain)*
- [ ] **Fine-tune ("make it ours")** — LoRA on your data → re-quantize → GGUF. Needs your data + a GPU run. *(Path B track)*

## Shipped this run (for context)
- ✅ **P0** — latency SLA harness (live: first-token p95 0.27s, reply p95 1.88s — well under budget).
- ✅ **P1 (core)** — brain persona rebranded to Alfred.
- ✅ **P2** — money gate: PIN required on any payment ≥ ~$100.
- ✅ **P5 (portable self)** — `memory/export.py` exports/imports Alfred's durable memory as one bundle.
- ✅ **Money-PIN surface wiring** — Telegram `approve <id> [pin]`, `/api/approve` `pin`, and the
      control room prompts for the PIN and only reports success when the move actually executes.
- ✅ **Full Alfred rebrand + offline wake** — wake word "Alfred" (offline-first, local Whisper),
      voice speaker key, control room / orb / HUD brand + labels, router accepts "Alfred", Telegram
      push header, gate messages, observer/market/reader/research/audit personas, server banner +
      open-greeting. Load-bearing internals (jarvis.db, JARVIS_* env, X-JARVIS-Token, the internal
      'JARVIS' dispatch key + allowed_agents, Keychain service) intentionally KEPT to avoid breakage.
      Live-verified: `/control` shows ALFRED; `/api/chat` replies "I am Alfred …".
- ✅ **P6 iMessage primary away-channel** (`imessage_channel.py`) — owner texts Alfred; reads new
      owner messages from chat.db (read-only), same owner-command set as Telegram, free text routes
      source='external' (gated), owner-handle allowlist is the spoofing guard, off until configured.
      Proactive notifications now prefer iMessage, fall back to Telegram (the fail-safe).
- ✅ **Offline purity** — wiki memory-extractor runs on the LOCAL model (Groq only as opt-in fallback);
      computer-use vision loop gated behind the cloud opt-in. No cloud LLM in the default path anywhere.
- ✅ **Onboarding wizard** (`scripts/setup.py`) — owner-run setup for PIN / iMessage / creds / people.
- ✅ **Self-dev orchestrator** (`brain/self_dev_runner.py`) — owner+identity-gated implement→branch→
      test→diff→revert; protected paths refused; isolated branch, never auto-merged, fully reversible.
      414 tests green; audit clean; eval GATE PASS.
