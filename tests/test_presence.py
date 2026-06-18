"""P5: presence-based away-mode + the away digest (model-free)."""
from brain import presence, runner


def test_idle_seconds_parses_ioreg(monkeypatch):
    fake = 'foo\n    "HIDIdleTime" = 12000000000\nbar\n'  # 12s in ns
    monkeypatch.setattr(presence.subprocess, "check_output", lambda *a, **k: fake)
    assert abs(presence.idle_seconds() - 12.0) < 0.1


def test_idle_seconds_safe_on_error(monkeypatch):
    def boom(*a, **k):
        raise OSError("no ioreg")
    monkeypatch.setattr(presence.subprocess, "check_output", boom)
    assert presence.idle_seconds() == 0.0


def test_is_away_threshold(monkeypatch):
    monkeypatch.setattr(presence, "screen_locked", lambda: False)
    monkeypatch.setattr(presence, "idle_seconds", lambda: presence.AWAY_IDLE_SECS + 1)
    assert presence.is_away() is True
    monkeypatch.setattr(presence, "idle_seconds", lambda: 1.0)
    assert presence.is_away() is False


def test_screen_lock_forces_away(monkeypatch):
    monkeypatch.setattr(presence, "screen_locked", lambda: True)
    monkeypatch.setattr(presence, "idle_seconds", lambda: 0.0)
    assert presence.is_away() is True


def test_build_digest(monkeypatch):
    from memory import memory
    monkeypatch.setattr(memory, "get_recent_actions", lambda limit=15: "")
    assert "Nothing to report" in runner.build_digest()
    monkeypatch.setattr(memory, "get_recent_actions", lambda limit=15: "[t] send_email(to=x) -> OK")
    out = runner.build_digest()
    assert "handled" in out.lower() and "send_email" in out
