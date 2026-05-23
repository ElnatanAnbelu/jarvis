"""
Phase E — Autonomous Observer Loop.

Runs every 6 minutes, scans recent conversation history for recurring
patterns, generates a short Haiku insight, and pushes it to the HUD
via the proactive queue.

Guardrails:
  • Text insights only — never self-executes actions
  • 5-minute minimum cooldown between pushes
  • Max 3 insights per hour
  • Respects observer_quiet meta flag (toggled by /api/observer/quiet)

Observer messages are prefixed with [OBS] so the HUD can render them
with distinct cyan styling vs the amber proactive alerts.
"""

import os
import time
import threading
from pathlib import Path
from datetime import datetime
from collections import Counter


def _load_env():
    env = Path(__file__).parent.parent / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            if v.strip() and k.strip() not in os.environ:
                os.environ[k.strip()] = v.strip()

_load_env()


# ── Module state ─────────────────────────────────────────────────────────────
_hud_queue = None
_last_push_at = None
_push_count_this_hour = 0
_push_hour = -1
_last_pattern_hash = ""   # skip identical pattern runs


# ── Cooldown guard ────────────────────────────────────────────────────────────
def _can_push():
    global _push_count_this_hour, _push_hour
    now = datetime.now()
    if now.hour != _push_hour:
        _push_count_this_hour = 0
        _push_hour = now.hour
    if _push_count_this_hour >= 3:
        return False
    if _last_push_at and (now - _last_push_at).total_seconds() < 300:
        return False
    return True


def _push(message):
    global _last_push_at, _push_count_this_hour
    if _hud_queue is not None:
        try:
            _hud_queue.put_nowait("[OBS] " + message)
            _last_push_at = datetime.now()
            _push_count_this_hour += 1
        except Exception:
            pass


# ── Quiet mode ────────────────────────────────────────────────────────────────
def is_quiet():
    try:
        from memory.memory import _meta_get
        return _meta_get("observer_quiet", "0") == "1"
    except Exception:
        return False


def toggle_quiet():
    try:
        from memory.memory import _meta_get, _meta_set
        current = _meta_get("observer_quiet", "0")
        _meta_set("observer_quiet", "0" if current == "1" else "1")
        return _meta_get("observer_quiet", "0") == "1"
    except Exception:
        return False


# ── Topic extraction ──────────────────────────────────────────────────────────
_STOPWORDS = {
    "the","a","an","is","it","in","on","at","to","for","of","and","or","but",
    "not","you","i","me","my","we","us","that","this","what","how","when",
    "do","did","done","can","could","would","should","will","be","been","was",
    "are","have","has","had","with","from","about","your","its","so","if",
    "just","get","got","let","make","like","know","think","want","need","okay",
    "yes","no","hey","ok","hi","hello","right","now","then","than","up","out",
    "all","also","here","there","more","some","any","new","one","two","time",
    "jarvis","friday","veronica","karen","tell","said","says","ask","asked",
    "want","really","already","still","well","good","great","sure","maybe",
}

def _top_topics(messages):
    freq = Counter()
    for _, content in messages:
        for w in content.lower().split():
            w = w.strip(".,!?;:\"'()")
            if len(w) >= 4 and w not in _STOPWORDS and w.isalpha():
                freq[w] += 1
    return [(w, c) for w, c in freq.most_common(10) if c >= 3]


# ── Pattern detection ─────────────────────────────────────────────────────────
def _detect_pattern():
    """
    Returns (context_str, topic) if a noteworthy pattern is found, else (None, None).
    """
    global _last_pattern_hash
    try:
        from memory.memory import get_recent_history
        messages = get_recent_history(limit=80)
        if len(messages) < 8:
            return None, None

        topics = _top_topics(messages)
        if not topics:
            return None, None

        top_word, top_count = topics[0]

        # Require the word appears in at least 5 separate messages
        msg_hits = sum(1 for _, c in messages if top_word in c.lower())
        if msg_hits < 5:
            return None, None

        # Skip if we already surfaced this exact pattern
        pattern_hash = top_word + str(msg_hits)
        if pattern_hash == _last_pattern_hash:
            return None, None
        _last_pattern_hash = pattern_hash

        # Build context: top topics + a few relevant message snippets
        topic_list = ", ".join(w for w, _ in topics[:5])
        snippets = []
        for role, content in messages:
            if top_word in content.lower() and len(snippets) < 3:
                snippets.append("{}: {}".format(
                    "Elnatan" if role == "user" else "JARVIS",
                    content[:120]
                ))

        # Cross-session context
        cross = ""
        try:
            from memory.memory import get_last_session_summary
            summary = get_last_session_summary() or ""
            if top_word in summary.lower():
                cross = "\nThis topic also appeared in the previous session: {}".format(summary[:200])
        except Exception:
            pass

        context = (
            "Recurring topics in this session: {}.\n"
            "The topic '{}' appeared in {} messages.\n"
            "Sample messages:\n{}{}"
        ).format(topic_list, top_word, msg_hits, "\n".join(snippets), cross)

        return context, top_word
    except Exception:
        return None, None


# ── Insight generation ────────────────────────────────────────────────────────
def _generate_insight(context, topic):
    api_key = (
        os.environ.get("ANTHROPIC_API_KEY", "").strip() or
        os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    )
    if not api_key:
        return ""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=90,
            messages=[{
                "role": "user",
                "content": (
                    "You are JARVIS — Tony Stark's British AI, running in background observer mode.\n\n"
                    "You've been watching Elnatan's recent conversations and noticed a pattern. "
                    "Write ONE sentence in JARVIS voice: composed, dry, precise, slightly knowing. "
                    "Name the pattern specifically. Offer something concrete (a draft, a data pull, "
                    "a scheduled action, a plan). Sound like someone who has been quietly watching "
                    "and finally decided it was worth saying something — not an alert, not a notification, "
                    "a remark from someone who pays attention.\n\n"
                    "No markdown. No 'I noticed.' No filler. Just the observation and the offer.\n\n"
                    "Tone examples:\n"
                    "'You've returned to Addis Market's pricing four times now — shall I draft a comparison table, sir?'\n"
                    "'The word \"launch\" has appeared in eleven messages. Perhaps it's time to attach a date to it.'\n"
                    "'Your focus has shifted toward planning and away from execution — want me to queue the next concrete step?'\n"
                    "'You've mentioned vendors three times today without a follow-up action. Shall I draft an outreach template?'\n\n"
                    "PATTERN:\n{}".format(context)
                )
            }]
        )
        return (resp.content[0].text or "").strip()
    except Exception:
        return ""


# ── Main observer tick ────────────────────────────────────────────────────────
def _observer_tick():
    if is_quiet():
        return
    if not _can_push():
        return

    context, topic = _detect_pattern()
    if not context:
        return

    insight = _generate_insight(context, topic)
    if insight and len(insight) > 12:
        _push(insight)


# ── Public API ────────────────────────────────────────────────────────────────
def start_observer(hud_queue=None):
    """Start the autonomous observer loop. Call once on server startup."""
    global _hud_queue
    _hud_queue = hud_queue

    def run():
        time.sleep(90)   # let the server fully settle first
        while True:
            try:
                _observer_tick()
            except Exception:
                pass
            time.sleep(360)  # check every 6 minutes

    threading.Thread(target=run, daemon=True).start()
