"""Tests for brain/notify.py — Telegram opt-in for Second Brain alerts."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_no_push_when_opt_in_disabled(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BRAIN_ALERTS", raising=False)
    from brain.notify import maybe_telegram_brain_alert
    pushed = maybe_telegram_brain_alert(
        "Saved a note. [BRAIN: SAVED → Learning/X]",
        visibility="surface",
        tags=["BRAIN:SAVED → Learning/X"],
        agent="JARVIS",
    )
    assert pushed is False


def test_no_push_when_not_surface(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BRAIN_ALERTS", "1")
    from brain.notify import maybe_telegram_brain_alert
    pushed = maybe_telegram_brain_alert(
        "got it",
        visibility="collapsed",
        tags=[],
        agent="FRIDAY",
    )
    assert pushed is False


def test_no_push_when_only_searched(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BRAIN_ALERTS", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "fake")
    from brain.notify import maybe_telegram_brain_alert
    pushed = maybe_telegram_brain_alert(
        "Pulled the gym note. [BRAIN: SEARCHED]",
        visibility="surface",
        tags=["BRAIN:SEARCHED"],
        agent="JARVIS",
    )
    assert pushed is False  # SEARCHED is routine, not noteworthy


def test_no_push_when_only_suggest(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BRAIN_ALERTS", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "fake")
    from brain.notify import maybe_telegram_brain_alert
    pushed = maybe_telegram_brain_alert(
        "[BRAIN: suggest → Energy Patterns: late-night work]",
        visibility="surface",
        tags=["BRAIN:suggest → Energy Patterns"],
        agent="KAREN",
    )
    assert pushed is False  # suggestions don't qualify


def test_push_on_brain_saved(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BRAIN_ALERTS", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "fake")
    from brain.notify import maybe_telegram_brain_alert
    pushed = maybe_telegram_brain_alert(
        "Created the note. [BRAIN: SAVED → Learning/Atomic Habits]",
        visibility="surface",
        tags=["BRAIN:SAVED → Learning/Atomic Habits"],
        agent="JARVIS",
    )
    assert pushed is True


def test_push_on_brain_proposed(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BRAIN_ALERTS", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "fake")
    from brain.notify import maybe_telegram_brain_alert
    pushed = maybe_telegram_brain_alert(
        "Proposal staged. [BRAIN: PROPOSED → Relationships/Solomon]",
        visibility="surface",
        tags=["BRAIN:PROPOSED → Relationships/Solomon"],
        agent="JARVIS",
    )
    assert pushed is True


def test_push_on_grounded_observer_insight(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BRAIN_ALERTS", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "fake")
    from brain.notify import maybe_telegram_brain_alert
    pushed = maybe_telegram_brain_alert(
        "[OBS] You've returned to Atomic Habits four times. [BRAIN: GROUNDED]",
        visibility="surface",
        tags=["BRAIN:GROUNDED", "OBSERVER"],
        agent="JARVIS",
    )
    assert pushed is True


def test_format_truncates_long_text(monkeypatch):
    from brain.notify import _format_alert
    long_text = "x" * 1000
    out = _format_alert(long_text, "JARVIS", ["BRAIN:SAVED"])
    assert len(out) < 600
