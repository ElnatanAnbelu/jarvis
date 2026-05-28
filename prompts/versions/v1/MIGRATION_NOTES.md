# JARVIS Prompt System — v1 Migration Snapshot

**Date frozen:** Current session (initial creation of prompts/ system)

## What v1 Represents

This is the first modular, production-grade prompt architecture extracted and improved from the previous monolithic system prompts that lived in:

- `brain/think.py` (JARVIS_SYSTEM + large embedded context)
- `brain/free_agents.py` (VERONICA_PERSONA, KAREN_PERSONA, _FACTS_HEADER, _NO_CODE_RULE)
- `brain/gemini.py` (FRIDAY logic)

## Major Improvements in v1

1. **Anti-hallucination** is now a standalone, extremely strong module (`core/anti_hallucination.md`) with many concrete negative examples.
2. **Fallback hardening** (`fallbacks/`) was added specifically to address the critical finding from the May 2026 system inspection: weaker models were not receiving strong enough rules.
3. **Personas are now separate files** — much easier to iterate on one agent without touching others.
4. **Runtime composition** via `prompts/runtime/prompt_loader.py` so the same blocks can be assembled differently per model and per agent.
5. **Clear separation** between static context, live facts, and rules.

## How to Migrate Existing Code

### Step 1: In `brain/think.py`

Replace the giant `JARVIS_SYSTEM` string + `_build_context()` logic with:

```python
from prompts.runtime.prompt_loader import build_jarvis_prompt
from memory.memory import get_facts, get_recent_history  # adjust as needed

facts = get_facts() or ""
# ... build wiki and session summary the way you already do ...

system_prompt = build_jarvis_prompt(
    facts_block=facts,
    wiki_context=wiki,
    session_summary=summary,
    model=chosen_model,
)
```

### Step 2: Update all fallback paths

Every place that currently does:
```python
messages=[{"role": "system", "content": JARVIS_SYSTEM + ctx + ...}]
```

Should instead call the appropriate builder or at minimum append `get_fallback_directive(model)` when using Groq/Ollama/etc.

### Step 3: Do the same for free_agents.py and gemini.py

Use `build_veronica_prompt`, `build_karen_prompt`, `build_friday_prompt`.

## Rollback

If the new system causes problems, the old monolithic prompts are still in the git history. You can also copy the content from `versions/v1/` back into the agents as a temporary measure.

## Next Steps After Migration

- Run the CLI helper: `python prompts/runtime/build_system_prompt.py --agent JARVIS --model groq`
- Compare token count and quality vs the old prompt.
- Add prompt-level evaluation (future work).

## Security Addition (Post-v1)

After the initial v1 freeze, a `security/` folder was added containing:
- `tool_safety.md`
- `secret_handling.md` (especially important because this repo lives on GitHub)
- `computer_use_guardrails.md`

These should be included by default when using `compose_full_system_prompt(include_security=True)` (the new default).

This was done to directly address real security risks identified during the GitHub + tool safety audit.

This v1 is the foundation. Iterate from here.
