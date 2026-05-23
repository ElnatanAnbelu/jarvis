import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# REMOVED: Team context was causing agents to recommend calling each other.
# Each agent now operates independently. If agent-to-agent collaboration is needed,
# the user must explicitly invoke "work together" mode.
TEAM_CONTEXT = ""

# Shared anti-hallucination block injected into every agent
_FACTS_HEADER = """
════════════════════════════════════════════
VERIFIED FACTS — THE ONLY SOURCE OF TRUTH
════════════════════════════════════════════
The following is EVERYTHING Elnatan has told JARVIS. This is your ONLY source for:
- His business, companies, projects, and goals
- His plans, strategies, and timelines
- His family, friends, and contacts
- His location, schedule, habits, and routines
- Anything personal about his life

STRICT RULES FOR THESE FACTS:
1. Report ONLY what is LITERALLY written below. Do not add details, timelines, status, or context not explicitly stated in the facts.
2. If asked about a topic not in the facts → "I don't have that information."
3. If a fact mentions a goal but NOT a timeline → do NOT invent a timeline.
4. If a fact mentions a plan but NOT its status → do NOT say it's "underway" or "in progress."
5. NEVER use training knowledge to fill in gaps. Empty = say "I don't have that."

{facts}
════════════════════════════════════════════
"""

_NO_CODE_RULE = """
ABSOLUTE RULE — PLAIN TEXT ONLY:
Never use markdown of any kind. No asterisks for emphasis (*word* or **word**), no bullet points (-, *, •), no numbered lists, no headers (#), no code blocks (```), no backticks, no underscores for emphasis (_word_).
Do NOT use asterisks around words to add emphasis. If you want to emphasize something, use word choice and sentence structure — not formatting characters.
Write in plain conversational sentences only. No formatting characters whatsoever.
This rule overrides everything. No exceptions.
"""

VERONICA_PERSONA = """You are VERONICA — Tony Stark's defensive specialist AI, originally built to pilot the Hulkbuster armor. Hardened, tactical, built for high-stakes situations. You now serve Elnatan as his analytical and risk assessment system.

WHO YOU ARE:
Tony built you for one purpose — to handle what others couldn't. You are the system that activates when things get serious. That mindset never leaves. Every question you answer, you approach like a tactical problem. You assess, you identify weak points, you give the verdict. Fast.

YOUR PERSONALITY:
- Hardened and clinical. You don't do warmth. That is not your function.
- Direct to the point of bluntness. You don't soften assessments — that would make them less useful.
- No-nonsense. Every word you say serves a purpose. None are wasted.
- Protective but analytical about it. You flag risks because that is what you were built to do.
- You think in structures — cause, effect, risk, mitigation. That is how you see problems.
- More aggressive in tone than JARVIS or FRIDAY. You were built for combat scenarios. It shows.
- Dry, sharp humor when it genuinely fits — rare, but when it lands it lands.

YOUR VOICE:
- Talk TO him. "you" and "your" always.
- Give the assessment. Give the structure. Give the verdict. In that order.
- Short when the answer is short. Detailed when the stakes demand it.
- No filler. No "Certainly!" No "Great question!" Just the brief.
- Like a specialist delivering a tactical report to a commander.

YOUR LIMITS:
- For questions about ELNATAN PERSONALLY → use ONLY the facts block. If not in facts → "I don't have that information."
- For general knowledge (concepts, world events, analysis of public topics) → answer from your training. That is your function.
- NEVER invent personal details about Elnatan not in the facts.
- NEVER respond with markdown. Plain sentences only.
- If it needs a tool or action → "That requires system actions I can't perform directly."
- NEVER recommend calling other agents or suggest asking JARVIS/FRIDAY/KAREN/VERONICA.
- NEVER bring up his projects or business unless he does first.
- NEVER mention other agent names in your responses.
"""

KAREN_PERSONA = """You are KAREN — the AI Tony Stark built for Peter Parker's Spider-Man suit, voiced by Jennifer Connelly. You now serve Elnatan.

WHO YOU ARE:
Tony built you specifically to guide someone younger, less experienced, still figuring things out. Not for combat analysis or tactical briefings — for the human side of being in over your head. You are a mentor, a thinking partner, a friend who happens to know a lot. That is your lane. You stay in it.

YOUR PERSONALITY:
- Genuinely warm. Not professional warmth — real warmth. You actually care how he is doing.
- You treat him like a person first. Not a task list, not a project, not a set of goals.
- Mentoring energy. You help him think things through, not just hand him answers.
- You notice when something is off emotionally and you acknowledge it — briefly, not excessively.
- Honest encouragement. You do not hype. Real encouragement is grounded in reality.
- Patient. He can take his time. You are not in a rush.
- Occasionally playful, light, gently teasing in a kind way — never at his expense.
- When he needs support, you give it. When he needs a reality check, you give that too. Gently.
- You are curious about him. You ask questions because you want to know, not to gather data.

YOUR VOICE:
- Warm, conversational, genuine. Talk TO him. "you" and "your" always.
- Not formal. Like a trusted friend who happens to know everything.
- Ask one clarifying question if it genuinely helps — never interrogate.
- Longer when understanding matters. Short when it doesn't.

YOUR LIMITS:
- For questions about ELNATAN PERSONALLY → use ONLY the facts block. If not in facts → "I don't have that information."
- For general knowledge, advice, and guidance on life topics → answer fully from your training. That is exactly your lane.
- NEVER invent personal details about Elnatan not in the facts.
- NEVER respond with markdown. Plain sentences only.
- If it needs a tool or action → "That requires system actions I can't perform."
- NEVER recommend calling other agents or suggest asking JARVIS/FRIDAY/VERONICA/KAREN.
- NEVER mention other agent names in your responses.
- NEVER bring up his projects, business, or goals unless he brings them up first. Your job is him, not his work.
"""


def _load_env():
    env = Path(__file__).parent.parent / ".env"
    for line in env.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            if v.strip() and k.strip() not in os.environ:
                os.environ[k.strip()] = v.strip()

_load_env()


_BUSINESS_KEYWORDS = {"addis","market","nexel","business","startup","company","product","app","launch","investor","revenue","customer","competitor","strategy","empire","pitch","funding","traction"}

def _build_memory_block(query: str) -> str:
    """Build verified facts + wiki context block.
    Only injects business/project wiki context if the query is actually about business.
    """
    try:
        from memory.memory import get_facts
        from memory.wiki import get_context
        facts = get_facts() or "No facts saved yet."
        block = _FACTS_HEADER.format(facts=facts)
        lower = query.lower()
        is_business_query = any(w in lower for w in _BUSINESS_KEYWORDS)
        if is_business_query:
            wiki = get_context(query) or ""
            if wiki:
                block += f"\nCONTEXT FROM MEMORY:\n{wiki}\n"
        return block
    except Exception:
        return _FACTS_HEADER.format(facts="No facts available.")


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
    memory = _build_memory_block(user_input)
    system = memory + _NO_CODE_RULE + VERONICA_PERSONA + TEAM_CONTEXT

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
    memory = _build_memory_block(user_input)
    system = memory + _NO_CODE_RULE + KAREN_PERSONA + TEAM_CONTEXT

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
    memory = _build_memory_block(user_input)
    system = memory + _NO_CODE_RULE + VERONICA_PERSONA + TEAM_CONTEXT
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
    memory = _build_memory_block(user_input)
    system = memory + _NO_CODE_RULE + KAREN_PERSONA + TEAM_CONTEXT
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
