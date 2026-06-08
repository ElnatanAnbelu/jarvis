"""
Tests for wiring the central autonomy safety gate into tool execution
(brain/tools/registry.execute_tool) and the red-risk tagging on the @tool
decorator.

Covers:
  - a red tool with away_mode ON returns a "needs approval" message and does
    NOT execute (it enqueues a confirmation instead);
  - the same red tool with away_mode OFF + source="user" executes normally;
  - when paused, a source="autonomous" call is denied while a source="user"
    call still runs (the kill-switch blocks non-user actions only);
  - _bypass_gate=True executes a red tool without enqueuing a confirmation;
  - a low-risk tool always executes;
  - existing per-agent ACL behavior is preserved.

DB isolation mirrors tests/test_safety_ledger.py: memory.memory.DB_PATH (and the
migrations module's DB_PATH) are pointed at a per-test temp file so the real
jarvis.db is never touched. autonomy reads/writes flags + confirmations through
memory, so patching memory's DB_PATH isolates the gate too.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolated memory DB + registered dummy tools (one red, one low).

    Returns a namespace with the memory module, the registry module, and the
    names of the two dummy tools plus a call-counter dict the tools mutate so
    tests can assert whether the underlying function actually ran.
    """
    import memory.memory as m
    import memory.migrations as mig

    db = tmp_path / "jarvis_test.db"
    monkeypatch.setattr(m, "DB_PATH", db)
    monkeypatch.setattr(mig, "DB_PATH", db)
    m.init_db()  # base tables + migrations against the temp DB

    import brain.tools.registry as reg

    calls = {"red": 0, "low": 0, "acl": 0}

    @reg.tool(
        description="dummy irreversible tool",
        parameters={"x": {"type": "string", "description": "x"}},
        risk="red",
    )
    def _gate_test_red(x: str = "") -> str:
        calls["red"] += 1
        return f"red-ran:{x}"

    @reg.tool(
        description="dummy low-risk tool",
        parameters={"x": {"type": "string", "description": "x"}},
    )
    def _gate_test_low(x: str = "") -> str:
        calls["low"] += 1
        return f"low-ran:{x}"

    @reg.tool(
        description="dummy JARVIS-only tool",
        parameters={},
        allowed_agents=["JARVIS"],
    )
    def _gate_test_jarvis_only() -> str:
        calls["acl"] += 1
        return "acl-ran"

    class _Env:
        pass

    e = _Env()
    e.m = m
    e.reg = reg
    e.calls = calls
    e.RED = "_gate_test_red"
    e.LOW = "_gate_test_low"
    e.ACL = "_gate_test_jarvis_only"

    yield e

    # Keep the global registry clean for other tests in the suite.
    for name in (e.RED, e.LOW, e.ACL):
        reg.TOOL_REGISTRY.pop(name, None)


# ── risk tagging on the decorator ────────────────────────────────────────────

def test_decorator_stores_risk(env):
    assert env.reg.TOOL_REGISTRY[env.RED]["risk"] == "red"
    assert env.reg.TOOL_REGISTRY[env.LOW]["risk"] == "low"


def test_shipped_red_tools_are_tagged(env):
    """The real irreversible tools must carry risk='red' once imported."""
    import brain.tools.messaging  # noqa: F401 - registers send_* tools
    import brain.tools.files      # noqa: F401 - registers delete_file
    import brain.tools.code       # noqa: F401 - registers run_shell/exec/push

    reg = env.reg
    for name in ("send_email", "send_imessage", "send_whatsapp",
                 "delete_file", "run_shell", "execute_code", "git_push"):
        assert reg.TOOL_REGISTRY[name]["risk"] == "red", name


# ── away-mode → confirm ───────────────────────────────────────────────────────

def test_red_tool_away_mode_needs_approval_and_does_not_execute(env):
    env.m.set_flag("away_mode", True)

    result = env.reg.execute_tool(env.RED, {"x": "hi"}, agent="JARVIS")

    assert "needs your approval" in result
    assert env.calls["red"] == 0  # NOT executed

    # A confirmation was enqueued for the human to approve.
    pending = env.m.get_pending_confirmations()
    assert len(pending) == 1
    assert pending[0]["tool_name"] == env.RED
    assert pending[0]["status"] == "pending"


def test_red_tool_away_off_user_executes(env):
    env.m.set_flag("away_mode", False)

    result = env.reg.execute_tool(env.RED, {"x": "yo"}, agent="JARVIS", source="user")

    assert result == "red-ran:yo"
    assert env.calls["red"] == 1
    assert env.m.get_pending_confirmations() == []  # nothing queued


# ── paused kill-switch ────────────────────────────────────────────────────────

def test_paused_denies_autonomous_but_allows_user(env):
    env.m.set_flag("paused", True)
    env.m.set_flag("away_mode", False)

    # Autonomous low-risk call is denied by the kill-switch.
    denied = env.reg.execute_tool(env.LOW, {"x": "a"}, agent="JARVIS",
                                  source="autonomous")
    assert "blocked" in denied.lower()
    assert env.calls["low"] == 0

    # A present-human (source="user") call still runs.
    ran = env.reg.execute_tool(env.LOW, {"x": "b"}, agent="JARVIS",
                               source="user")
    assert ran == "low-ran:b"
    assert env.calls["low"] == 1


# ── _bypass_gate ─────────────────────────────────────────────────────────────

def test_bypass_gate_executes_red_tool_without_enqueuing(env):
    env.m.set_flag("away_mode", True)  # would normally force confirm

    result = env.reg.execute_tool(env.RED, {"x": "z"}, agent="JARVIS",
                                  _bypass_gate=True)

    assert result == "red-ran:z"
    assert env.calls["red"] == 1
    assert env.m.get_pending_confirmations() == []  # gate skipped, no queue


# ── low-risk always runs ──────────────────────────────────────────────────────

def test_low_risk_tool_always_executes(env):
    # Even in away-mode, a low-risk user action runs without confirmation.
    env.m.set_flag("away_mode", True)
    env.m.set_flag("paused", False)

    result = env.reg.execute_tool(env.LOW, {"x": "ok"}, agent="JARVIS",
                                  source="user")
    assert result == "low-ran:ok"
    assert env.calls["low"] == 1
    assert env.m.get_pending_confirmations() == []


# ── ACL preserved ─────────────────────────────────────────────────────────────

def test_acl_blocks_disallowed_agent_before_gate(env):
    # A non-allowed agent is refused with the ACL message and never runs.
    refused = env.reg.execute_tool(env.ACL, {}, agent="Observer")
    assert "not available to Observer" in refused
    assert env.calls["acl"] == 0


def test_acl_allows_permitted_agent(env):
    env.m.set_flag("paused", False)
    env.m.set_flag("away_mode", False)
    ok = env.reg.execute_tool(env.ACL, {}, agent="JARVIS", source="user")
    assert ok == "acl-ran"
    assert env.calls["acl"] == 1


def test_acl_no_agent_runs(env):
    """agent=None preserves the legacy no-filtering path."""
    env.m.set_flag("paused", False)
    env.m.set_flag("away_mode", False)
    ok = env.reg.execute_tool(env.ACL, {}, source="user")
    assert ok == "acl-ran"
    assert env.calls["acl"] == 1
