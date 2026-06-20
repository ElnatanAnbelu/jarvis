"""brain/app_control.py — deterministic voice control of Alfred's own environment.

The owner's #1 complaint: he says "open approvals" / "close the tabs" / "switch to
activity" and Alfred *narrates* the action ("opening approvals, sir") but never
performs it, then asks "what's next" without finishing. Root cause: the brain had no
hands in its own app — a tool/LLM round-trip that only produces text can't press a
button in the frontend.

The fix is a deterministic intent matcher that runs BEFORE the model in
`brain.router.route_stream`: an unambiguous app-control command is mapped straight to
a structured UI action (which rides the SSE stream to app/alfred.html and triggers the
panel's ALREADY-EXISTING open/close function — the same code path a finger-tap uses)
plus a short spoken confirmation. No model round-trip → instant and 100% reliable.
Anything ambiguous, compound, or unrelated returns None and falls through to the brain
exactly as before.

The panels are the dock surfaces in app/alfred.html: code, web, brain, approvals,
activity, health. The action dicts this module emits are consumed by the
`ui_action` SSE branch in ui/server.py and `applyUiAction()` in app/alfred.html.
"""
import re

# Dock panel id → spoken synonyms. The id is exactly what alfred.html openPanel()/
# closePanel() expect. Multi-word synonyms are matched first (see _find_panels) so
# "system health" wins over "health" and "second brain" over "brain".
_PANEL_SYNONYMS = {
    "approvals": ("pending approvals", "approval queue", "approvals", "approval",
                  "what needs approving", "things to approve", "pending"),
    "activity":  ("activity feed", "activity log", "your activity", "the feed",
                  "activities", "activity", "what you did", "what you've done"),
    "health":    ("system health", "system status", "health panel", "diagnostics",
                  "vitals", "health"),
    "code":      ("code editor", "code panel", "editor", "code"),
    "web":       ("web panel", "the browser", "browser", "web"),
    "brain":     ("second brain", "the vault", "knowledge", "memory", "notes", "brain"),
}
_PANEL_LABEL = {
    "approvals": "Approvals", "activity": "Activity", "health": "Health",
    "code": "Code", "web": "Web", "brain": "Brain",
}

_OPEN_VERBS  = ("open up", "open", "show me", "show", "pull up", "bring up", "give me",
                "let me see", "let's see", "display", "view", "load", "take me to", "go to")
_CLOSE_VERBS = ("close", "hide", "dismiss", "get rid of", "shut", "take down", "kill",
                "remove", "minimize", "minimise", "clear")
_SWITCH_VERBS = ("switch to", "switch over to", "jump to", "flip to")

# Words that signal the utterance is about some OTHER object (a file, an email, a
# message…), not a dock panel — so we don't hijack "open my email" as a panel command.
_NOT_PANEL = ("file", "email", "e mail", "gmail", "inbox", "message", "imessage",
              "whatsapp", "document", "spreadsheet", "folder", "calendar", "draft",
              "song", "playlist", "url", "website", "link")

_ALL_TOKEN_RE = re.compile(r"\b(all|everything|every (panel|tab|window)|"
                           r"all (the )?(panels?|tabs?|windows?)|them( all)?|"
                           r"the tabs?|the panels?|the windows?|it all|all of (it|them))\b")


def _clean(text: str) -> str:
    t = " " + re.sub(r"[^a-z0-9\s']", " ", (text or "").lower()) + " "
    return re.sub(r"\s+", " ", t)


def _has(t: str, phrase: str) -> bool:
    return (" " + phrase + " ") in t


def _find_panels(t: str):
    """Return the dock panel ids named in `t`, longest-synonym-first so multi-word
    names win and don't double-count their shorter substrings."""
    syns = [(w, pid) for pid, words in _PANEL_SYNONYMS.items() for w in words]
    syns.sort(key=lambda x: -len(x[0]))
    found, used = [], []
    for w, pid in syns:
        for m in re.finditer(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", t):
            span = (m.start(), m.end())
            if any(not (span[1] <= s or span[0] >= e) for s, e in used):
                continue  # overlaps an already-claimed (longer) phrase
            used.append(span)
            if pid not in found:
                found.append(pid)
    return found


def match_panel_command(text: str):
    """If `text` is an unambiguous command to control a dock panel, return
    {"actions": [ {act, panel?}, ... ], "say": "<short confirmation>"}.
    Otherwise return None (the brain handles it).

    Conservative by design: requires an explicit verb AND a known panel (or an
    explicit close-all), is length-capped, and bails on non-panel object words — a
    false trigger (opening a panel he didn't ask for) is worse than a miss the brain
    can still field.
    """
    raw = (text or "").strip()
    if not raw or len(raw.split()) > 12:
        return None
    t = _clean(raw)
    if any(_has(t, w) or (" " + w) in t for w in _NOT_PANEL):
        return None

    has_open   = any(_has(t, v) for v in _OPEN_VERBS)
    has_close  = any(_has(t, v) for v in _CLOSE_VERBS)
    has_switch = any(_has(t, v) for v in _SWITCH_VERBS)
    if not (has_open or has_close or has_switch):
        return None

    panels = _find_panels(t)

    # "close everything / close the tabs / close all panels" — no specific panel needed.
    explicit_all = bool(re.search(r"\b(all|everything)\b", t))
    if has_close and (explicit_all or (not panels and _ALL_TOKEN_RE.search(t))):
        return {"actions": [{"act": "close_all"}], "say": "All closed, sir."}

    if not panels:
        return None  # a verb but no panel and not a close-all → let the brain decide

    if has_switch:
        acts = [{"act": "switch", "panel": p} for p in panels]
        return {"actions": acts, "say": _PANEL_LABEL[panels[0]] + ", sir."}
    if has_close:
        acts = [{"act": "close", "panel": p} for p in panels]
        return {"actions": acts,
                "say": "Closed, sir." if len(panels) == 1 else "Done, sir."}
    # default: open
    acts = [{"act": "open", "panel": p} for p in panels]
    if len(panels) == 1:
        return {"actions": acts, "say": _PANEL_LABEL[panels[0]] + ", sir."}
    return {"actions": acts, "say": "Done, sir."}
