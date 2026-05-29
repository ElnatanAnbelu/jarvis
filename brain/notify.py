"""
Cross-device notification for Second Brain activity.

Mirrors the HUD notification badge (B7) but for Telegram. Opt-in via
TELEGRAM_BRAIN_ALERTS=1 env var. Designed to give Elnatan optional
cross-device awareness without re-introducing the noise of the
disabled proactive scheduler.

Rules:
  - Telegram push only fires for visibility == "surface" AND tags
    contain a BRAIN action (SAVED, PROPOSED, UPDATED, APPROVED,
    REJECTED, GROUNDED). SEARCHED and suggest tags do NOT push.
  - Push is fire-and-forget on a background thread — never blocks
    the SSE stream.
  - Same filter philosophy as B7: signal, not noise.
"""
import os
import threading
from typing import Optional


def _is_opted_in() -> bool:
    return os.environ.get("TELEGRAM_BRAIN_ALERTS", "").strip() in ("1", "true", "yes", "on")


def _has_brain_action(tags) -> bool:
    """True if any tag is a BRAIN action that warrants a push.

    SEARCHED and suggest do not qualify — they're routine, not noteworthy.
    """
    if not tags:
        return False
    for t in tags:
        if not isinstance(t, str) or not t.startswith("BRAIN:"):
            continue
        inner = t[len("BRAIN:"):].strip().lower()
        if inner.startswith("suggest"):
            continue
        if inner.startswith("searched"):
            continue
        return True
    return False


def _format_alert(text: str, agent: Optional[str], tags) -> str:
    """Build the Telegram message body. Short, scannable, no noise."""
    head = f"⬡ Second Brain — {agent or 'JARVIS'}"
    snippet = (text or "").replace("[BRAIN:", "\n[BRAIN:").strip()
    if len(snippet) > 500:
        snippet = snippet[:500].rstrip() + "..."
    return f"{head}\n\n{snippet}"


def _send_telegram(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not (token and chat_id):
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=6,
        )
    except Exception:
        pass


def maybe_telegram_brain_alert(text: str, visibility: str,
                               tags=None, agent: Optional[str] = None) -> bool:
    """Maybe push a Telegram alert for this message. Returns True if pushed.

    The return value is mainly for testability — production callers don't
    need it. The actual send happens on a background thread.
    """
    if not _is_opted_in():
        return False
    if visibility != "surface":
        return False
    if not _has_brain_action(tags):
        return False
    body = _format_alert(text, agent, tags)
    threading.Thread(target=_send_telegram, args=(body,), daemon=True).start()
    return True
