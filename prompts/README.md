# JARVIS Prompt Engineering System

**Folder:** `prompts/` — Modular prompt system for JARVIS (renamed from the original `promopt` typo)

This is the single source of truth for all prompts that power JARVIS, FRIDAY, VERONICA, and KAREN.

## Philosophy (Senior Prompt Engineer Standards)

- **Modular & Composable**: Never put everything in one giant string again. Prompts are built from small, focused, reusable blocks.
- **Model-Aware**: Different models need different prompt strength. Claude gets elegant instructions. Groq/Ollama/Mistral get hardened, repetitive, example-heavy versions.
- **Anti-Hallucination First**: The #1 failure mode in personal AI. Every prompt variant must make "I don't have that in my records, sir" the easiest and safest answer.
- **Personality Fidelity**: Each agent has a distinct voice that must survive temperature, model swaps, and long context.
- **Observable**: Every prompt block has a clear purpose, owner, and version.
- **Testable**: Prompts live alongside evaluation cases.

## Directory Structure

```
prompts/
├── README.md
├── core/                    # Universal rules that apply to everyone
│   ├── base_rules.md
│   ├── anti_hallucination.md
│   ├── output_formatting.md
│   └── tool_calling.md
├── personas/                # Distinct agent identities
│   ├── jarvis.md
│   ├── friday.md
│   ├── veronica.md
│   └── karen.md
├── context/                 # Dynamic + static knowledge blocks (lightened to reduce repetition)
│   ├── elnatan_profile.md
│   ├── business_context.md   # Significantly reduced static priming
│   ├── life_context.md
│   └── facts_injection_template.md
├── specialized/             # Task-specific instructions + Second Brain execution plan
│   ├── morning_briefing.md
│   ├── deep_research.md
│   ├── code_execution.md
│   ├── decision_framework.md
│   # Second Brain modules (added to realize the full observational + write autonomy vision)
│   ├── second_brain_execution_overview.md
│   ├── observational_logging.md
│   ├── second_brain_synthesis.md
│   ├── safe_vault_write.md
│   ├── personal_model_update.md
│   ├── self_capabilities_and_testing.md   # Includes awareness of existing tools/skills + testing instructions
│   └── latency_management.md
├── security/                # Critical safety & secret handling rules
│   ├── tool_safety.md
│   ├── secret_handling.md
│   ├── computer_use_guardrails.md
│   └── README.md
├── fallbacks/               # Hardened instructions for weaker models
└── runtime/                 # Prompt composition helpers
```

## Second Brain Modules

The following modules were added to implement the Second Brain concept (human as primary loader + JARVIS as intelligent observer + synthesizer + co-curator with write/update/organize capabilities driven by observation of emails, schedule, interests, conversations, etc.):

- `second_brain_execution_overview.md` — High-level strategy and principles (entry point for the detailed execution plan).
- `observational_logging.md` — How to capture and structure observations from life signals.
- `second_brain_synthesis.md` — How to turn observations + vault content into high-quality updates.
- `safe_vault_write.md` — Rules for writing/updating/organizing the vault safely and transparently.
- `personal_model_update.md` — Maintaining an evolving model of Elnatan in the Second Brain.
- `self_capabilities_and_testing.md` — Instructions for JARVIS to be aware of its own tools, skills, and prompt modules + testing new capabilities.
- `latency_management.md` — Guidelines for keeping the system responsive while doing deep Second Brain work.

These modules are designed to be used together as an interconnected execution plan. They emphasize:
- Human ownership of core brain quality
- Strong attribution and verification before writes
- Latency awareness
- Self-awareness of existing tools and skills
- Testing of new capabilities once implemented
│   ├── code_execution.md
│   ├── decision_framework.md
│   └── document_generation.md
├── fallbacks/               # Hardened versions for weaker models
│   ├── weak_model_directive.md
│   └── groq_optimized.md
├── runtime/                 # Python helpers to compose prompts at runtime
│   ├── prompt_loader.py
│   └── build_system_prompt.py
└── versions/
    └── v1/                  # Frozen snapshots for rollback + A/B testing
```

## Security Section (Important)

Because JARVIS has real tool access (shell, computer control, email, etc.) and runs on GitHub, the `security/` folder contains mandatory guardrails:

- `secret_handling.md` — Prevents accidental leakage of API keys or tokens (critical for open-source safety)
- `tool_safety.md` — Stops destructive actions without confirmation
- `computer_use_guardrails.md` — Extra caution for mouse/keyboard/screen agent mode

These should be included in prompts for JARVIS and any agentic/tool-heavy flows.

## How to Compose a System Prompt (Current Best Practice)

```python
from prompts.runtime.prompt_loader import build_jarvis_prompt

system_prompt = build_jarvis_prompt(
    model="claude-sonnet",
    include_business=True,
    include_life=True,
    strength="high"   # or "medium" for faster models
)
```

The loader intelligently:
- Uses the full elegant version for Claude
- Swaps in `fallbacks/weak_model_directive.md` + extra repetition for Groq/Ollama
- Always injects the latest facts block from memory
- Handles token budget awareness

## Key Improvements Over Previous Monolithic Prompts

1. **Anti-hallucination is now a first-class, versioned module** with concrete negative + positive examples that get reinforced in every fallback path.
2. **Output rules are separated** so formatting discipline can be applied even when the main persona is stripped in some fallbacks.
3. **Tool calling guidelines** are explicit and include "when NOT to call tools".
4. **Each agent persona is now a standalone file** — easier to iterate on one voice without touching others.
5. **Context is injected, not hardcoded** — `elnatan_profile.md` + facts DB win over static text in the prompt.

## Versioning & Migration

- `versions/v1/` contains the exact prompts that were extracted from the old `brain/think.py` + `free_agents.py` on the day this system was created.
- Never edit inside `versions/`. Treat it as immutable history.
- When you make meaningful changes, copy the current production set into a new `versions/v2/` folder and update the loader.

## Integration Plan (Recommended)

1. **Phase 1 (Immediate)**: Point `brain/think.py`, `brain/free_agents.py`, and `brain/gemini.py` to import from `prompts.runtime` instead of the giant inline strings.
2. **Phase 2**: Update all fallback paths to use the appropriate strength variant from `fallbacks/`.
3. **Phase 3**: Add prompt evaluation harness (see `runtime/eval/` in future).
4. **Phase 4**: Make the router classifier also prompt-driven (currently in `gemini.py`).

## Naming Conventions

- Files use `snake_case.md`
- Blocks meant for direct concatenation start with `## SECTION NAME`
- Use `{{VARIABLE}}` style for runtime templating (kept minimal)
- Every file has a 1-2 line "Purpose" comment at the very top

## Usage in Code (Example)

```python
# In brain/think.py (future state)
from prompts.runtime.build_system_prompt import build_for_jarvis

system = build_for_jarvis(
    user_input=user_input,
    model=chosen_model,
    facts_block=get_facts_block(),
    wiki_context=get_wiki_context()
)
```

## Contributing / Iteration Rules

- Change one block at a time.
- Test the change against both strong (Claude) and weak (Groq 70B + Ollama) paths.
- When personality drifts or hallucinations increase, the first place to look is `core/anti_hallucination.md` and the fallback variants.
- Never put personal facts directly into persona files — they belong in `context/` + the live facts DB.

---

**This system exists because the previous monolithic approach in `think.py` (300+ lines of system prompt) became unmaintainable and inconsistently applied across the fallback chain.**

You now have proper prompt architecture.

Next step: implement the runtime loader + migrate the existing prompts into these modules.

Status: **Foundation created — ready for content population and integration.**
