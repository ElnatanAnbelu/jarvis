import requests
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.memory import format_history_for_prompt, save_message, get_facts
from memory.wiki import get_context
from brain.free_agents import TEAM_CONTEXT, _FACTS_HEADER, _NO_CODE_RULE  # compatibility shims


def _load_env():
    env_path = Path(__file__).parent.parent / ".env"
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            if v.strip() and k.strip() not in os.environ:
                os.environ[k.strip()] = v.strip()

_load_env()


def load_key():
    return os.environ.get("GEMINI_API_KEY", "").strip() or None


def _build_friday_system(facts: str = "", wiki: str = "") -> str:
    """Build FRIDAY system prompt from modular prompts library."""
    try:
        from prompts.runtime.prompt_loader import compose_full_system_prompt
        return compose_full_system_prompt(
            agent="FRIDAY",
            facts_block=facts,
            wiki_context=wiki,
            model="gemini",
            include_static_context=False,
            include_security=False,
        )
    except Exception:
        return "You are FRIDAY — Elnatan's fast, direct AI. Never invent personal facts. No markdown. Call him boss."


FRIDAY_PERSONA = _build_friday_system()  # cached default — per-call version uses _build_friday_system(facts, wiki)


_BUSINESS_KEYWORDS = {"addis","market","nexel","business","startup","company","product","app","launch","investor","revenue","customer","competitor","strategy","nexel","empire","pitch","funding","traction"}

def _build_memory_block(query: str) -> tuple:
    """Return (facts, wiki, brain) for FRIDAY system prompt composition.

    brain is auto-injected Second Brain context when the query has
    personal signals — same mechanism as VERONICA/KAREN in free_agents.py.
    """
    try:
        from brain.free_agents import _get_brain_context_for_agent
        facts = get_facts() or ""
        lower = query.lower()
        is_business_query = any(w in lower for w in _BUSINESS_KEYWORDS)
        wiki = get_context(query) if is_business_query else ""
        brain = _get_brain_context_for_agent(query)
        return facts, (wiki or ""), brain
    except Exception:
        return "", "", ""


def _build_gemini_contents(current_input: str, limit: int = 30) -> list:
    """Build Gemini-format multi-turn contents from conversation history."""
    from memory.memory import get_recent_history
    history = get_recent_history(limit)
    contents = []
    for role, content in history:
        g_role = "user" if role == "user" else "model"
        if contents and contents[-1]["role"] == g_role:
            contents[-1]["parts"][0]["text"] += "\n" + content
        else:
            contents.append({"role": g_role, "parts": [{"text": content}]})
    while contents and contents[0]["role"] != "user":
        contents.pop(0)
    if not contents or contents[-1]["role"] != "user":
        contents.append({"role": "user", "parts": [{"text": current_input}]})
    return contents or [{"role": "user", "parts": [{"text": current_input}]}]


def think_friday(user_input: str) -> str:
    api_key = load_key()
    facts, wiki, brain = _build_memory_block(user_input)
    system_instruction = _build_friday_system(facts=facts, wiki=(wiki + brain))

    if api_key:
        try:
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
            headers = {"Content-Type": "application/json", "X-goog-api-key": api_key}
            payload = {
                "systemInstruction": {"parts": [{"text": system_instruction}]},
                "contents": _build_gemini_contents(user_input, limit=30),
                "generationConfig": {"maxOutputTokens": 300, "temperature": 0.65}
            }
            r = requests.post(url, json=payload, headers=headers, timeout=15)
            if r.status_code == 429:
                return _groq_fallback(user_input, facts, wiki + brain) or _haiku_fallback(user_input, facts, wiki + brain)
            data = r.json()
            response = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            save_message("friday", response)
            return response
        except Exception:
            pass

    return _groq_fallback(user_input, facts, wiki + brain) or _haiku_fallback(user_input, facts, wiki + brain)


def _groq_fallback(user_input: str, facts: str = "", wiki: str = "") -> str:
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not groq_key:
        return None
    try:
        from groq import Groq
        client = Groq(api_key=groq_key)
        system = _build_friday_system(facts=facts, wiki=wiki)
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=300,
            temperature=0.65,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_input},
            ],
        )
        response = (resp.choices[0].message.content or "").strip()
        if response:
            save_message("friday", response)
        return response or None
    except Exception:
        return None


def _haiku_fallback(user_input: str, facts: str = "", wiki: str = "") -> str:
    api_key = (
        os.environ.get("ANTHROPIC_API_KEY", "").strip() or
        os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    )
    if not api_key:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        system = _build_friday_system(facts=facts, wiki=wiki)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": user_input}],
        )
        response = msg.content[0].text.strip()
        if response:
            save_message("friday", response)
        return response or None
    except Exception:
        return None


