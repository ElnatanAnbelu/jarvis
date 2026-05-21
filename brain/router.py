import re
from brain.gemini import think_friday, classify, classify_score3
from brain.think import think as think_jarvis
from brain.free_agents import think_veronica_agent, think_karen_agent
from memory.memory import save_message

MODELS = {
    1: "claude-haiku-4-5-20251001",
    4: "claude-sonnet-4-6",
    5: "claude-opus-4-7",
}

AGENT_PATTERNS = [
    (r'^(hey\s+)?jarvis[,!?\s]*',   "JARVIS"),
    (r'^(hey\s+)?friday[,!?\s]*',   "FRIDAY"),
    (r'^(hey\s+)?veronica[,!?\s]*', "VERONICA"),
    (r'^(hey\s+)?karen[,!?\s]*',    "KAREN"),
]

# Agent names mentioned anywhere in the message (e.g. "finish it jarvis")
_AGENT_ANYWHERE = [
    (r'\bjarvis\b',   "JARVIS"),
    (r'\bfriday\b',   "FRIDAY"),
    (r'\bveronica\b', "VERONICA"),
    (r'\bkaren\b',    "KAREN"),
]

TOOL_WORDS = [
    "send", "text", "email", "open", "search", "find", "check",
    "set volume", "add task", "screenshot", "call", "play", "remind",
    "weather", "timer", "alarm", "calendar", "briefing", "brief me",
    "morning update", "daily update", "news", "control", "click",
    "show me my", "show me", "show me a", "read my", "take a screenshot", "type for me",
    "scroll down", "scroll up",
    # Code execution
    "run", "execute", "run it", "write code", "write python", "write javascript",
    "write a script", "calculate", "compute", "build a", "build me",
    "scaffold", "create a", "make a", "open in browser", "open the website",
    "finish it", "finish the",
]


def _has_tool(text: str) -> bool:
    low = text.lower()
    return any(w in low for w in TOOL_WORDS)


def _call_agent(name: str, user_input: str) -> str:
    if name == "FRIDAY":
        return think_friday(user_input) or ""
    if name == "VERONICA":
        return think_veronica_agent(user_input) or ""
    if name == "KAREN":
        return think_karen_agent(user_input) or ""
    return ""


def _pick_agent_by_score(score: int, user_input: str) -> str:
    """Returns the agent name for a given score."""
    if score >= 4:
        return "JARVIS"
    if score == 2:
        return "FRIDAY"
    if score == 3:
        return classify_score3(user_input)
    return "JARVIS"  # score 1 = JARVIS with Haiku


def _jarvis_model(score: int) -> str:
    if score >= 5:
        return MODELS[5]
    if score >= 4:
        return MODELS[4]
    return MODELS[1]


def route(user_input: str) -> tuple[str, str]:
    """Blocking route — returns (response, agent_name)."""
    lower = user_input.lower().strip()

    if lower in ("stop", "cancel", "abort", "stop it", "never mind"):
        try:
            from control.agent import get_agent
            get_agent().abort()
        except Exception:
            pass
        return "Stopping.", "SYSTEM"

    # Detect explicit agent prefix (start of message)
    explicit_agent = None
    actual = user_input
    for pattern, name in AGENT_PATTERNS:
        m = re.match(pattern, lower)
        if m:
            explicit_agent = name
            actual = user_input[m.end():].strip() or "Hey."
            break

    # Fallback: agent name anywhere in message ("finish it jarvis")
    if not explicit_agent:
        for pattern, name in _AGENT_ANYWHERE:
            if re.search(pattern, lower):
                explicit_agent = name
                # Strip the agent name from the message
                actual = re.sub(pattern, '', lower).strip() or user_input
                actual = user_input  # keep original phrasing, just know who to call
                break

    score = classify(actual)
    save_message("user", actual)

    # Tool requests + score 4-5 always go to JARVIS
    if _has_tool(actual) or score >= 4:
        r = think_jarvis(actual, model=_jarvis_model(score))
        return r, "JARVIS"

    # If explicit agent called, use them
    if explicit_agent and explicit_agent != "JARVIS":
        r = _call_agent(explicit_agent, actual)
        if r:
            return r, explicit_agent
        # fallback to JARVIS Haiku
        r = think_jarvis(actual, model=MODELS[1])
        return r, "JARVIS"

    # Score-based routing
    agent = _pick_agent_by_score(score, actual)
    if agent != "JARVIS":
        r = _call_agent(agent, actual)
        if r:
            return r, agent
        # fallback to JARVIS Haiku
        r = think_jarvis(actual, model=MODELS[1])
        return r, "JARVIS"

    # JARVIS with Haiku (score 1)
    r = think_jarvis(actual, model=MODELS[1])
    return r, "JARVIS"


