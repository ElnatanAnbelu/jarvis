"""Regression: panic()/Undo must actually reverse file operations (the P2
'_inverse_for always returns (None,None)' finding). Previously every executed
action logged inverse_tool=NULL, so the Undo button and panic's revert window
silently no-op'd. These tests prove a write/create is truly undone end-to-end
through execute_tool → ledger → revert_action.
"""
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mem(tmp_path, monkeypatch):
    import memory.memory as m
    import memory.migrations as mig
    db = tmp_path / "jarvis_test.db"
    monkeypatch.setattr(m, "DB_PATH", db)
    monkeypatch.setattr(mig, "DB_PATH", db)
    m.init_db()
    return m


def _last_action_id(m):
    import sqlite3
    conn = sqlite3.connect(m.DB_PATH)
    try:
        return conn.execute("SELECT MAX(id) FROM actions_performed").fetchone()[0]
    finally:
        conn.close()


def test_write_file_overwrite_is_undone(mem):
    import brain.tools.registry as r
    # A file OUTSIDE the install tree (so the self-write firewall allows it).
    d = tempfile.mkdtemp()
    p = str(Path(d) / "note.txt")
    Path(p).write_text("ORIGINAL")

    res = r.execute_tool("write_file", {"path": p, "content": "OVERWRITTEN"}, source="user")
    assert "Refused" not in res
    assert Path(p).read_text() == "OVERWRITTEN"

    aid = _last_action_id(mem)
    msg = mem.revert_action(aid)
    assert "Reverted" in msg
    assert Path(p).read_text() == "ORIGINAL", "undo did not restore prior content"


def test_create_file_is_undone_by_delete(mem):
    import brain.tools.registry as r
    d = tempfile.mkdtemp()
    p = str(Path(d) / "fresh.txt")

    r.execute_tool("create_file", {"path": p, "content": "hello"}, source="user")
    assert Path(p).exists()

    aid = _last_action_id(mem)
    mem.revert_action(aid)
    assert not Path(p).exists(), "undo did not delete the created file"


def test_panic_revert_window_reverts_file_actions(mem):
    import brain.tools.registry as r
    d = tempfile.mkdtemp()
    p = str(Path(d) / "a.txt")
    Path(p).write_text("BEFORE")
    r.execute_tool("write_file", {"path": p, "content": "AFTER"}, source="user")

    out = mem.revert_recent(60)
    assert "reverted" in out.lower() and "no reversible" not in out.lower()
    assert Path(p).read_text() == "BEFORE"
