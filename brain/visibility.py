"""
Smart Visibility classification for HUD rendering.

Every agent response, observer push, and proactive queue item is
classified into one of three visibility levels before reaching the HUD:

  surface   — must be visible (Second Brain writes, sensitive content,
              Tier 3 destructive actions, observer insights). Notification
              eligible (B7).
  normal    — standard conversation. Default rendering, no special treatment.
  collapsed — low-stakes inter-agent coordination (other agents nudging
              JARVIS, deferrals, raw tool echoes, one-word acks). Rendered
              as muted single-line preview the user can expand.

Pure rule-based string matching, no model calls. Runs in <1ms.

Returns a dict {"visibility": str, "tags": list[str]} per message.
"""
import re
from typing import Optional


# ── Compiled patterns ─────────────────────────────────────────────────────────

# Tag patterns — extract structured tags JARVIS or other agents emit
_BRAIN_TAG = re.compile(r"\[BRAIN:\s*([^\]]+)\]", re.IGNORECASE)
_SENSITIVE_TAG = re.compile(r"\[SENSITIVE\]", re.IGNORECASE)
_OBSERVER_PREFIX = re.compile(r"^\s*\[OBS\]", re.IGNORECASE)

# Surface triggers — these always promote a message to `surface`
_TIER3_ACTION_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bdelete_file\b",
        r"\bdelete_directory\b",
        r"\bgit\s+push\b",
        r"\bsend(ing)?\s+(email|imessage|message|whatsapp|telegram)\b",
        r"\b(payment|purchase|transaction)\b.*\b(confirm|proceed|approved)\b",
        r"\bsudo\s",
        r"\brm\s+-[rf]",
    ]
]
_PERSONAL_MODEL_PATTERNS = [
    re.compile(r"_PersonalModel", re.IGNORECASE),
    re.compile(r"\bupdate_personal_model\b"),
]

# Collapsed triggers — these demote to `collapsed`
# 1. Suggestions from non-JARVIS agents (just a nudge; JARVIS decides)
_BRAIN_SUGGEST = re.compile(r"\[BRAIN:\s*suggest", re.IGNORECASE)

# 2. Agent-deferral phrases
_DEFERRAL_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"that'?s\s+jarvis\s+(territory|domain|business)",
        r"i'?ll\s+defer\s+to\s+jarvis",
        r"hand(ing)?\s+(this\s+)?(off\s+)?to\s+jarvis",
        r"jarvis\s+handles\s+(this|that)",
    ]
]

# 3. One-word acknowledgments
_ONE_WORD_ACK = re.compile(
    r"^\s*(noted|got\s+it|okay|ok|sure|done|copy|acknowledged|on\s+it|"
    r"yes|yep|right|indeed|understood)[.!\s]*$",
    re.IGNORECASE,
)


def _extract_tags(text: str) -> list:
    """Pull out [BRAIN: ...] and [SENSITIVE] tags as normalized strings."""
    tags = []
    for m in _BRAIN_TAG.finditer(text or ""):
        inner = m.group(1).strip()
        tags.append(f"BRAIN:{inner}")
    if _SENSITIVE_TAG.search(text or ""):
        tags.append("SENSITIVE")
    return tags


def _is_jarvis_brain_action(tags: list) -> bool:
    """Return True if any BRAIN tag is an action JARVIS performed (not a suggestion)."""
    for t in tags:
        if not t.startswith("BRAIN:"):
            continue
        inner = t[len("BRAIN:"):].strip().lower()
        if inner.startswith("suggest"):
            continue
        # SAVED, PROPOSED, SEARCHED, UPDATED, REJECTED, APPROVED, etc.
        return True
    return False


def _is_suggest_only(tags: list) -> bool:
    """Return True if every BRAIN tag is a suggest (not an action)."""
    brain_tags = [t for t in tags if t.startswith("BRAIN:")]
    if not brain_tags:
        return False
    return all(t[len("BRAIN:"):].strip().lower().startswith("suggest")
               for t in brain_tags)


def _matches_any(patterns: list, text: str) -> bool:
    return any(p.search(text) for p in patterns)


def classify(text: str, agent: Optional[str] = None,
             source: Optional[str] = None) -> dict:
    """Classify a message into a visibility tier.

    Args:
        text: The message text (post-strip-markdown is fine).
        agent: Optional agent name (JARVIS, FRIDAY, VERONICA, KAREN).
        source: Optional source — "chat", "observer", "proactive".

    Returns:
        {"visibility": "surface" | "normal" | "collapsed",
         "tags": list[str]}
    """
    if not text:
        return {"visibility": "normal", "tags": []}

    tags = _extract_tags(text)

    # ── SURFACE — checked first (highest priority) ───────────────────────

    # Observer insights always surface
    if _OBSERVER_PREFIX.search(text):
        return {"visibility": "surface", "tags": tags + ["OBSERVER"]}

    # Any JARVIS brain action (SAVED, PROPOSED, etc.) — surface
    if _is_jarvis_brain_action(tags):
        return {"visibility": "surface", "tags": tags}

    # [SENSITIVE] tag — surface
    if "SENSITIVE" in tags:
        return {"visibility": "surface", "tags": tags}

    # Personal Model references — surface
    if _matches_any(_PERSONAL_MODEL_PATTERNS, text):
        return {"visibility": "surface", "tags": tags + ["PERSONAL_MODEL"]}

    # Tier 3 destructive / sensitive actions — surface
    if _matches_any(_TIER3_ACTION_PATTERNS, text):
        return {"visibility": "surface", "tags": tags + ["TIER3_ACTION"]}

    # ── COLLAPSED — second priority ──────────────────────────────────────

    # Pure BRAIN: suggest from non-JARVIS agent — collapsed
    if _is_suggest_only(tags) and agent and agent.upper() != "JARVIS":
        return {"visibility": "collapsed", "tags": tags}

    # Agent deferral phrases — collapsed
    if _matches_any(_DEFERRAL_PATTERNS, text):
        return {"visibility": "collapsed", "tags": tags}

    # One-word acks — collapsed
    if _ONE_WORD_ACK.match(text):
        return {"visibility": "collapsed", "tags": tags}

    # ── NORMAL — default ─────────────────────────────────────────────────
    return {"visibility": "normal", "tags": tags}
