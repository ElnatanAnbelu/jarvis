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

def _build_memory_block(query: str) -> tuple:
    """Return (facts, wiki) tuple for agent system prompt composition."""
    try:
        from memory.memory import get_facts
        from memory.wiki import get_context
        facts = get_facts() or ""
        lower = query.lower()
        is_business_query = any(w in lower for w in _BUSINESS_KEYWORDS)
        wiki = get_context(query) if is_business_query else ""
        return facts, (wiki or "")
    except Exception:
        return "", ""


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
    """Groq Llama-3.3-70b — VERONICA persona. Falls back to Haiku."""
    from memory.memory import save_message, build_messages_for_prompt
    facts, wiki = _build_memory_block(user_input)
    system = _build_agent_system("VERONICA", facts=facts, wiki=wiki, model="groq")

    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            messages = build_messages_for_prompt(user_input, limit=30, include_topic=False)
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=512,
                temperature=0.65,
                messages=[{"role": "system", "content": system}] + messages,
            )
            result = (resp.choices[0].message.content or "").strip()
            if result:
                save_message("veronica", result)
            return result
        except Exception:
            pass

    return _haiku_fallback_agent(user_input, system, "VERONICA")


def think_karen_agent(user_input: str) -> str:
    """Mistral medium — KAREN persona. Falls back to Groq, then Haiku."""
    from memory.memory import save_message, build_messages_for_prompt
    facts, wiki = _build_memory_block(user_input)
    system = _build_agent_system("KAREN", facts=facts, wiki=wiki, model="mistral")

    mistral_key = os.environ.get("MISTRAL_API_KEY", "").strip()
    if mistral_key:
        try:
            from mistralai import Mistral
            client = Mistral(api_key=mistral_key)
            messages = build_messages_for_prompt(user_input, limit=30, include_topic=False)
            resp = client.chat.complete(
                model="mistral-medium-latest",
                max_tokens=768,
                timeout_ms=8000,
                messages=[{"role": "system", "content": system}] + messages,
            )
            result = (resp.choices[0].message.content or "").strip()
            if result:
                save_message("karen", result)
                return result
        except Exception:
            pass

    # Fallback: Groq with KAREN persona
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            messages = build_messages_for_prompt(user_input, limit=30, include_topic=False)
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=768,
                temperature=0.65,
                messages=[{"role": "system", "content": system}] + messages,
            )
            result = (resp.choices[0].message.content or "").strip()
            if result:
                save_message("karen", result)
                return result
        except Exception:
            pass

    return _haiku_fallback_agent(user_input, system, "KAREN")


# ── Streaming generators ───────────────────────────────────────────────────────

def think_veronica_stream(user_input: str):
    """Streaming generator for VERONICA. Groq stream → Haiku stream fallback."""
    from memory.memory import save_message, build_messages_for_prompt
    facts, wiki = _build_memory_block(user_input)
    system = _build_agent_system("VERONICA", facts=facts, wiki=wiki, model="groq")
    messages = build_messages_for_prompt(user_input, limit=30)

    # ── 1. Groq streaming ──────────────────────────────────────────────────────
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=512,
                temperature=0.65,
                stream=True,
                messages=[{"role": "system", "content": system}] + messages,
            )
            full = []
            for chunk in stream:
                text = (chunk.choices[0].delta.content or "")
                if text:
                    full.append(text)
                    yield text
            if full:
                save_message("veronica", "".join(full))
            return
        except Exception:
            pass

    # ── 2. Haiku streaming fallback ────────────────────────────────────────────
    api_key = (
        os.environ.get("ANTHROPIC_API_KEY", "").strip() or
        os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    )
    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            full = []
            with client.messages.stream(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                system=system,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    if text:
                        full.append(text)
                        yield text
            if full:
                save_message("veronica", "".join(full))
        except Exception:
            pass


def think_karen_stream(user_input: str):
    """Streaming generator for KAREN. Mistral stream → Groq stream → Haiku stream fallback."""
    import json as _json
    import requests as _req
    from memory.memory import save_message, build_messages_for_prompt
    facts, wiki = _build_memory_block(user_input)
    system = _build_agent_system("KAREN", facts=facts, wiki=wiki, model="mistral")
    messages = build_messages_for_prompt(user_input, limit=30)

    # ── 1. Mistral streaming (raw HTTP — SDK version-agnostic) ────────────────
    mistral_key = os.environ.get("MISTRAL_API_KEY", "").strip()
    if mistral_key:
        try:
            payload = {
                "model": "mistral-medium-latest",
                "messages": [{"role": "system", "content": system}] + messages,
                "max_tokens": 768,
                "stream": True,
            }
            r = _req.post(
                "https://api.mistral.ai/v1/chat/completions",
                json=payload,
                headers={"Authorization": "Bearer " + mistral_key,
                         "Content-Type": "application/json"},
                stream=True,
                timeout=15,
            )
            if r.status_code == 200:
                full = []
                for raw_line in r.iter_lines(decode_unicode=True):
                    if not raw_line or not raw_line.startswith("data: "):
                        continue
                    data_str = raw_line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        text = _json.loads(data_str)["choices"][0]["delta"].get("content", "")
                        if text:
                            full.append(text)
                            yield text
                    except Exception:
                        continue
                if full:
                    save_message("karen", "".join(full))
                return
        except Exception:
            pass

    # ── 2. Groq streaming fallback ─────────────────────────────────────────────
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=768,
                temperature=0.65,
                stream=True,
                messages=[{"role": "system", "content": system}] + messages,
            )
            full = []
            for chunk in stream:
                text = (chunk.choices[0].delta.content or "")
                if text:
                    full.append(text)
                    yield text
            if full:
                save_message("karen", "".join(full))
            return
        except Exception:
            pass

    # ── 3. Haiku streaming fallback ────────────────────────────────────────────
    api_key = (
        os.environ.get("ANTHROPIC_API_KEY", "").strip() or
        os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    )
    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            full = []
            with client.messages.stream(
                model="claude-haiku-4-5-20251001",
                max_tokens=768,
                system=system,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    if text:
                        full.append(text)
                        yield text
            if full:
                save_message("karen", "".join(full))
        except Exception:
            pass
