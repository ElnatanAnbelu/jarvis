"""Regression: a stuck local model re-issuing the SAME tool call must not get it
re-executed every round (wasted work + duplicate gated prompts), and the
confirmation queue must dedup identical pending calls (second-audit P3s)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain import agent
from brain.tools import registry
from memory import memory, migrations


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "dedup.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    yield p


def test_identical_tool_call_executes_once_per_run(db, monkeypatch):
    runs = {"n": 0}

    @registry.tool(description="counter", parameters={})
    def _loop_probe():
        runs["n"] += 1
        return "ok"

    try:
        monkeypatch.setattr(agent, "_select_tools", lambda *a, **k: [])
        monkeypatch.setattr(agent, "_system_for", lambda *a, **k: "sys")
        monkeypatch.setattr(agent.llm, "select_tier", lambda x: "m")
        # model is stuck: same tool call every round, never answers
        monkeypatch.setattr(agent.llm, "chat", lambda *a, **k: {
            "tool_calls": [{"name": "_loop_probe", "arguments": {}}],
            "raw": {"role": "assistant"}, "content": "",
        })
        agent._resolve_tools("do the thing", "JARVIS", "user")
        assert runs["n"] == 1, f"stuck call executed {runs['n']} times (no dedup)"
    finally:
        registry.TOOL_REGISTRY.pop("_loop_probe", None)


def test_enqueue_confirmation_dedups_identical_pending(db):
    a = memory.enqueue_confirmation("send_email", {"to": "x@y.com", "body": "hi"}, risk="red")
    b = memory.enqueue_confirmation("send_email", {"to": "x@y.com", "body": "hi"}, risk="red")
    c = memory.enqueue_confirmation("send_email", {"to": "z@y.com", "body": "hi"}, risk="red")
    assert a == b and a != c
    assert len(memory.get_pending_confirmations()) == 2
