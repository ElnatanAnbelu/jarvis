import pytest
from control.code_executor import run_shell


def test_run_shell_basic_command():
    result = run_shell("echo hello")
    assert result["success"] is True
    assert result["stdout"] == "hello"


def test_run_shell_does_not_chain_commands():
    # With shell=True, the semicolon splits into two commands → two output lines.
    # With shell=False, everything is passed as arguments to echo → one line.
    result = run_shell("echo hello; echo injected")
    assert "\n" not in result["stdout"], "Semicolon must not trigger a second command"


def test_run_shell_timeout():
    result = run_shell("sleep 10", timeout=1)
    assert result["success"] is False
    assert "timed out" in result["error"].lower()


def test_run_shell_invalid_command():
    result = run_shell("thiscommanddoesnotexist_abc123")
    assert result["success"] is False
