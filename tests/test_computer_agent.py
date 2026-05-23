import pytest
from unittest.mock import patch


def test_unknown_action_is_rejected():
    from control.computer_agent import _execute_action
    result = _execute_action({"action": "delete_everything"})
    assert "not allowed" in result.lower() or "unknown" in result.lower()


def test_empty_action_is_rejected():
    from control.computer_agent import _execute_action
    result = _execute_action({})
    assert result  # must return a non-empty error string


def test_known_actions_are_in_allowlist():
    from control.computer_agent import ALLOWED_ACTIONS
    for action in ["click", "double_click", "right_click", "move", "type",
                   "key", "scroll", "drag", "wait", "done"]:
        assert action in ALLOWED_ACTIONS, f"'{action}' missing from ALLOWED_ACTIONS"


def test_destructive_key_requires_confirmation(monkeypatch):
    from control.computer_agent import _execute_action
    monkeypatch.setattr("builtins.input", lambda _: "no")
    with patch("pyautogui.hotkey") as mock_hotkey:
        result = _execute_action({"action": "key", "key": "cmd+q"})
        mock_hotkey.assert_not_called()
        assert "cancel" in result.lower() or "skip" in result.lower()


def test_safe_key_skips_confirmation(monkeypatch):
    from control.computer_agent import _execute_action
    calls = []
    monkeypatch.setattr("builtins.input", lambda _: calls.append(True) or "yes")
    with patch("pyautogui.press"):
        _execute_action({"action": "key", "key": "enter"})
        assert len(calls) == 0
