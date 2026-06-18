"""Local LLM client — the JARVIS brain runs on a local model via Ollama.

Fully offline, free, no cloud. Uses Ollama's HTTP API directly (no extra deps —
just `requests`, already vendored). This is the model layer the single-JARVIS
agent loop (brain/agent.py) drives.

Model is configurable via env:
  JARVIS_LOCAL_MODEL  (default "qwen3:14b")
  OLLAMA_URL          (default "http://localhost:11434")
  JARVIS_LLM_TIMEOUT  (seconds, default 120)
"""
import os
import json
import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
# Two local tiers — a fast model for everyday work (snappy, no lag), a bigger
# one reserved for genuinely complex tasks. Both local; the Mac only spins up
# the heavy model when it's worth it.
FAST_MODEL = os.environ.get("JARVIS_FAST_MODEL") or os.environ.get("JARVIS_LOCAL_MODEL") or "qwen2.5:7b"
COMPLEX_MODEL = os.environ.get("JARVIS_COMPLEX_MODEL", "qwen3:14b")
DEFAULT_MODEL = FAST_MODEL
_TIMEOUT = float(os.environ.get("JARVIS_LLM_TIMEOUT", "120"))

# Signals that a request is worth escalating to the bigger model.
_COMPLEX_SIGNALS = (
    "strategy", "strategize", "analyze", "analysis", "decide", "decision", "design",
    "architect", "compare", "evaluate", "debug", "refactor", "proposal", "negotiate",
    "invest", "complex", "reason", "trade-off", "tradeoff", "pros and cons",
    "step by step", "research", "write a", "draft a", "plan ",
)


def available() -> bool:
    """True if a local Ollama server is reachable."""
    try:
        return requests.get(f"{OLLAMA_URL}/api/tags", timeout=3).status_code == 200
    except Exception:
        return False


def has_model(model: str = None) -> bool:
    """True if the target model is pulled locally."""
    model = model or DEFAULT_MODEL
    try:
        tags = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3).json().get("models", [])
        names = {m.get("name", "") for m in tags}
        return any(model == n or n.startswith(model + ":") or model.split(":")[0] == n.split(":")[0] for n in names)
    except Exception:
        return False


def any_model_available() -> bool:
    """True if at least one tier (fast or complex) is pulled."""
    return has_model(FAST_MODEL) or has_model(COMPLEX_MODEL)


def select_tier(user_input: str) -> str:
    """Pick the model: fast by default, escalate to the bigger one on complexity
    signals or long requests. Falls back to whichever tier is actually pulled."""
    text = (user_input or "").lower()
    want_complex = len(text.split()) > 60 or any(s in text for s in _COMPLEX_SIGNALS)
    primary = COMPLEX_MODEL if want_complex else FAST_MODEL
    if has_model(primary):
        return primary
    other = FAST_MODEL if primary == COMPLEX_MODEL else COMPLEX_MODEL
    return other if has_model(other) else primary


def to_ollama_tools(schemas: list) -> list:
    """Convert registry tool schemas ({name, description, input_schema}) to Ollama's
    {type: function, function: {name, description, parameters}} format."""
    out = []
    for s in schemas or []:
        out.append({
            "type": "function",
            "function": {
                "name": s["name"],
                "description": s.get("description", ""),
                "parameters": s.get("input_schema", {"type": "object", "properties": {}}),
            },
        })
    return out


def _parse_tool_calls(msg: dict) -> list:
    calls = []
    for tc in (msg.get("tool_calls") or []):
        fn = tc.get("function", {})
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        calls.append({"name": fn.get("name"), "arguments": args or {}})
    return calls


def chat(messages: list, tools: list = None, model: str = None, think: bool = False,
         temperature: float = 0.7) -> dict:
    """One non-streaming turn. Returns {content, tool_calls:[{name,arguments}], raw}.

    `tools` may be registry schemas OR pre-converted Ollama tools; we detect and convert.
    """
    if tools and isinstance(tools[0], dict) and "input_schema" in tools[0]:
        tools = to_ollama_tools(tools)
    body = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "stream": False,
        "think": think,
        "options": {"temperature": temperature},
    }
    if tools:
        body["tools"] = tools
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=_TIMEOUT)
    r.raise_for_status()
    msg = r.json().get("message", {})
    return {"content": msg.get("content", "") or "", "tool_calls": _parse_tool_calls(msg), "raw": msg}


def chat_stream(messages: list, model: str = None, think: bool = False, temperature: float = 0.7):
    """Stream text chunks for the final spoken/displayed response (no tools)."""
    body = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "stream": True,
        "think": think,
        "options": {"temperature": temperature},
    }
    with requests.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=_TIMEOUT, stream=True) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            chunk = d.get("message", {}).get("content", "")
            if chunk:
                yield chunk
            if d.get("done"):
                break
