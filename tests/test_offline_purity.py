"""Regression: in the default fully-local mode, NO cloud LLM may serve the
reasoning path (the blocking offline-purity gate).

The audit found router.route_stream sent deep-research / document-gen / team-mode
to Anthropic BEFORE the local brain was consulted, and think_stream fell to the
cloud whenever the local model produced nothing. These tests pin the switch:
cloud_reasoning_allowed() is False by default, and the cloud branches are then
skipped in favor of the local brain.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import brain.agent as agent


def test_cloud_reasoning_off_by_default(monkeypatch):
    monkeypatch.delenv("JARVIS_ALLOW_CLOUD_BRAIN", raising=False)
    monkeypatch.delenv("JARVIS_LOCAL_BRAIN", raising=False)
    assert agent.cloud_reasoning_allowed() is False


def test_cloud_reasoning_opt_in(monkeypatch):
    monkeypatch.setenv("JARVIS_ALLOW_CLOUD_BRAIN", "1")
    assert agent.cloud_reasoning_allowed() is True


def test_cloud_allowed_when_local_brain_disabled(monkeypatch):
    monkeypatch.delenv("JARVIS_ALLOW_CLOUD_BRAIN", raising=False)
    monkeypatch.setenv("JARVIS_LOCAL_BRAIN", "0")
    assert agent.cloud_reasoning_allowed() is True


def _drain(gen):
    return "".join(v for t, v in gen if t == "chunk")


def test_router_skips_cloud_branches_in_local_mode(monkeypatch):
    """deep-research / doc-gen triggers must NOT call the cloud functions when
    local-only; they fall through to the single local Alfred brain."""
    import brain.router as router
    import brain.research as research
    import brain.reader as reader
    import brain.think as think

    monkeypatch.setattr(agent, "cloud_reasoning_allowed", lambda: False)

    called = {"cloud": False}

    def _boom(*a, **k):
        called["cloud"] = True
        raise AssertionError("cloud reasoning path was invoked in local-only mode")

    # Make every trigger match, then prove none of the cloud fns run.
    monkeypatch.setattr(research, "is_research_request", lambda x: True)
    monkeypatch.setattr(research, "deep_research", _boom)
    monkeypatch.setattr(reader, "is_doc_gen_request", lambda x: (True, "report"))
    monkeypatch.setattr(reader, "generate_document", _boom)

    def fake_think_stream(user_input, agent=None, source="user", **k):
        yield "LOCAL-BRAIN-ANSWER"

    monkeypatch.setattr(think, "think_stream", fake_think_stream)

    out = _drain(router.route_stream("write a report on Addis Market"))
    assert called["cloud"] is False
    assert "LOCAL-BRAIN-ANSWER" in out


def test_router_uses_cloud_branch_when_opted_in(monkeypatch):
    """Sanity: the switch is a gate, not a removal — with cloud allowed, the
    research branch IS taken."""
    import brain.router as router
    import brain.research as research
    import brain.reader as reader

    monkeypatch.setattr(agent, "cloud_reasoning_allowed", lambda: True)
    monkeypatch.setattr(reader, "is_doc_gen_request", lambda x: (False, None))
    monkeypatch.setattr(research, "is_research_request", lambda x: True)

    used = {"research": False}

    def fake_research(x):
        used["research"] = True
        yield "CLOUD-RESEARCH"

    monkeypatch.setattr(research, "deep_research", fake_research)

    out = _drain(router.route_stream("deep dive on Ethiopian fintech"))
    assert used["research"] is True
    assert "CLOUD-RESEARCH" in out
