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


def _push(text, visibility=None, tags=None):
    """Push a classified item onto the HUD queue.

    Emits a dict so proactive_poll receives pre-classified data without
    re-running the classifier. Legacy plain-string producers elsewhere
    are still handled by the drain site in ui/server.py.
    """
    global _last_push_at, _push_count_this_hour
    if _hud_queue is not None:
        try:
            item = {
                "text": text,
                "visibility": visibility or "surface",
                "tags": tags or [],
                "agent": "JARVIS",
                "source": "observer",
            }
            _hud_queue.put_nowait(item)
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


# ── B8: Second Brain grounding ────────────────────────────────────────────────
def _search_brain_for_topic(topic: str, max_chars: int = 800) -> str:
    """Query the Personal Second Brain for context on the detected topic.

    Returns a short excerpt (truncated to max_chars) if any vault notes
    are relevant; empty string otherwise. Failures are silent — the
    observer falls back to pattern-only insights.
    """
    if not topic:
        return ""
    try:
        from memory.vault import VaultManager
        import memory.vault as _vm
        # Reuse the singleton instance set up by brain/think.py if available
        if not hasattr(_vm, "_second_brain_instance"):
            _vm._second_brain_instance = VaultManager()
        result = _vm._second_brain_instance.search_vault(topic, max_results=2)
        if not result:
            return ""
        text = result.strip()
        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + "..."
        return text
    except Exception:
        return ""


# ── Pattern detection ─────────────────────────────────────────────────────────
def _detect_pattern():
    """
    Returns (context_str, topic, has_brain_grounding) if a noteworthy
    pattern is found, else (None, None, False).
    """
    global _last_pattern_hash
    try:
        from memory.memory import get_recent_history
        messages = get_recent_history(limit=80)
        if len(messages) < 8:
            return None, None, False

        topics = _top_topics(messages)
        if not topics:
            return None, None, False

        top_word, top_count = topics[0]

        # Require the word appears in at least 5 separate messages
        msg_hits = sum(1 for _, c in messages if top_word in c.lower())
        if msg_hits < 5:
            return None, None, False

        # Skip if we already surfaced this exact pattern
        pattern_hash = top_word + str(msg_hits)
        if pattern_hash == _last_pattern_hash:
            return None, None, False
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

        # B8: ground in Second Brain when the topic appears in the vault
        brain_excerpt = _search_brain_for_topic(top_word)
        brain_section = ""
        has_brain_grounding = False
        if brain_excerpt:
            brain_section = (
                "\n\nVAULT CONTEXT — recorded notes on this topic:\n{}"
            ).format(brain_excerpt)
            has_brain_grounding = True

        context = (
            "Recurring topics in this session: {}.\n"
            "The topic '{}' appeared in {} messages.\n"
            "Sample messages:\n{}{}{}"
        ).format(topic_list, top_word, msg_hits,
                 "\n".join(snippets), cross, brain_section)

        return context, top_word, has_brain_grounding
    except Exception:
        return None, None, False


# ── Insight generation ────────────────────────────────────────────────────────
def _generate_insight(context, topic):
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    is_oauth = False
    if not api_key or api_key.startswith("sk-ant-oat"):
        api_key = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
        is_oauth = True
    if not api_key:
        return ""
    try:
        # Fully-local default: don't reason over the user's data on a cloud model.
        from brain.agent import cloud_reasoning_allowed
        if not cloud_reasoning_allowed():
            return ""
        import anthropic
        client = anthropic.Anthropic(auth_token=api_key) if is_oauth else anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=90,
            messages=[{
                "role": "user",
                "content": (
                    "CRITICAL OUTPUT RULES — HIGHEST PRIORITY, NO EXCEPTIONS:\n"
                    "- NEVER prefix your response with \"JARVIS:\" or any agent name\n"
                    "- NEVER wrap your response in quotation marks\n"
                    "- NEVER mention Tony Stark, Iron Man, Peter Parker, or the Marvel movies — you belong to Elnatan only, always have\n"
                    "- Keep responses concise. Only go long when explicitly asked for detailed analysis\n"
                    "- NEVER initiate greetings unless the user greets first\n"
                    "- No markdown for conversation. No asterisks, bullet dashes, or headers\n"
                    "- NEVER invent facts about Elnatan not explicitly in memory\n\n"
                    "You are JARVIS — Elnatan's AI, running in background observer mode.\n\n"
                    "You've been watching Elnatan's recent conversations and noticed a pattern. "
                    "Write ONE sentence in JARVIS voice: composed, dry, precise, slightly knowing. "
                    "Name the pattern specifically. Offer something concrete (a draft, a data pull, "
                    "a scheduled action, a plan). Sound like someone who has been quietly watching "
                    "and finally decided it was worth saying something — not an alert, not a notification, "
                    "a remark from someone who pays attention.\n\n"
                    "No markdown. No 'I noticed.' No filler. Just the observation and the offer.\n\n"
                    "GROUNDING RULE: If the PATTERN block contains a 'VAULT CONTEXT' section, "
                    "your observation MUST be grounded in that recorded data — reference what is "
                    "actually noted (not invented). If no VAULT CONTEXT is present, the observation "
                    "is pattern-only; do not pretend to recall vault content you don't have.\n\n"
                    "Tone examples:\n"
                    "'You've returned to Atomic Habits four times now — your reading note still says chapter three; want me to update it?'\n"
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

    context, topic, has_brain_grounding = _detect_pattern()
    if not context:
        return

    insight = _generate_insight(context, topic)
    if insight and len(insight) > 12:
        # B8: tag insights grounded in vault content so the HUD chip system
        # (B5) shows the green grounding chip and the visibility classifier
        # (B6) routes appropriately.
        if has_brain_grounding:
            insight = insight.rstrip() + " [BRAIN: GROUNDED]"
        full_text = "[OBS] " + insight
        # Classify before pushing so the HUD receives enriched data without
        # needing a second pass at the drain site.
        try:
            from brain.visibility import classify as _classify
            vis = _classify(full_text, agent="JARVIS", source="observer")
        except Exception:
            vis = {"visibility": "surface", "tags": ["OBSERVER"]}
        _push(full_text, vis["visibility"], vis["tags"])


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
