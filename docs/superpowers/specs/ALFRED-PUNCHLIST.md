# Alfred — Build Punch-List (deferred you-gates + follow-ups)

The nonstop build defers anything that needs Elnatan (or a model/training run, or a
coordinated risky pass) into this queue instead of stopping. Each item: what it is,
why it was deferred, and what unblocks it. Cleared at go-live.

## Needs YOU (human-in-the-loop — can't be built)
- [ ] **Mic test** — speak end-to-end: wake → STT → Alfred reply → voice. Confirms the voice loop on your hardware. *(P1)*
- [ ] **Caine/Alfred voice sample** — a clean clip to clone the butler voice locally. *(P1)*
- [ ] **Camera + voice enrollment** — enroll your face + voiceprint so biometric/presence identity works. *(identity / P5)*
- [ ] **Live credentials** — Gmail/Google OAuth, Notion token, WhatsApp token — YOU enter them into the encrypted vault (I never type your secrets). *(P7)*
- [ ] **People data** — VIP / family / blocklist contacts for the contact-aware gate. *(P2/P7)*
- [ ] **Business descriptions** — what Addis Market + Nexel are/need, so the business domain is grounded. *(P7)*
- [ ] **Goals** — confirm the goals in your Second Brain so proactivity aligns to them. *(P7)*

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
      Live-verified: `/control` shows ALFRED; `/api/chat` replies "I am Alfred …". 397 tests green.
