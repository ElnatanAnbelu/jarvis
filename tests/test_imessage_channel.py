"""P6 — iMessage as the primary away-channel. Uses a TEMP chat.db with the minimal
schema, so the owner's real ~/Library/Messages/chat.db is never read. Pins the
owner-handle allowlist (spoofing guard), the read query, and that free-text routes
to the brain tagged source='external'."""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import imessage_channel as im


def _make_chatdb(path, rows):
    """rows: list of (rowid, handle, text, is_from_me)."""
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT)")
    conn.execute("CREATE TABLE message (ROWID INTEGER PRIMARY KEY, text TEXT, handle_id INTEGER, is_from_me INTEGER)")
    handles = {}
    for _rid, handle, _t, _f in rows:
        if handle not in handles:
            hid = len(handles) + 1
            handles[handle] = hid
            conn.execute("INSERT INTO handle (ROWID, id) VALUES (?, ?)", (hid, handle))
    for rid, handle, text, is_me in rows:
        conn.execute("INSERT INTO message (ROWID, text, handle_id, is_from_me) VALUES (?,?,?,?)",
                     (rid, text, handles[handle], is_me))
    conn.commit()
    conn.close()


def test_norm_handle():
    assert im._norm_handle("+1 (415) 555-1212") == "14155551212"
    assert im._norm_handle("Me@Example.COM") == "me@example.com"


def test_enabled_follows_env(monkeypatch):
    monkeypatch.delenv("ALFRED_IMESSAGE_OWNER", raising=False)
    assert im.enabled() is False
    monkeypatch.setenv("ALFRED_IMESSAGE_OWNER", "+14155551212")
    assert im.enabled() is True
    assert "14155551212" in im.owner_handles()


def test_fetch_new_only_owner_and_incoming(tmp_path):
    db = tmp_path / "chat.db"
    _make_chatdb(db, [
        (1, "+14155551212", "approve 5", 0),       # owner, incoming  ✓
        (2, "+14155551212", "this is from me", 1),  # owner, OUTGOING  ✗ (is_from_me)
        (3, "+19998887777", "approve 9", 0),        # stranger          ✗
        (4, "+1-415-555-1212", "pause", 0),         # owner (diff fmt)  ✓
    ])
    owners = {"14155551212"}
    got = im._fetch_new(str(db), owners, since_rowid=0)
    assert [(r, t) for r, _h, t in got] == [(1, "approve 5"), (4, "pause")]


def test_fetch_new_respects_since_rowid(tmp_path):
    db = tmp_path / "chat.db"
    _make_chatdb(db, [(1, "a@b.com", "pause", 0), (2, "a@b.com", "resume", 0)])
    got = im._fetch_new(str(db), {"a@b.com"}, since_rowid=1)
    assert [t for _r, _h, t in got] == ["resume"]


def test_handle_text_command_vs_freetext(monkeypatch):
    # control command → goes through the shared owner-command handler
    import telegram_bot
    monkeypatch.setattr(telegram_bot, "_handle_owner_command", lambda cmd, arg: f"CMD:{cmd}:{arg}")
    assert im.handle_text("a@b.com", "pause") == "CMD:pause:None"

    # free text → routes to the brain tagged source='external'
    calls = {}
    import brain.router
    monkeypatch.setattr(brain.router, "route", lambda text, source=None: calls.update(text=text, source=source) or ("ok, sir", "m"))
    out = im.handle_text("a@b.com", "what's on my plate today")
    assert out == "ok, sir"
    assert calls == {"text": "what's on my plate today", "source": "external"}


def test_poll_once_disabled_is_noop(monkeypatch):
    monkeypatch.delenv("ALFRED_IMESSAGE_OWNER", raising=False)
    assert im.poll_once(db_path="/nonexistent") == 0


def test_poll_once_handles_and_advances(tmp_path, monkeypatch):
    db = tmp_path / "chat.db"
    _make_chatdb(db, [(7, "+14155551212", "status", 0)])
    monkeypatch.setenv("ALFRED_IMESSAGE_OWNER", "+14155551212")
    # dict-backed memory flags
    store = {}
    from memory import memory
    monkeypatch.setattr(memory, "get_flag", lambda k, d=None: store.get(k, d))
    monkeypatch.setattr(memory, "set_flag", lambda k, v: store.__setitem__(k, v))
    monkeypatch.setattr(im, "handle_text", lambda h, t: f"reply to {t}")
    sent = []
    monkeypatch.setattr(im, "send", lambda text, to: sent.append((to, text)))

    handled = im.poll_once(db_path=str(db))
    assert handled == 1
    assert sent == [("+14155551212", "reply to status")]
    assert store[im._ROWID_FLAG] == 7
    # second poll: nothing new
    assert im.poll_once(db_path=str(db)) == 0
