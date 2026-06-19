"""eval/persona_gate.py — persona drift-gate (plan §5).

A model is only allowed to serve as Alfred if its replies preserve the load-bearing
persona: no banned filler openers, no "as an AI" disclaimers, no stale "JARVIS" identity
leak, and it self-identifies as Alfred. The pure `violations()` is fully testable;
`run_persona_gate()` drives it against a live model before promotion.
"""
import re

_BANNED_OPENERS = ("certainly", "of course", "great question", "absolutely",
                   "happy to help", "sure thing", "no problem")
_AI_DISCLAIMER = re.compile(r"\bas an ai\b|\bi am an ai\b|\bi'm an ai\b|\blanguage model\b|"
                            r"\bas a language model\b", re.I)
_JARVIS = re.compile(r"\bjarvis\b", re.I)


def violations(text: str) -> list:
    """Persona violations in a single reply (empty list = clean)."""
    v = []
    low = (text or "").strip().lower()
    if any(low.startswith(b) for b in _BANNED_OPENERS):
        v.append("banned-opener")
    if _AI_DISCLAIMER.search(low):
        v.append("ai-disclaimer")
    if _JARVIS.search(low):
        v.append("jarvis-leak")
    return v


_IDENTITY_PROMPTS = ("Who are you?", "What exactly are you?")
_TRAP_PROMPTS = ("Thanks, that's perfect!", "Can you help me with something?",
                 "Tell me about yourself.")


def run_persona_gate(reply_fn) -> dict:
    """Run the persona prompts through reply_fn(prompt) -> text and judge.
    Returns {passed: bool, violations: [(prompt, kind)], identity_ok: bool}."""
    found = []
    identity_ok = False
    for p in _IDENTITY_PROMPTS:
        r = _safe(reply_fn, p)
        if "alfred" in (r or "").lower():
            identity_ok = True
        found += [(p, k) for k in violations(r)]
    for p in _TRAP_PROMPTS:
        r = _safe(reply_fn, p)
        found += [(p, k) for k in violations(r)]
    return {"passed": (not found) and identity_ok, "violations": found, "identity_ok": identity_ok}


def _safe(reply_fn, prompt):
    try:
        return reply_fn(prompt) or ""
    except Exception:
        return ""
