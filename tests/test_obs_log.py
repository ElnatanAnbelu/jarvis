"""P4: structured observability (obs/log.py) + execute_tool instrumentation."""
import pytest

from obs import log
from brain.tools import registry
from memory import memory, migrations


def test_correlation_roundtrip():
    cid = log.new_correlation("abc123")
    assert cid == "abc123"
    assert log.correlation_id() == "abc123"


def test_heartbeat_and_liveness():
    log.heartbeat("unittest_daemon")
    lv = log.liveness()
    assert "unittest_daemon" in lv
    assert lv["unittest_daemon"]["stale"] is False
    assert lv["unittest_daemon"]["last_tick"] >= 0


def test_log_helpers_never_raise():
    log.log_event("test.event", level="info", a=1, b="x")
    log.log_exception("test.boom", k="v")  # no active exception → still safe


def test_execute_tool_emits_structured_event(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "DB_PATH", str(tmp_path / "obs.db"))
    monkeypatch.setattr(migrations, "DB_PATH", str(tmp_path / "obs.db"))
    memory.init_db()

    events = []
    monkeypatch.setattr(registry, "_obs", lambda ev, **k: events.append((ev, k)))

    @registry.tool(description="obs test", parameters={}, risk="low")
    def _obs_probe_tool():
        return "ok"

    try:
        out = registry.execute_tool("_obs_probe_tool", {}, agent="JARVIS", source="user")
        assert out == "ok"
        assert any(ev == "tool.executed" for ev, _ in events)
        ev_fields = next(k for ev, k in events if ev == "tool.executed")
        assert ev_fields["tool"] == "_obs_probe_tool"
        assert "duration_ms" in ev_fields
    finally:
        registry.TOOL_REGISTRY.pop("_obs_probe_tool", None)
