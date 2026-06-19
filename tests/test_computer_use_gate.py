"""Regression: the computer-use channel (real mouse/keyboard/AppleScript) must
respect the safety net (the P0 'computer-use bypasses the gate' finding).

- control_screen is red-list → confirms when away / from an external source.
- The agent loop honors the pause/panic kill-switch (refuses to start, aborts
  mid-run) so panic actually halts a running screen-control task.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import brain.autonomy as autonomy
from control.agent import get_agent


def test_control_screen_is_red_list():
    assert autonomy.is_red("control_screen")
    assert autonomy.is_red("control_screen", "red")


def test_control_screen_confirms_when_away(monkeypatch):
    monkeypatch.setattr(autonomy, "is_away", lambda: True)
    d = autonomy.gate("control_screen", {"task": "open mail"}, source="user", risk="red")
    assert d.get("action") == "confirm"


def test_control_screen_confirms_from_external(monkeypatch):
    monkeypatch.setattr(autonomy, "is_away", lambda: False)
    d = autonomy.gate("control_screen", {"task": "open mail"}, source="external", risk="red")
    assert d.get("action") == "confirm"


def test_agent_refuses_to_start_while_paused(monkeypatch):
    monkeypatch.setattr(autonomy, "is_paused", lambda: True)
    out = get_agent().run("open safari")
    assert "paused" in out.lower()


def test_agent_aborts_mid_run_when_paused(monkeypatch):
    """_should_abort must return True when the kill-switch is active, regardless
    of the local stop flag — so panic halts a task already in progress."""
    monkeypatch.setattr(autonomy, "is_paused", lambda: True)
    assert get_agent()._should_abort() is True
    monkeypatch.setattr(autonomy, "is_paused", lambda: False)
    ag = get_agent()
    ag._abort = False
    assert ag._should_abort() is False
