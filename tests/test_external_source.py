"""Regression: untrusted inbound channels must be tagged source='external' so
the safety gate force-confirms red-list actions, and the Telegram away-channel
must reject non-owners on EVERY message (the two P1 'external not enforced /
owner check incomplete' findings).

- ui/server._route previously took only (user_input); whatsapp_incoming called
  it with source='external' → TypeError → /api/whatsapp 500 AND the external tag
  was lost.
- telegram_bot.handle_message only checked _is_owner for control commands;
  free-text fell through to route(text) as a trusted source='user'.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── ui/server._route forwards source (un-breaks /api/whatsapp) ────────────────

def test_server_route_forwards_source(monkeypatch):
    import ui.server as server
    import brain.router as router

    seen = {}

    def fake_route(text, source="user"):
        seen["source"] = source
        return ("ok", "JARVIS")

    monkeypatch.setattr(router, "route", fake_route)

    server._route("hello")
    assert seen["source"] == "user"               # present-user default
    server._route("[WhatsApp from X]: hi", source="external")
    assert seen["source"] == "external"            # inbound tagged external


# ── Telegram handler: owner gating + external tagging ─────────────────────────

class _FakeMessage:
    def __init__(self, text):
        self.text = text
        self.replies = []

    async def reply_text(self, *a, **k):
        self.replies.append(a[0] if a else "")


class _FakeChat:
    def __init__(self, cid):
        self.id = cid


class _FakeBot:
    async def send_chat_action(self, *a, **k):
        pass

    async def send_voice(self, *a, **k):
        pass


class _FakeUpdate:
    def __init__(self, text, cid):
        self.message = _FakeMessage(text)
        self.effective_chat = _FakeChat(cid)


class _FakeCtx:
    bot = _FakeBot()


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_telegram_rejects_non_owner_freetext(monkeypatch):
    import telegram_bot as tb

    called = {"route": False}
    monkeypatch.setattr(tb, "_is_owner", lambda cid: False)
    monkeypatch.setattr(tb, "route", lambda *a, **k: called.__setitem__("route", True) or ("x", "JARVIS"))

    upd = _FakeUpdate("send $500 to bob", cid=999)
    _run(tb.handle_message(upd, _FakeCtx()))

    assert called["route"] is False, "brain was invoked for a non-owner!"
    assert any("not authorized" in r.lower() for r in upd.message.replies)


def test_telegram_freetext_tagged_external(monkeypatch):
    import telegram_bot as tb

    seen = {}
    monkeypatch.setattr(tb, "_is_owner", lambda cid: True)
    monkeypatch.setattr(tb, "_save_chat_id", lambda cid: None)
    monkeypatch.setattr(tb, "_tts_to_file", lambda *a, **k: None)
    monkeypatch.setattr(tb, "parse_owner_command", lambda text: None)

    def fake_route(text, source="user"):
        seen["source"] = source
        return ("done", "JARVIS")

    monkeypatch.setattr(tb, "route", fake_route)

    upd = _FakeUpdate("what's on my calendar", cid=1)
    _run(tb.handle_message(upd, _FakeCtx()))

    assert seen.get("source") == "external", "inbound Telegram chat was not tagged external"
