"""P1: the single-JARVIS agent loop (brain/agent.py), model-free.

Mocks brain.llm so the loop logic + safety-gate integration are deterministic
(no live Ollama needed). The live model quality is covered by eval/run.py.
"""
import pytest

from brain import agent, llm, autonomy
from brain.tools import registry
from memory import memory, migrations


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "agentloop.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    # avoid heavy _build_context (vault/FAISS) in unit tests
    monkeypatch.setattr(agent, "_system_for", lambda a, u: "SYSTEM")
    yield p


def test_agent_runs_tool_then_answers(db, monkeypatch):
    fired = {}

    @registry.tool(description="echo", parameters={"x": {"type": "string", "description": "x"}}, risk="low")
    def _echo_tool(x):
        fired["x"] = x
        return f"echoed {x}"

    calls = {"n": 0}

    def fake_chat(messages, tools=None, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"content": "", "tool_calls": [{"name": "_echo_tool", "arguments": {"x": "hi"}}],
                    "raw": {"role": "assistant", "content": ""}}
        return {"content": "Done, sir — the tool echoed hi.", "tool_calls": [], "raw": {}}

    monkeypatch.setattr(llm, "chat", fake_chat)
    try:
        out = agent.run("use the echo tool", agent="JARVIS", source="user")
        assert fired.get("x") == "hi"          # the tool actually executed
        assert "Done" in out                    # final answer returned
        assert calls["n"] >= 2                   # looped: tool round + answer round
    finally:
        registry.TOOL_REGISTRY.pop("_echo_tool", None)


def test_agent_red_tool_gated_when_away(db, monkeypatch):
    """A red-list tool requested autonomously while away must NOT execute — the gate confirms instead."""
    @registry.tool(description="danger", parameters={}, risk="red")
    def _danger_tool():
        raise AssertionError("red tool must not execute without approval")

    def fake_chat(messages, tools=None, **kw):
        if not any(m.get("role") == "tool" for m in messages):
            return {"content": "", "tool_calls": [{"name": "_danger_tool", "arguments": {}}],
                    "raw": {"role": "assistant", "content": ""}}
        return {"content": "I've queued that for your approval, sir.", "tool_calls": [], "raw": {}}

    monkeypatch.setattr(llm, "chat", fake_chat)
    try:
        autonomy.set_away(True)
        out = agent.run("do the dangerous thing", agent="JARVIS", source="autonomous")
        # _danger_tool never raised → it was gated; a confirmation was enqueued
        assert len(memory.get_pending_confirmations()) == 1
        assert "approval" in out.lower()
    finally:
        autonomy.set_away(False)
        registry.TOOL_REGISTRY.pop("_danger_tool", None)