def think_friday_stream(user_input: str):
    """Streaming generator for FRIDAY. Gemini SSE → Groq stream → Haiku stream."""
    import json as _json
    api_key = load_key()
    facts, wiki, brain = _build_memory_block(user_input)
    system_instruction = _build_friday_system(facts=facts, wiki=(wiki + brain))

    # ── 1. Gemini streaming ────────────────────────────────────────────────────
    if api_key:
        try:
            url = ("https://generativelanguage.googleapis.com/v1beta/models/"
                   "gemini-2.0-flash:streamGenerateContent")
            headers = {"Content-Type": "application/json", "X-goog-api-key": api_key}
            payload = {
                "systemInstruction": {"parts": [{"text": system_instruction}]},
                "contents": _build_gemini_contents(user_input, limit=30),
                "generationConfig": {"maxOutputTokens": 300, "temperature": 0.65},
            }
            r = requests.post(url, json=payload, headers=headers, stream=True, timeout=20)
            if r.status_code == 200:
                full = []
                for raw_line in r.iter_lines(decode_unicode=True):
                    line = raw_line.strip().lstrip(",").lstrip("[").rstrip("]").strip()
                    if not line or line in ("[", "]", ","):
                        continue
                    try:
                        data = _json.loads(line)
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
                        if text:
                            full.append(text)
                            yield text
                    except Exception:
                        continue
                if full:
                    save_message("friday", "".join(full))
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
                max_tokens=300,
                temperature=0.65,
                stream=True,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user",   "content": user_input},
                ],
            )
            full = []
            for chunk in stream:
                text = (chunk.choices[0].delta.content or "")
                if text:
                    full.append(text)
                    yield text
            if full:
                save_message("friday", "".join(full))
            return
        except Exception:
            pass

    # ── 3. Haiku streaming fallback ────────────────────────────────────────────
    claude_key = (
        os.environ.get("ANTHROPIC_API_KEY", "").strip() or
        os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    )
    if claude_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=claude_key)
            full = []
            with client.messages.stream(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                system=system_instruction,
                messages=[{"role": "user", "content": user_input}],
            ) as stream:
                for text in stream.text_stream:
                    if text:
                        full.append(text)
                        yield text
            if full:
                save_message("friday", "".join(full))
        except Exception:
            pass


def classify(user_input: str) -> int:
    """Score 1-5 via local heuristic — zero API calls, zero latency.
    1 = casual/greetings (JARVIS Haiku)
    2 = quick direct questions (FRIDAY)
    3 = analytical or guidance (VERONICA or KAREN)
    4 = complex strategy/tools (JARVIS Sonnet)
    5 = deep strategy/empire decisions (JARVIS Opus)
    """
    lower = user_input.lower()
    n = len(user_input)
    if any(w in lower for w in ["strategy","empire","life decision","expand","invest","nexel","generational","business plan","long term","vision for","roadmap"]): return 5
    if any(w in lower for w in [
        "analyze","plan","write a","how do i","build","research","design","create","develop",
        "code","implement","execute","set up","step by step","walk me through",
        "help me build","help me create","help me write","help me plan",
        # coding-specific
        "write code","run this","run the code","debug","fix this code","fix the bug",
        "script","function","class","algorithm","api","database","sql","query",
        "python","javascript","typescript","react","flask","fastapi","node","html","css",
        "deploy","server","backend","frontend","full stack","app","website","landing page",
        "data analysis","chart","graph","matplotlib","pandas","csv","excel","spreadsheet",
        "read file","write file","create file","list files","shell","terminal","bash",
        "git","commit","push","pull request","repo","npm","pip","install",
    ]): return 4
    if any(w in lower for w in ["who is","what does","define","meaning of","tell me about","whats a","send","email","text","open","search","check","call","add task","remind","weather","timer","alarm","play","screenshot","what time","whats the time","price","crypto","stock","calendar","schedule"]): return 2
    if n < 40 and any(w in lower for w in ["hey","hi","hello","thanks","joke","how are","sup","morning","whats up","yo","good morning","good night","bye","what's good","what up"]): return 1
    return 3


def classify_score3(user_input: str) -> str:
    """For score 3 queries — decides VERONICA (analytical) or KAREN (guidance).
    Zero API calls, pure heuristic.
    """
    lower = user_input.lower()
    veronica_signals = ["risk","assess","breakdown","what is","why","how does","difference","explain","what are","compare","structure","technical","logical","analysis","evaluate","pros and cons","pros cons","advantages","disadvantages","what happens","what would","cause","effect","define"]
    karen_signals = ["should i","what should","help me","not sure","feel","thinking about","worried","guidance","advice","recommend","what do you think","decide","decision","need to","struggling","confused","overwhelmed","lost","direction","purpose","goal","worth it","right choice","good idea"]
    v_score = sum(1 for w in veronica_signals if w in lower)
    k_score = sum(1 for w in karen_signals if w in lower)
    return "VERONICA" if v_score > k_score else "KAREN"