def _extract_file_path(text: str):
    """Return the first file/image path found in the text, or None."""
    import re
    # Match quoted paths or bare paths with a file extension
    quoted = re.findall(r'["\']([^"\']+\.[a-zA-Z0-9]{1,6})["\']', text)
    if quoted:
        return quoted[0]
    bare = re.findall(r'(?:^|\s)((?:~|\/|\./)[^\s]+\.[a-zA-Z0-9]{1,6})', text)
    if bare:
        return bare[0].strip()
    return None


_FILE_READ_WORDS = ["read", "open", "summarize", "summary", "analyze", "analyse",
                    "what does", "what's in", "whats in", "tell me about", "show me",
                    "explain this", "review this", "look at", "check this"]
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".heic"}
_DOC_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".json",
                   ".py", ".js", ".ts", ".html", ".css", ".xml", ".yaml", ".yml"}


def _is_file_request(text: str):
    """Returns (path, kind) if this looks like a file read request, else (None, None)."""
    from pathlib import Path
    lower = text.lower()
    if not any(w in lower for w in _FILE_READ_WORDS):
        return None, None
    path = _extract_file_path(text)
    if not path:
        return None, None
    ext = Path(path).suffix.lower()
    if ext in _IMAGE_EXTENSIONS:
        return path, "image"
    if ext in _DOC_EXTENSIONS:
        return path, "document"
    return None, None


