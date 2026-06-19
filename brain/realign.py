"""brain/realign.py — re-assert Alfred's identity on a major level-up (plan §R6).

After a model swap, restore, or import, the SUBSTRATE changed — so we re-inject the persona
and verify the load-bearing identity markers survived. The being must never become a
stranger when the engine underneath it changes.
"""

# The minimal load-bearing markers that prove the persona is still Alfred.
_MARKERS = ("alfred", "sir", "butler")


def persona_intact() -> bool:
    """True if the live persona still carries Alfred's load-bearing identity markers."""
    try:
        from brain.agent import _LEAN_PERSONA
        low = _LEAN_PERSONA.lower()
        return all(m in low for m in _MARKERS)
    except Exception:
        return False


def realign_assertion() -> str:
    """The identity re-assertion to prepend after a level-up (the canonical lean persona)."""
    try:
        from brain.agent import _LEAN_PERSONA
        return _LEAN_PERSONA
    except Exception:
        return ("You are Alfred — Elnatan's second self and chief of staff, a refined British "
                "butler. Address him as 'sir'. One continuous being across every model.")


def realign() -> dict:
    """Run a realignment check after a level-up. Returns the status + any re-assertion needed."""
    intact = persona_intact()
    return {
        "persona_intact": intact,
        "assertion": None if intact else realign_assertion(),
        "note": ("Identity verified — still the same Alfred, sir." if intact
                 else "Persona markers missing after the level-up — re-asserting identity."),
    }
