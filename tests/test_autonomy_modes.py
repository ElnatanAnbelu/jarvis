"""P5: supervised→auto shakeout switch + the autonomous runner's pause respect."""
import pytest

from brain import autonomy, runner
from brain.tools import registry
from memory import memory, migrations


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "modes.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    yield p


def test_supervised_queues_autonomous_low_risk(db):
    sink = {}

    @registry.tool(description="sup low", parameters={}, risk="low")
    def _sup_low():
        sink["ran"] = True
        return "ran"

    try:
        autonomy.set_autonomy_mode("supervised")
        out = registry.execute_tool("_sup_low", {}, source="autonomous")
        assert "ran" not in sink                       # NOT executed
        assert "approval" in out.lower() or "supervised" in out.lower()
        assert len(memory.get_pending_confirmations()) == 1
    finally:
        registry.TOOL_REGISTRY.pop("_sup_low", None)


def test_auto_executes_autonomous_low_risk(db):
    sink = {}

    @registry.tool(description="auto low", parameters={}, risk="low")
    def _auto_low():
        sink["ran"] = True
        return "ran"

    try:
        autonomy.set_autonomy_mode("auto")
        out = registry.execute_tool("_auto_low", {}, source="autonomous")
        assert sink.get("ran") is True                 # executed in auto mode
        assert out == "ran"
    finally:
        registry.TOOL_REGISTRY.pop("_auto_low", None)


def test_auto_red_still_confirms_when_away(db):
    sink = {}

    @registry.tool(description="auto red", parameters={}, risk="red")
    def _auto_red():
        sink["ran"] = True
        return "ran"

    try:
        autonomy.set_autonomy_mode("auto")
        autonomy.set_away(True)
        out = registry.execute_tool("_auto_red", {}, source="autonomous")
        assert "ran" not in sink                       # red always confirms
        assert len(memory.get_pending_confirmations()) == 1
    finally:
        autonomy.set_away(False)
        registry.TOOL_REGISTRY.pop("_auto_red", None)


def test_runner_respects_pause(db):
    autonomy.set_paused(True)
    try:
        out = runner.run_goal("do something autonomous")
        assert "paused" in out.lower()                 # never calls the model when paused
    finally:
        autonomy.set_paused(False)


def test_panic_halts_and_rejects_pending(db):
    @registry.tool(description="panic probe", parameters={}, risk="low")
    def _panic_probe():
        return "ran"

    try:
        autonomy.set_autonomy_mode("supervised")
        registry.execute_tool("_panic_probe", {}, source="autonomous")  # queued by supervised
        assert len(memory.get_pending_confirmations()) == 1
        out = autonomy.panic()
        assert autonomy.is_paused() is True
        assert len(memory.get_pending_confirmations()) == 0   # all rejected
        assert "panic" in out.lower()
    finally:
        autonomy.set_paused(False)
        registry.TOOL_REGISTRY.pop("_panic_probe", None)


def test_revert_recent_undoes_reversible_actions(db):
    sink = {}

    @registry.tool(description="inverse", parameters={}, risk="low")
    def _inv_probe():
        sink["undone"] = True
        return "undone"

    try:
        memory.log_action("did_thing", {}, "result", success=True,
                          inverse_tool="_inv_probe", inverse_args={})
        msg = memory.revert_recent(60)
        assert sink.get("undone") is True
        assert "reverted 1" in msg
    finally:
        registry.TOOL_REGISTRY.pop("_inv_probe", None)


def test_source_threads_through_think(monkeypatch):
    """think(source=...) must reach the agent (which passes it to the gate)."""
    from brain import think as T, agent
    cap = {}
    monkeypatch.setattr(agent, "enabled", lambda: True)

    def fake_run(ui, agent="JARVIS", source="user"):
        cap["source"] = source
        return "ok"

    monkeypatch.setattr(agent, "run", fake_run)
    monkeypatch.setattr(T, "save_message", lambda *a, **k: None)
    monkeypatch.setattr(T, "learn", lambda *a, **k: None)
    out = T.think("send an email to a stranger", source="external")
    assert cap["source"] == "external"
    assert out == "ok"
