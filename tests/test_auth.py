"""P0: the consolidated auth (brain/auth.py) — guards against the tuple-as-api_key
crash class that broke vision / documents / briefings / computer-use."""
import pytest

from brain import auth


def test_get_auth_key_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api-xyz")
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    assert auth.get_auth_key() == ("sk-ant-api-xyz", False)


def test_get_auth_key_oauth(monkeypatch):
    # an sk-ant-oat* value in ANTHROPIC_API_KEY must NOT be treated as an api key
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-oat-abc")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-tok")
    assert auth.get_auth_key() == ("oauth-tok", True)


def test_get_auth_key_none(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    assert auth.get_auth_key() == (None, False)


def test_make_client_none_when_no_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    assert auth.make_client() is None


def test_make_client_uses_correct_kwarg(monkeypatch):
    """OAuth → auth_token=, plain key → api_key= (the bug was passing a tuple)."""
    import anthropic
    calls = {}

    class FakeClient:
        def __init__(self, **kw):
            calls.update(kw)

    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)

    auth.make_client("plainkey", False)
    assert calls == {"api_key": "plainkey"}

    calls.clear()
    auth.make_client("oauthtok", True)
    assert calls == {"auth_token": "oauthtok"}


def test_think_get_auth_key_delegates(monkeypatch):
    """brain.think._get_auth_key must return the same tuple shape (no drift)."""
    from brain import think
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api-zzz")
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    assert think._get_auth_key() == ("sk-ant-api-zzz", False)
