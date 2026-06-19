"""Request router — ONE Alfred.

The 4-agent system (FRIDAY / VERONICA / KAREN) is retired. Every request goes to the
single local Alfred brain (brain/think.py → brain/agent.py local loop). These helpers
just (a) handle stop/cancel, (b) strip an "Alfred,"/"Hey Alfred" address prefix, and
(c) route a few cloud-only capabilities (deep research / doc-gen / file+image read)
when the cloud escape-hatch is on — otherwise everything falls through to Alfred.

Note: the internal brain dispatch key stays "JARVIS" (invisible, gating-critical via
allowed_agents). The user only ever sees / talks to Alfred; the SSE 'agent' label is
"Alfred".
"""
import re
from brain.think import think as think_jarvis
from memory.memory import save_message

# Address prefixes — stripped, then routed to the one brain. "jarvis" stays as an alias.
_ADDRESS_PATTERNS = (
    r'^(hey\s+)?alfred[,!?\s]*',
    r'^(hey\s+)?jarvis[,!?\s]*',
)
_STOP_WORDS = ("stop", "cancel", "abort", "stop it", "never mind")


def _strip_address(user_input: str, lower: str) -> str:
    for pattern in _ADDRESS_PATTERNS:
        m = re.match(pattern, lower)
        if m:
            return user_input[m.end():].strip() or "Hey."
    return user_input


def _abort_running_task():
    try:
        from control.agent import get_agent
        get_agent().abort()
    except Exception:
        pass


def route(user_input: str, source: str = "user") -> tuple[str, str]:
    """Blocking route to the single Alfred brain. Returns (response, "Alfred").

    source: "user" (present, trusted owner) | "external" (untrusted inbound) —
    threaded to the brain so the safety gate forces confirmation on red-list actions
    triggered by untrusted content.
    """
    lower = user_input.lower().strip()
    if lower in _STOP_WORDS:
        _abort_running_task()
        return "Stopping.", "SYSTEM"
    actual = _strip_address(user_input, lower)
    save_message("user", actual)
    return think_jarvis(actual, source=source), "Alfred"


def _extract_file_path(text: str):
    """Return the first file/image path found in the text, or None."""
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


def route_stream(user_input: str, image_b64: str = None, source: str = "user"):
    """Streaming generator to the single Alfred brain. Yields:
      ('agent', "Alfred") — who is speaking (always Alfred)
      ('chunk', text)     — each token
      ('done', full_text) — complete response
      ('persist', None)   — no agent pinning anymore (always None)
    """
    from brain.think import think_stream
    from brain.agent import cloud_reasoning_allowed as _cloud_ok
    from memory.wiki import learn

    # Vision: an image was captured → Alfred answers with the vision path.
    if image_b64:
        from brain.think import think_vision_stream
        yield ("agent", "Alfred")
        full = ""
        for chunk in think_vision_stream(user_input, image_b64):
            yield ("chunk", chunk)
            full += chunk
        yield ("done", full)
        return

    lower = user_input.lower().strip()
    if lower in _STOP_WORDS:
        _abort_running_task()
        yield ("agent", "SYSTEM")
        yield ("persist", None)
        yield ("chunk", "Stopping.")
        yield ("done", "Stopping.")
        return

    def _stream_capability(gen):
        """Stream a cloud-capability generator as Alfred, persisting the reply."""
        save_message("user", user_input)
        yield ("agent", "Alfred")
        yield ("persist", None)
        chunks = []
        for chunk in gen:
            chunks.append(chunk)
            yield ("chunk", chunk)
        full = "".join(chunks).strip()
        if full:
            save_message("jarvis", full)
        yield ("done", full)

    # Cloud-only capabilities (deep research / doc-gen) — only when the cloud
    # escape-hatch is on; otherwise fall through to Alfred (which has web tools).
    from brain.research import is_research_request, deep_research
    if is_research_request(user_input) and _cloud_ok():
        yield from _stream_capability(deep_research(user_input))
        return

    from brain.reader import is_doc_gen_request, generate_document
    is_docgen, _ = is_doc_gen_request(user_input)
    if is_docgen and _cloud_ok():
        yield from _stream_capability(generate_document(user_input))
        return

    # File / image read → Alfred via the reader module.
    file_path, file_kind = _is_file_request(user_input)
    if file_path and file_kind:
        from brain.reader import ask_about_file, ask_about_image
        fn = ask_about_image if file_kind == "image" else ask_about_file
        yield from _stream_capability(fn(file_path, user_input))
        return

    # Default: the one Alfred brain.
    actual = _strip_address(user_input, lower)
    save_message("user", actual)
    yield ("agent", "Alfred")
    yield ("persist", None)
    chunks = []
    for chunk in think_stream(actual, source=source):
        chunks.append(chunk)
        yield ("chunk", chunk)
    full = "".join(chunks).strip()
    if full:
        save_message("jarvis", full)
        learn(actual, full)
    yield ("done", full)
