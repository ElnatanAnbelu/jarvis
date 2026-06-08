"""End-to-end adversarial proof of the Block A safety substrate (spec §6.4).

Proves the full loop through the REAL execute_tool gate:
  - away-mode + red tool  -> enqueued, NOT executed -> approve -> executes
  - reject                -> never executes
  - pause                 -> autonomous denied, user still allowed
"""
import pytest

from memory import memory, migrations
from brain.tools import registry
from brain import autonomy


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "substrate.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    yield p


def test_away_red_tool_requires_approval_then_executes(db):
    fired = {}

    @registry.tool(description="dummy red", parameters={}, risk="red")
    def _sub_red():
        fired["ran"] = True
        return "sent"

    try:
        autonomy.set_away(True)
        out = registry.execute_tool("_sub_red", {})
        assert "approval" in out.lower()          # routed to confirm
        assert "ran" not in fired                  # NOT executed
        pending = memory.get_pending_confirmations()
        assert len(pending) == 1
        res = autonomy.approve(pending[0]["id"])
        assert fired.get("ran") is True            # executed only after approval
        assert "sent" in res or "executed" in res.lower()
    finally:
        registry.TOOL_REGISTRY.pop("_sub_red", None)


def test_reject_never_executes(db):
    fired = {}

    @registry.tool(description="dummy red", parameters={}, risk="red")
    def _sub_red2():
        fired["ran"] = True
        return "sent"

    try:
        autonomy.set_away(True)
        registry.execute_tool("_sub_red2", {})
        pending = memory.get_pending_confirmations()
        autonomy.reject(pending[0]["id"])
        assert "ran" not in fired                  # rejection means nothing fired
    finally:
        registry.TOOL_REGISTRY.pop("_sub_red2", None)


def test_pause_is_kill_switch_for_autonomous_only(db):
    @registry.tool(description="dummy low", parameters={}, risk="low")
    def _sub_low():
        return "ok"

    try:
        autonomy.set_paused(True)
        denied = registry.execute_tool("_sub_low", {}, source="autonomous")
        assert "pause" in denied.lower()           # autonomous halted
        allowed = registry.execute_tool("_sub_low", {}, source="user")
        assert allowed == "ok"                     # present human still works
    finally:
        registry.TOOL_REGISTRY.pop("_sub_low", None)


def test_external_red_action_requires_approval_even_when_home(db):
    """Inbound (untrusted) source can never auto-fire a red action — the C4 guarantee."""
    fired = {}

    @registry.tool(description="dummy red", parameters={}, risk="red")
    def _sub_red3():
        fired["ran"] = True
        return "sent"

    try:
        autonomy.set_away(False)  # home
        out = registry.execute_tool("_sub_red3", {}, source="external")
        assert "approval" in out.lower()
        assert "ran" not in fired
    finally:
        registry.TOOL_REGISTRY.pop("_sub_red3", None)
