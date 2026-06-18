"""The single-JARVIS agentic loop — a local LLM driving the tool registry.

This is the fully-local brain (P1): one JARVIS (no 4-agent split, no cloud).
It composes the system prompt + vault-grounded context, then runs a multi-round
tool-use loop where EVERY tool call goes through the safety gate
(registry.execute_tool → autonomy.gate). Model layer is brain/llm.py (Ollama).

Reuses the existing prompt + context machinery in brain/think.py
(`_agent_system`, `_build_context`) so grounding/persona stay identical.
"""
import os
import re

from brain import llm

MAX_ROUNDS = int(os.environ.get("JARVIS_AGENT_MAX_ROUNDS", "8"))
MAX_TOOLS = int(os.environ.get("JARVIS_AGENT_MAX_TOOLS", "24"))

# Always-offered common tools; the rest are added per-request by relevance so
# the local model isn't handed all ~130 schemas every call (a big speedup).
_CORE_TOOLS = {
    "read_file", "list_directory", "web_search", "get_weather",
    "check_calendar", "read_emails", "send_email", "take_screenshot",
}


def enabled() -> bool:
    """Local brain is the default; disable with JARVIS_LOCAL_BRAIN=0. Requires Ollama up + a model pulled."""
    if os.environ.get("JARVIS_LOCAL_BRAIN", "1") == "0":
        return False
    return llm.available() and llm.any_model_available()


def _system_for(agent: str, user_input: str) -> str:
    """Persona system prompt + dynamic vault/facts/business/history context (reused from think.py)."""
    from brain.think import _agent_system, _build_context
    sys = _agent_system(agent)
    try:
        ctx = _build_context(user_input, include_history=True)
    except Exception:
        ctx = ""
    return (sys + "\n\n" + ctx) if ctx else sys


def _select_tools(user_input: str, agent: str, k: int = MAX_TOOLS) -> list:
    """Offer only the most relevant tools to the model — not all ~130 (major
    local-inference speedup). Always include a small core; add tools whose
    name/description matches the request; cap at k."""
    from brain.tools.registry import get_tools
    allt = get_tools(agent)
    words = set(re.findall(r"[a-z]{4,}", (user_input or "").lower()))
    chosen = [s for s in allt if s["name"] in _CORE_TOOLS]
    scored = []
    for s in allt:
        if s["name"] in _CORE_TOOLS:
            continue
        hay = (s["name"] + " " + s.get("description", "")).lower()
        score = sum(1 for w in words if w in hay)
        if score:
            scored.append((score, s))
    for _, s in sorted(scored, key=lambda x: -x[0]):
        if len(chosen) >= k:
            break
        chosen.append(s)
    return chosen[:k]


def _resolve_tools(user_input: str, agent: str, source: str):
    """Run the tool-use rounds; return (messages, last_response, model).

    The model decides which (relevance-filtered) tools to call; each call is
    gated + executed via the registry. Model tier is picked per request.
    """
    from brain.tools.registry import execute_tool
    tools = _select_tools(user_input, agent)
    model = llm.select_tier(user_input)
    messages = [
        {"role": "system", "content": _system_for(agent, user_input)},
        {"role": "user", "content": user_input},
    ]
    for _ in range(MAX_ROUNDS):
        r = llm.chat(messages, tools=tools, model=model, think=False)
        if not r["tool_calls"]:
            return messages, r, model  # model is ready to answer
        messages.append(r["raw"])  # assistant turn carrying the tool_calls
        for tc in r["tool_calls"]:
            result = execute_tool(tc["name"], tc["arguments"], agent=agent, source=source)
            messages.append({"role": "tool", "tool_name": tc["name"], "content": str(result)[:4000]})
    return messages, None, model  # hit round cap


def run(user_input: str, agent: str = "JARVIS", source: str = "user") -> str:
    """Blocking: returns JARVIS's final response after any tool use."""
    messages, last, model = _resolve_tools(user_input, agent, source)
    if last is not None and not last["tool_calls"]:
        return last["content"]
    return llm.chat(messages, model=model, think=False)["content"]


def run_stream(user_input: str, agent: str = "JARVIS", source: str = "user"):
    """Generator: resolves tools, then yields the final answer."""
    messages, last, model = _resolve_tools(user_input, agent, source)
    if last is not None and last.get("content"):
        yield last["content"]  # already produced (no tools) — no second call
        return
    yield from llm.chat_stream(messages, model=model, think=False)