def route_stream(user_input: str, active_agent: str = None):
    """
    Streaming generator. Yields:
      ('agent', name)     — who is speaking, emitted immediately
      ('chunk', text)     — each token as it arrives
      ('done', full_text) — complete response
      ('persist', name)   — server should remember this agent (None = clear)
    """
    from brain.think import think_stream
    from memory.wiki import learn

    lower = user_input.lower().strip()

    if lower in ("stop", "cancel", "abort", "stop it", "never mind"):
        try:
            from control.agent import get_agent
            get_agent().abort()
        except Exception:
            pass
        yield ("agent", "SYSTEM")
        yield ("persist", None)
        yield ("chunk", "Stopping.")
        yield ("done", "Stopping.")
        return

    # Work Together mode — all four agents
    from brain.team import is_work_together, work_together
    if is_work_together(user_input):
        full_parts = {}
        for event_type, value in work_together(user_input):
            if event_type == "agent":
                current_agent = value
                yield ("agent", value)
                yield ("persist", None)
            elif event_type == "chunk":
                yield ("chunk", value)
                full_parts[current_agent] = value
            elif event_type == "done_agent":
                yield ("done", full_parts.get(value, ""))
            # all_done is the terminal event, nothing to yield
        return

    # Deep research request
    from brain.research import is_research_request, deep_research
    if is_research_request(user_input):
        save_message("user", user_input)
        yield ("agent", "JARVIS")
        yield ("persist", None)
        chunks = []
        for chunk in deep_research(user_input):
            chunks.append(chunk)
            yield ("chunk", chunk)
        full = "".join(chunks).strip()
        if full:
            save_message("jarvis", full)
        yield ("done", full)
        return

    # Document generation request
    from brain.reader import is_doc_gen_request, generate_document
    is_docgen, _ = is_doc_gen_request(user_input)
    if is_docgen:
        save_message("user", user_input)
        yield ("agent", "JARVIS")
        yield ("persist", None)
        chunks = []
        for chunk in generate_document(user_input):
            chunks.append(chunk)
            yield ("chunk", chunk)
        full = "".join(chunks).strip()
        if full:
            save_message("jarvis", full)
        yield ("done", full)
        return

    # File/image read request → JARVIS handles with reader module
    file_path, file_kind = _is_file_request(user_input)
    if file_path and file_kind:
        from brain.reader import ask_about_file, ask_about_image
        save_message("user", user_input)
        yield ("agent", "JARVIS")
        yield ("persist", None)
        question = user_input  # pass the full question so Claude has context
        chunks = []
        fn = ask_about_image if file_kind == "image" else ask_about_file
        for chunk in fn(file_path, question):
            chunks.append(chunk)
            yield ("chunk", chunk)
        full = "".join(chunks).strip()
        if full:
            save_message("jarvis", full)
        yield ("done", full)
        return

    # Detect explicit agent prefix (start of message)
    explicit_agent = None
    actual = user_input
    for pattern, name in AGENT_PATTERNS:
        m = re.match(pattern, lower)
        if m:
            explicit_agent = name
            actual = user_input[m.end():].strip() or "Hey."
            break

    # Fallback: agent name anywhere in message ("finish it jarvis")
    if not explicit_agent:
        for pattern, name in _AGENT_ANYWHERE:
            if re.search(pattern, lower):
                explicit_agent = name
                actual = user_input  # keep original phrasing
                break

    score = classify(actual)
    save_message("user", actual)

    # Tool requests → always JARVIS (FRIDAY/VERONICA/KAREN can't execute tools)
    if _has_tool(actual):
        model = _jarvis_model(score)
        yield ("agent", "JARVIS")
        yield ("persist", None)
        chunks = []
        for chunk in think_stream(actual, model=model):
            chunks.append(chunk)
            yield ("chunk", chunk)
        full = "".join(chunks).strip()
        if full:
            save_message("jarvis", full)
            learn(actual, full)
        yield ("done", full)
        return

    # Score 4-5 → always JARVIS with Sonnet/Opus
    if score >= 4:
        model = _jarvis_model(score)
        yield ("agent", "JARVIS")
        yield ("persist", None)
        chunks = []
        for chunk in think_stream(actual, model=model):
            chunks.append(chunk)
            yield ("chunk", chunk)
        full = "".join(chunks).strip()
        if full:
            save_message("jarvis", full)
            learn(actual, full)
        yield ("done", full)
        return

    # Determine which agent handles this
    if explicit_agent and explicit_agent != "JARVIS":
        agent = explicit_agent
        persist = explicit_agent  # remember this agent
    elif active_agent and active_agent not in ("JARVIS", "SYSTEM"):
        agent = active_agent  # stay with active agent
        persist = active_agent
    else:
        agent = _pick_agent_by_score(score, actual)
        persist = agent if agent != "JARVIS" else None

    # Non-JARVIS agents respond directly
    if agent != "JARVIS":
        yield ("agent", agent)
        yield ("persist", persist)
        r = _call_agent(agent, actual)
        if r:
            yield ("chunk", r)
            yield ("done", r)
            return
        # Agent failed — fall back to JARVIS Haiku
        yield ("agent", "JARVIS")
        yield ("persist", None)
        r = think_jarvis(actual, model=MODELS[1])
        yield ("chunk", r)
        yield ("done", r)
        return

    # JARVIS with Haiku (score 1, no active agent)
    yield ("agent", "JARVIS")
    yield ("persist", None)
    chunks = []
    for chunk in think_stream(actual, model=MODELS[1]):
        chunks.append(chunk)
        yield ("chunk", chunk)
    full = "".join(chunks).strip()
    if full:
        save_message("jarvis", full)
        learn(actual, full)
    yield ("done", full)
