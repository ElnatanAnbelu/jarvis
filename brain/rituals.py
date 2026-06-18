"""Greeting + goodnight/goodmorning rituals — the human touch JARVIS opens/closes the day with.

Model-free and quiet by design: greet on recognition and surface only what needs
the user; no unsolicited briefing unless something's waiting or he asks.
"""
import datetime

from memory import memory


def _period() -> str:
    h = datetime.datetime.now().hour
    if 5 <= h < 12:
        return "morning"
    if 12 <= h < 17:
        return "afternoon"
    if 17 <= h < 22:
        return "evening"
    return "night"


_HELLO = {
    "morning": "Good morning, sir.",
    "afternoon": "Good afternoon, sir.",
    "evening": "Good evening, sir.",
    "night": "Still up, sir?",
}


def greeting() -> str:
    """On recognition: greet, then surface only what needs the user (else stay light)."""
    hello = _HELLO[_period()]
    try:
        pend = len(memory.get_pending_confirmations())
    except Exception:
        pend = 0
    if pend:
        noun = "item needs" if pend == 1 else "items need"
        return f"{hello} {pend} {noun} your decision when you have a moment."
    return f"{hello} All quiet — nothing needs you right now."


def goodmorning() -> str:
    return greeting()


def goodnight() -> str:
    """Wind down: a short account of what was handled, then go quiet."""
    from brain.runner import build_digest
    digest = build_digest()
    return f"Goodnight, sir. {digest}\nI'll keep watch and stay quiet until morning."
