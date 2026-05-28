"""
Prompt Loader for JARVIS Prompt Engineering System

This module provides clean functions to compose system prompts from the modular prompts/ library.
"""

from pathlib import Path
from typing import Literal, Optional

PROMPT_ROOT = Path(__file__).parent.parent


def _read(rel_path: str) -> str:
    """Read a prompt file relative to prompts/ root."""
    full_path = PROMPT_ROOT / rel_path
    if not full_path.exists():
        return f"[MISSING PROMPT FILE: {rel_path}]"
    return full_path.read_text().strip()


def load_core() -> str:
    """Load all universal core rules."""
    parts = [
        _read("core/base_rules.md"),
        _read("core/anti_hallucination.md"),
        _read("core/output_formatting.md"),
        _read("core/tool_calling.md"),
    ]
    return "\n\n".join(parts)


def load_persona(agent: Literal["JARVIS", "FRIDAY", "VERONICA", "KAREN"]) -> str:
    """Load the persona file for a specific agent."""
    mapping = {
        "JARVIS": "personas/jarvis.md",
        "FRIDAY": "personas/friday.md",
        "VERONICA": "personas/veronica.md",
        "KAREN": "personas/karen.md",
    }
    return _read(mapping[agent])


def load_context(include_profile: bool = True, include_business: bool = True, include_life: bool = True) -> str:
    """Load static context blocks."""
    parts = []
    if include_profile:
        parts.append(_read("context/elnatan_profile.md"))
    if include_business:
        parts.append(_read("context/business_context.md"))
    if include_life:
        parts.append(_read("context/life_context.md"))
    return "\n\n".join(parts)


def load_business_context() -> str:
    """Load just the business context block — used for dynamic injection
    on business-relevant queries (see brain/think.py _is_business_query)."""
    return _read("context/business_context.md")


def build_facts_block(facts: str, wiki: str = "", session_summary: str = "") -> str:
    """Inject live facts into the official template."""
    template = _read("context/facts_injection_template.md")
    return (
        template
        .replace("{FACTS_BLOCK}", facts or "(No specific facts recorded yet)")
        .replace("{WIKI_CONTEXT}", wiki or "(No wiki entries yet)")
        .replace("{SESSION_SUMMARY}", session_summary or "(No previous session summary)")
    )


def get_specialized(task: str) -> str:
    """Load a specialized task prompt (e.g. 'morning_briefing')."""
    return _read(f"specialized/{task}.md")


def get_fallback_directive(model_hint: str = "weak") -> str:
    """Load the appropriate hardened fallback instructions."""
    if "groq" in model_hint.lower():
        return _read("fallbacks/groq_optimized.md") + "\n\n" + _read("fallbacks/weak_model_directive.md")
    return _read("fallbacks/weak_model_directive.md")


def load_second_brain_modules() -> str:
    """Load core Second Brain guidance for when JARVIS is doing vault work."""
    parts = [
        _read("specialized/second_brain_execution_overview.md"),
        _read("specialized/safe_vault_write.md"),
        _read("security/second_brain_vault_writes.md"),
    ]
    return "\n\n".join(p for p in parts if not p.startswith("[MISSING"))


def load_security() -> str:
    """Load all security modules (tool safety, secret handling, computer use guardrails)."""
    parts = [
        _read("security/tool_safety.md"),
        _read("security/secret_handling.md"),
        _read("security/computer_use_guardrails.md"),
    ]
    return "\n\n".join(parts)


def compose_full_system_prompt(
    agent: Literal["JARVIS", "FRIDAY", "VERONICA", "KAREN"] = "JARVIS",
    facts_block: str = "",
    wiki_context: str = "",
    session_summary: str = "",
    model: str = "claude",
    include_static_context: bool = True,
    include_business: bool = True,
    specialized_task: Optional[str] = None,
    include_security: bool = True,
) -> str:
    """
    Main composition function.

    This is the recommended way to build system prompts going forward.

    include_business=False excludes the static business_context.md from
    the prompt. Callers (e.g. brain/think.py) inject business context
    dynamically only on business-relevant queries — see _is_business_query.
    """
    sections = []

    # 1. Core rules (always)
    sections.append(load_core())

    # 2. Persona
    sections.append(load_persona(agent))

    # 3. Static context (optional; business excluded by default for JARVIS
    #    to reduce constant Addis Market priming — injected dynamically)
    if include_static_context:
        sections.append(load_context(include_business=include_business))

    # 4. Live facts (critical)
    if facts_block or wiki_context or session_summary:
        sections.append(build_facts_block(facts_block, wiki_context, session_summary))

    # 5. Specialized task instructions (if any)
    if specialized_task:
        sections.append(get_specialized(specialized_task))

    # 6. Security rules (strongly recommended when tools are available)
    if include_security:
        sections.append(load_security())

    # 7. Fallback hardening for non-Claude models
    if "claude" not in model.lower():
        sections.append(get_fallback_directive(model))

    return "\n\n".join(sections)


# Convenience aliases
def build_jarvis_prompt(**kwargs):
    return compose_full_system_prompt(agent="JARVIS", **kwargs)


def build_friday_prompt(**kwargs):
    return compose_full_system_prompt(agent="FRIDAY", **kwargs)


def build_veronica_prompt(**kwargs):
    return compose_full_system_prompt(agent="VERONICA", **kwargs)


def build_karen_prompt(**kwargs):
    return compose_full_system_prompt(agent="KAREN", **kwargs)
