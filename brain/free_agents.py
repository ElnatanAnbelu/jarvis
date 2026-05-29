import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# REMOVED: Team context was causing agents to recommend calling each other.
# Each agent now operates independently. If agent-to-agent collaboration is needed,
# the user must explicitly invoke "work together" mode.
TEAM_CONTEXT = ""

# Compatibility shims — gemini.py imports these. Kept minimal since the real content
# now lives in prompts/personas/ and prompts/core/.
_FACTS_HEADER = """
════════════════════════════════════════════
CRITICAL ANTI-HALLUCINATION SOURCE OF TRUTH
════════════════════════════════════════════
{facts}
════════════════════════════════════════════
"""
_NO_CODE_RULE = "\nNo markdown. Plain conversational sentences only.\n"


def _build_agent_system(agent: str, facts: str = "", wiki: str = "", model: str = "groq") -> str:
    """Build a system prompt for VERONICA or KAREN using the modular prompts library."""
    try:
        from prompts.runtime.prompt_loader import compose_full_system_prompt
        return compose_full_system_prompt(
            agent=agent,
            facts_block=facts,
            wiki_context=wiki,
            model=model,
            include_static_context=False,
            include_security=False,
        )
    except Exception:
        # Inline fallback if prompts/ is unavailable
        base = f"You are {agent} — Elnatan's AI assistant. Never invent personal facts. No markdown. Direct and honest."
        if facts:
            base += f"\n\nFACTS:\n{facts}"
        return base


def _load_env():
    env = Path(__file__).parent.parent / ".env"
    for line in env.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            if v.strip() and k.strip() not in os.environ:
                os.environ[k.strip()] = v.strip()

_load_env()


_BUSINESS_KEYWORDS = {"addis","market","nexel","business","startup","company","product","app","launch","investor","revenue","customer","competitor","strategy","empire","pitch","funding","traction"}

# Personal signals — overlap with brain/think.py _PERSONAL_SIGNALS, used to
# decide whether to auto-inject Second Brain context for non-JARVIS agents.
_PERSONAL_BRAIN_SIGNALS = frozenset({
    "sleep", "gym", "workout", "family", "mom", "dad", "sister", "brother",
    "book", "reading", "anime", "hobby", "interest", "diet", "health",
    "feel", "mood", "energy", "goal", "relationship", "friend",
    "decision", "choice", "tired", "motivated", "stressed", "happy",
    "sad", "bored", "productive", "focused", "habit", "routine",
})


def _get_brain_context_for_agent(query: str) -> str:
    """Auto-injected Second Brain context for FRIDAY/VERONICA/KAREN.

    These agents do not call tools at runtime — their personas state they
    have read-only brain access, but the actual mechanism is auto-injection
    by the server before the API call. When the query has personal signals,
    we search the vault and inject up to 2 results as context they can read
    and reference naturally.

    Returns empty string when:
      - Query has no personal signals
      - Vault is unavailable or empty
      - Any failure (silent fallback — agent works without brain context)
    """
    if not query:
        return ""
    lower = query.lower()
    if not any(s in lower for s in _PERSONAL_BRAIN_SIGNALS):
        return ""
    try:
        import memory.vault as _vm
        if not hasattr(_vm, "_second_brain_instance") or _vm._second_brain_instance is None:
            from memory.vault import VaultManager
            _vm._second_brain_instance = VaultManager()
        result = _vm._second_brain_instance.search_vault(query, max_results=2)
        if not result:
            return ""
        block = (
            "\nBRAIN CONTEXT (auto-injected — relevant notes from Elnatan's "
            "Personal Second Brain; reference these directly, do not invent):\n"
            f"{result}\n"
        )
        return block
    except Exception:
        return ""


def _build_memory_block(query: str) -> tuple:
    """Return (facts, wiki, brain) tuple for agent system prompt composition.

    facts: long-term recorded facts from the memory module
    wiki:  graphify project/codebase context (business queries only)
    brain: Personal Second Brain context (personal queries only)
    """
    try:
        from memory.memory import get_facts
        from memory.wiki import get_context
        facts = get_facts() or ""
        lower = query.lower()
        is_business_query = any(w in lower for w in _BUSINESS_KEYWORDS)
        wiki = get_context(query) if is_business_query else ""
        brain = _get_brain_context_for_agent(query)
        return facts, (wiki or ""), brain
    except Exception:
        return "", "", ""


def _haiku_fallback_agent(user_input: str, system: str, agent_name: str) -> str:
    """Haiku fallback for any agent when primary model is unavailable."""
    api_key = (
        os.environ.get("ANTHROPIC_API_KEY", "").strip() or
        os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    )
    if not api_key:
        return ""
    try:
        import anthropic
        from memory.memory import save_message, build_messages_for_prompt
        client = anthropic.Anthropic(api_key=api_key)
        messages = build_messages_for_prompt(user_input, limit=30)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=system,
            messages=messages,
        )
        result = msg.content[0].text.strip()
        if result:
            save_message(agent_name.lower(), result)
        return result or ""
    except Exception:
        return ""


def think_veronica_agent(user_input: str) -> str:
    """VERONICA — Claude (Haiku→Sonnet) with tools + grounded context.
    Was Groq Llama; now runs the same engine as JARVIS with her own persona."""
    from brain.think import think
    return think(user_input, agent="VERONICA")


def think_karen_agent(user_input: str) -> str:
    """KAREN — Claude (Haiku→Sonnet) with tools + grounded context.
    Was Mistral/Groq; now runs the same engine as JARVIS with her own persona."""
    from brain.think import think
    return think(user_input, agent="KAREN")


# ── Streaming generators ───────────────────────────────────────────────────────

def think_veronica_stream(user_input: str):
    """VERONICA streaming — Claude with tools + grounded context."""
    from brain.think import think_stream
    yield from think_stream(user_input, agent="VERONICA")


def think_karen_stream(user_input: str):
    """KAREN streaming — Claude with tools + grounded context."""
    from brain.think import think_stream
    yield from think_stream(user_input, agent="KAREN")
