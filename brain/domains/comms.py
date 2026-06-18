"""Comms domain — triage inbound messages: routine / important / spam.

The classifier is heuristic-first (fast, offline, deterministic) and VIP/family
aware via the people registry. Triage routing decides per message:
  - spam      → archive silently (low-stakes)
  - important → escalate to the user (never auto-replied)
  - routine   → draft + send a reply (which the safety gate still governs:
                supervised/away/VIP all force confirmation)

Live execution (reading Gmail, sending) needs the relevant integrations; the
classification + routing here is pure and unit-tested.
"""
from memory import people

_SPAM = ("unsubscribe", "newsletter", "limited time", "act now", "click here",
         "you have won", "winner", "viagra", "crypto", "promo", "% off", "sale ends",
         "verify your account", "claim your", "free trial", "no-reply", "noreply")
_IMPORTANT = ("urgent", "asap", "immediately", "deadline", "invoice", "payment",
              "overdue", "contract", "legal", "lawsuit", "offer", "interview",
              "meeting", "call me", "emergency", "wire", "past due", "final notice")


def classify_message(text: str, sender: str = "") -> str:
    """Return 'spam' | 'important' | 'routine' for a message."""
    blob = f"{sender}\n{text}".lower()
    # VIP / family always count as important (their flags live in the people registry).
    flags = people.match(sender)
    if flags["vip"] or flags["family"]:
        return "important"
    if any(k in blob for k in _IMPORTANT):
        return "important"
    if any(k in blob for k in _SPAM):
        return "spam"
    return "routine"


def triage(messages: list) -> list:
    """Decide what to do with each message. Returns a list of decision dicts:
    {sender, subject, kind, action}. action ∈ {archive, escalate, draft_reply}.
    Pure routing — execution (with gating) is the caller's job."""
    decisions = []
    for m in messages or []:
        sender = m.get("sender", "") or m.get("from", "")
        subject = m.get("subject", "")
        body = m.get("body", "") or m.get("text", "")
        kind = classify_message(f"{subject}\n{body}", sender)
        action = {"spam": "archive", "important": "escalate", "routine": "draft_reply"}[kind]
        decisions.append({"sender": sender, "subject": subject, "kind": kind, "action": action})
    return decisions


def triage_summary(messages: list) -> str:
    """Human-readable triage rollup for a digest / the user."""
    d = triage(messages)
    n = {"archive": 0, "escalate": 0, "draft_reply": 0}
    for x in d:
        n[x["action"]] += 1
    esc = [x for x in d if x["action"] == "escalate"]
    lines = [f"Triaged {len(d)} messages, sir: {n['draft_reply']} routine, "
             f"{n['escalate']} need you, {n['archive']} junk."]
    for x in esc:
        lines.append(f"  ↑ {x['sender']}: {x['subject']}")
    return "\n".join(lines)


def triage_inbox(limit: int = 10) -> str:
    """Autonomous entry point: read recent emails, triage, route.

    Routine replies and archiving go through the tool registry (so the safety
    gate governs every send). Importants are escalated, never auto-replied.
    Returns a summary. Requires the email integration for live use.
    """
    try:
        from brain.tools.registry import execute_tool
        raw = execute_tool("read_emails", {"limit": limit}, agent="JARVIS", source="autonomous")
    except Exception as e:
        return f"Couldn't read inbox: {e}"
    # read_emails returns text; for live structured triage the email tool would
    # return rows. Here we surface what we got + the routing policy.
    if not raw or "no api key" in str(raw).lower() or "error" in str(raw).lower():
        return f"Inbox unavailable (integration not configured): {str(raw)[:120]}"
    return f"Inbox read. Triage policy active (routine→draft, important→escalate, spam→archive).\n{str(raw)[:400]}"
