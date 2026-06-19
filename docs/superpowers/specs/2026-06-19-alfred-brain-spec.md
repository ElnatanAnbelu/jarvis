# Alfred — Brain & Capability Spec (PLAN ONLY)

_Captured from the capability interrogation (2026-06-19). How Alfred's brain is sized, made smart at hard problems, made to "know everything," and how it grows. Companion to the master plan + build-detail. No code built until approved._

## Form factor (LOCKED)
- **Compact, portable brain — runs on the Mac AND a phone.** Target a top small model (~3–7B class) so it runs anywhere; optionally a **two-tier** setup (a bigger ~14B-class brain on the ~32GB Mac, a tiny one on phone/other devices) sharing **one memory + persona**.
- **4-bit quantized** for size + speed + low RAM. Brain stays RAM-light; knowledge lives on cheap SSD.
- **Dial = "all at once"** (fast + smart + compact), achieved at the **system** level (small SOTA model + quantization + tools + RAG + adaptive thinking + fine-tune), not by a giant model.
- **RAM vs SSD reality:** RAM is the ceiling on brain size (32GB Mac ⇒ up to ~14B; phone ~6–12GB ⇒ ~3B). SSD is cheap/plentiful and holds the model file + the offline knowledge library.

## Smart at hard problems — coding, math, physics, logic (ALL — LOCKED)
The levers that make a *local* model strong at complex work:
1. **Reasoning/code-specialized base** (Qwen-Coder / DeepSeek-Coder/Math / a thinking model) — the #1 lever.
2. **Tools, not guessing — it executes:** code sandbox (write→run→test→fix), SymPy/symbolic math, calculator. Reliable math/physics/code beyond raw IQ.
3. **Verification loops:** run tests, check units, re-derive. Correctness over one-shot.
4. **Adaptive difficulty routing:** easy → fast tier (instant); hard → heavy "thinking" tier (slower, deeper). Latency stays low day-to-day (his #1 dealbreaker).
5. **Fine-tune on his domains** for the kinds of problems he actually does.
- **Coding depth:** ALL of it — one-liners → full projects, build/run/debug/ship (risky bits gated).
- **Correctness posture:** **adaptive** — instant on easy, deep + tool-verified on hard.
- **Proof of a hard answer:** **adaptive** — quietly confident on easy; runs it + shows the verification (tests passing / units checking) on the hard/risky.

## "Knows everything" = retrieval, not weights (LOCKED)
- **Parametric:** the quantized model already holds compressed world knowledge (runs offline natively, frozen at training cutoff, lossy).
- **Offline depth = a local reference library on SSD** (Wikipedia ~15–30GB text via Kiwix/ZIM, textbooks, docs, code) + the **Second Brain**, indexed for local RAG. Fully offline.
- **Online = + live web/tools.**
- Owner wants it **compact/portable**, so knowledge sits on SSD (big, cheap) while the brain stays small (RAM-light). "Literally every fact, always current, offline" is not physical (petabytes, ever-changing); "the vast majority of useful reference knowledge offline" is.
- **Offline-pack size:** TBD with owner (he reframed to "compact the LLM"); default plan = a curated local library scaled to the disk budget.

## "No limit / can do anything" — honest reconciliation (LOCKED stance)
- The **model's raw IQ has a ceiling**; the **system's reach does not.** Full laptop control + research + code/math execution + verification means it **offloads hard parts to tools** and can *attempt anything*.
- The only true wall is raw reasoning on the genuinely-hardest problems with no tool to lean on — shrunk to near-nil by tools+RAG, and covered by the **optional cloud opt-in** (owner's explicit choice) if ever flipped on.
- **No *artificial* limits:** no cap on effort, tools, or research.

## Comprehends "both brains" (LOCKED)
- **Him:** a deep, intelligent model of Elnatan — mind, patterns, decisions (the Second Brain made genuinely smart about him).
- **Itself:** understands its own code/architecture well enough to extend itself (feeds gated self-dev).

## Self-extension (LOCKED — via the safe pipeline)
- Alfred **writes + edits its own code / builds its own tools** — through **gated self-dev (P3)**: owner request → branch/worktree → implement → tests+eval+latency gate → diff → owner approve → ship → reversible.
- HARD invariant: it can **never** touch its own safety gate / secrets / credential vault, and **never** self-modifies from autonomous or injected triggers. Self-improving, not unleashed.

## Research (LOCKED)
- **All, by need** — quick lookups when quick'll do; **autonomous deep multi-source, cited research** when it matters (online); local-corpus research offline.

## Growth model — "better every day" (LOCKED)
- **Memory compounds** (knows him more each day) + **periodic fine-tunes** on his data + **swap in better open base models as they ship** (model-agnostic, portable self) + **self-built tools** (gated self-dev).
- This is how it gets smarter — system-level, riding the open-model tide — **not** retraining a frontier model from scratch (a $50–100M+, thousand-GPU, months-long job that is impossible on a laptop and would come out *worse* than free open models). That path is explicitly OUT.

## Final Model Lineup (LOCKED — research-picked, no benchmark race per owner)
Researched against the case (M5/32GB, no-lag, coding-first, fine-tunable, offline, Apache-2.0). One Qwen family across the whole ladder → one tokenizer + one fine-tune recipe.

| Tier | Model | ~RAM (4-bit) | Role |
|---|---|---|---|
| Fast / everyday | **Qwen3-8B** (`qwen3:8b`) | ~5–6GB | default brain: tool-calling, chat, routine reasoning; instant on M5 |
| Reasoning / smart | **Qwen3-14B** (`qwen3:14b` — already installed, KEEP) | ~9GB | hard math/physics/logic; thinking gated + reasoning-token-capped |
| Coder / complex | **Qwen2.5-Coder-14B** (`qwen2.5-coder:14b`) | ~9GB | write/run/debug whole projects; FIM + tools; easiest to fine-tune into "ours" |
| Phone | **Qwen3-4B-Thinking-2507** (`qwen3:4b-thinking`) | ~2.5GB | compact shared-persona variant; phone-runnable |

- **Owner decision: NO benchmark race** — commit to the research pick directly. No-lag is the priority, so the coder is the dense **Coder-14B** (roomy on 32GB, easy fine-tune), NOT the RAM-tight MoE.
- **Future "push it" option (optional, later):** Qwen3-Coder-30B-A3B (MoE) — best coding, ~18GB resident, only if RAM headroom proves fine under the full stack.
- **Serving:** prefer **MLX** on Apple Silicon (~20–40% faster) where practical; Ollama otherwise.
- **The swap — executed at BUILD time, NOT now:**
  1. `ollama pull qwen3:8b` + `ollama pull qwen2.5-coder:14b` (+ later `qwen3:4b-thinking`).
  2. `brain/llm.py`: FAST_MODEL → `qwen3:8b`; keep COMPLEX_MODEL → `qwen3:14b`; add a coder route → `qwen2.5-coder:14b`.
  3. `ollama rm qwen2.5:7b` (superseded fast tier); **keep `qwen3:14b`**.
  - Fully reversible (models re-pullable). Nothing is downloaded/deleted until the build phase is approved.
- **Ignore unverified "2026" models** (Qwen3.5 / Gemma-4 / DeepSeek-V4 SEO ghosts) until weights are actually on HuggingFace/Ollama; a real one would be a drop-in family upgrade.

## Honest constraints (stated, accepted)
- **Compact/portable ↔ raw-smart** trade off; mitigated by small-SOTA-model + quant + tools + RAG + fine-tune + (Mac tier / cloud opt-in for the hardest).
- **Frontier-genius raw reasoning on a phone** is not physical; the system (tools/RAG/verification) closes most of the gap.
- Local parametric knowledge is frozen at cutoff; currency comes from RAG + web.
