"""Regression: the computer-use channel (real mouse/keyboard/AppleScript) must
respect the safety net (the P0 'computer-use bypasses the gate' finding).

- control_screen is red-list. Per the owner's explicit choice it is an
  OWNER-OPERATOR tool: a present owner runs it frictionlessly (even in away-mode),
  but EXTERNAL/injected content can never fire it (and autonomous use needs the
  'system' domain flipped to auto). The injection defense is the load-bearing part.
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


def test_owner_runs_control_screen_even_when_away(monkeypatch):
    # Owner's choice: frictionless computer control. A PRESENT owner runs it even in
    # away-mode (it's still him asking). Injected/external content still can't — see below.
    monkeypatch.setattr(autonomy, "is_away", lambda: True)
    d = autonomy.gate("control_screen", {"task": "open mail"}, source="user", risk="red")
    assert d.get("action") == "execute"


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
