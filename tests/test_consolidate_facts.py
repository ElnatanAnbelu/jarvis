"""Regression for consolidate_facts (second-audit data-loss + exfiltration):
  - it must NOT ship the fact store to the cloud in local-only mode;
  - it must delete only the rows it READ, so a fact saved during the LLM call
    survives (was wiped by a blanket DELETE FROM facts);
  - if the model returns implausibly few facts, keep the originals.
"""
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mem(tmp_path, monkeypatch):
    from memory import memory, migrations
    db = str(tmp_path / "j.db")
    monkeypatch.setattr(memory, "DB_PATH", db)
    monkeypatch.setattr(migrations, "DB_PATH", db)
    memory.init_db()
    return memory


def _seed(memory, n):
    for i in range(n):
        memory.save_fact("cat", f"key{i}", f"val{i}")


def _fake_anthropic(cleaned_text, on_create=None):
    class _Msg:
        content = [types.SimpleNamespace(text=cleaned_text)]

    class _M:
        def create(self, *a, **k):
            if on_create:
                on_create()
            return _Msg()

    class _Client:
        def __init__(self, *a, **k):
            self.messages = _M()

    return _Client


def test_no_cloud_call_in_local_only_mode(mem, monkeypatch):
    import brain.agent as agent
    monkeypatch.setattr(agent, "cloud_reasoning_allowed", lambda: False)
    _seed(mem, 6)
    before = mem.get_facts()
    mem.consolidate_facts()                # must early-return, no cloud, no DELETE
    assert mem.get_facts() == before


def test_concurrent_insert_survives(mem, monkeypatch):
    import brain.agent as agent
    import anthropic
    monkeypatch.setattr(agent, "cloud_reasoning_allowed", lambda: True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    _seed(mem, 6)

    cleaned = "\n".join(f"[cat] key{i}: val{i}" for i in range(6))
    # a fact saved WHILE the LLM "runs" — must not be wiped by consolidation
    inject = lambda: mem.save_fact("cat", "concurrent_key", "survives")
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic(cleaned, on_create=inject))

    mem.consolidate_facts()
    facts = mem.get_facts()
    assert "concurrent_key" in facts, "fact saved during consolidation was wiped"
    assert "key0" in facts and "key5" in facts


def test_safety_floor_keeps_originals(mem, monkeypatch):
    import brain.agent as agent
    import anthropic
    monkeypatch.setattr(agent, "cloud_reasoning_allowed", lambda: True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    _seed(mem, 8)

    # model returned only 1 fact (truncation/garbage) — far below half of 8
    monkeypatch.setattr(anthropic, "Anthropic", _fake_anthropic("[cat] key0: val0"))

    before = set(mem.get_facts().splitlines())
    mem.consolidate_facts()
    assert set(mem.get_facts().splitlines()) == before, "originals lost to a tiny result"
