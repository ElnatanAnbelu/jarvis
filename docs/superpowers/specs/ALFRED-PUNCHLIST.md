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
- [ ] **"Hey Alfred" wake word** — needs a custom openwakeword model (prebuilt is `hey_jarvis`); current wake word stays "Hey JARVIS" until then. *(P1)*
- [ ] **Model swap** — pull `qwen3:8b` (fast) + `qwen2.5-coder:14b` (coder), repoint `brain/llm.py`, `ollama rm qwen2.5:7b` (keep `qwen3:14b`). ~14GB download — only on your "do it". *(P1 / brain)*
- [ ] **Fine-tune ("make it ours")** — LoRA on your data → re-quantize → GGUF. Needs your data + a GPU run. *(Path B track)*

## Coordinated / careful passes (buildable, deferred for safety)
- [ ] **UI speaker-label + full string rebrand** JARVIS→Alfred — the frontend matches on the name, so this is a coordinated pass, not a string-swap. *(P1)*
- [ ] **UI/Telegram PIN collection** — surface wiring so the approve flow can collect + pass the PIN for money ≥ $100 (gate logic already enforces it). *(P2)*

## Shipped this run (for context)
- ✅ **P0** — latency SLA harness (measured: first-token ~0.2s, reply ~1.5s — well under budget).
- ✅ **P1 (core)** — brain persona rebranded to Alfred.
- ✅ **P2** — money gate: PIN required on any payment ≥ ~$100.
