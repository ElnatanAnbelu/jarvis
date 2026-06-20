"""P1: the local model-tier router + tool routing (model-free)."""
from brain import agent, llm


def test_select_tier_fast_vs_complex(monkeypatch):
    monkeypatch.setattr(llm, "has_model", lambda m=None: True)
    # Short conversational turns ALWAYS stay fast — snappy voice, never lag the Mac,
    # even when they contain a "complex" word.
    assert llm.select_tier("hey sir, how are you") == llm.FAST_MODEL
    assert llm.select_tier("analyze the strategy and compare the options") == llm.FAST_MODEL
    # Genuinely heavy work escalates: a long request, OR a substantial one carrying a
    # real complexity signal.
    assert llm.select_tier("word " * 90) == llm.COMPLEX_MODEL                       # long → escalate
    assert llm.select_tier("please " + "context " * 18 + "refactor this architecture") == llm.COMPLEX_MODEL


def test_select_tier_lock_fast_env(monkeypatch):
    monkeypatch.setattr(llm, "has_model", lambda m=None: True)
    monkeypatch.setenv("JARVIS_LOCK_FAST_MODEL", "1")
    assert llm.select_tier("draft a full strategic analysis " + "word " * 90) == llm.FAST_MODEL


def test_select_tier_falls_back_when_preferred_missing(monkeypatch):
    # complex desired, but only the fast model is pulled → use fast
    monkeypatch.setattr(llm, "has_model", lambda m=None: m == llm.FAST_MODEL)
    assert llm.select_tier("analyze the strategy") == llm.FAST_MODEL


def test_select_tools_caps_and_includes_core_and_relevant():
    tools = agent._select_tools("send an email to my friend", "JARVIS")
    names = {t["name"] for t in tools}
    assert len(tools) <= agent.MAX_TOOLS          # routed subset, not all ~130
    assert "send_email" in names                   # core + keyword match
    assert "read_file" in names                    # always-on core
    # a clearly-irrelevant tool should not crowd in for this short request
    assert "business_financials" not in names
