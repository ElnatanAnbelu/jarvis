"""Regression: control-layer cloud features must CONSUME the (key, is_oauth)
tuple correctly (the P1 'tuple-as-api_key' finding).

These sites used `key = _get_auth_key()` (a 2-tuple) and passed it to
`api_key=`, so the `if not key` guard never fired and the first API call raised
'Header value must be str or bytes, not tuple', swallowed into an error string —
the feature silently produced an error even with a valid credential. The fix
routes all of them through brain.auth.make_client(). The producer-side
test_auth.py never exercised these consumers, which is why it slipped through.
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import brain.auth as auth


class _FakeResp:
    def __init__(self, text):
        self.content = [types.SimpleNamespace(text=text)]


class _FakeClient:
    """Stands in for anthropic.Anthropic — proves the caller never passes a
    tuple (constructing this requires nothing) and uses the client correctly."""
    def __init__(self):
        self.messages = types.SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        return _FakeResp("CANNED_OUTPUT")


def test_marketing_claude_uses_make_client(monkeypatch):
    import control.marketing as marketing
    monkeypatch.setattr(auth, "make_client", lambda *a, **k: _FakeClient())
    out = marketing._claude("write an ad")
    assert out == "CANNED_OUTPUT"
    assert "Header value" not in out and "error" not in out.lower()


def test_life_os_decision_uses_make_client(monkeypatch):
    import control.life_os as life_os
    monkeypatch.setattr(auth, "make_client", lambda *a, **k: _FakeClient())
    out = life_os.tool_decision_framework("should I expand to Kenya?")
    assert out == "CANNED_OUTPUT"
    assert "Header value" not in out and "error" not in out.lower()


def test_marketing_degrades_gracefully_without_key(monkeypatch):
    import control.marketing as marketing
    monkeypatch.setattr(auth, "make_client", lambda *a, **k: None)
    out = marketing._claude("write an ad")
    assert "no claude" in out.lower() or "unavailable" in out.lower()


def test_life_os_degrades_gracefully_without_key(monkeypatch):
    import control.life_os as life_os
    monkeypatch.setattr(auth, "make_client", lambda *a, **k: None)
    out = life_os.tool_decision_framework("q")
    assert "unavailable" in out.lower()
