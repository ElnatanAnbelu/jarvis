"""
Tests for the Block A safety-substrate data layer:
  - migration framework (idempotent, ordered, transactional, additive)
  - extended action ledger (agent/risk/inverse fields, revert_action)
  - get_flag / set_flag over the meta table
  - pending_confirmations lifecycle

Every test points memory.memory.DB_PATH at a per-test temp file (matching the
DB isolation pattern used by the existing suite) so the real jarvis.db is never
touched.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mem(tmp_path, monkeypatch):
    """Fresh, migrated, fully isolated memory module bound to a temp DB."""
    import memory.memory as m
    import memory.migrations as mig

    db = tmp_path / "jarvis_test.db"
    monkeypatch.setattr(m, "DB_PATH", db)
    # migrations.run_migrations defaults its arg to the (now stale) import-time
    # DB_PATH, so callers must pass db_path explicitly; patch the default too
    # for any code that calls run_migrations() with no arg.
    monkeypatch.setattr(mig, "DB_PATH", db)
    m.init_db()  # creates base tables + runs migrations against the temp DB
    return m


def _user_version(db_path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


def _columns(db_path, table) -> set:
    conn = sqlite3.connect(db_path)
    try:
        return {row[1] for row in conn.execute("PRAGMA table_info(%s)" % table).fetchall()}
    finally:
        conn.close()


# ── Migrations ───────────────────────────────────────────────────────────────

def test_migrations_idempotent_and_versioned(mem, tmp_path):
    import memory.migrations as mig
    db = mem.DB_PATH

    # init_db already ran migrations once; user_version should be at the top.
    top = max(v for v, _ in mig.MIGRATIONS)
    assert _user_version(db) == top

    # Running again applies nothing and leaves the version unchanged.
    returned = mig.run_migrations(db)
    assert returned == top
    assert _user_version(db) == top

    # Schema is correct after migration 1.
    action_cols = _columns(db, "actions_performed")
    for col in ("agent", "risk", "inverse_tool", "inverse_args", "reverted", "reverted_at"):
        assert col in action_cols
    # Legacy columns preserved.
    for col in ("timestamp", "tool_name", "args", "result", "success"):
        assert col in action_cols

    conf_cols = _columns(db, "pending_confirmations")
    for col in ("id", "created_at", "tool_name", "args", "agent", "risk",
                "reason", "status", "result", "resolved_at"):
        assert col in conf_cols


def test_migrations_preserve_existing_rows(tmp_path, monkeypatch):
    """A legacy DB with the old actions_performed schema and existing rows must
    be migrated additively without losing data."""
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE actions_performed (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, tool_name TEXT, args TEXT, result TEXT,
            success INTEGER DEFAULT 1
        )
    """)
    conn.execute(
        "INSERT INTO actions_performed (timestamp, tool_name, args, result, success) "
        "VALUES ('t', 'old_tool', '{}', 'old_result', 1)"
    )
    conn.commit()
    conn.close()

    import memory.migrations as mig
    monkeypatch.setattr(mig, "DB_PATH", db)
    mig.run_migrations(db)

    conn = sqlite3.connect(db)
    try:
        row = conn.execute(
            "SELECT tool_name, result, reverted FROM actions_performed WHERE tool_name='old_tool'"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "old_tool"
    assert row[1] == "old_result"
    assert row[2] == 0  # new column defaulted


# ── log_action / round-trip ─────────────────────────────────────────────────

def test_log_action_returns_id_and_round_trips_fields(mem):
    rid = mem.log_action(
        "send_email", {"to": "a@b.com"}, "sent", success=True,
        agent="JARVIS", risk="medium",
        inverse_tool="delete_email", inverse_args={"id": 7},
    )
    assert isinstance(rid, int) and rid > 0

    conn = sqlite3.connect(mem.DB_PATH)
    try:
        row = conn.execute(
            "SELECT agent, risk, inverse_tool, inverse_args, reverted "
            "FROM actions_performed WHERE id=?", (rid,)
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "JARVIS"
    assert row[1] == "medium"
    assert row[2] == "delete_email"
    assert row[3] == '{"id": 7}'  # dict serialized to JSON string
    assert row[4] == 0


def test_log_action_backward_compatible_positional(mem):
    """Existing callers pass 4 positional args + success kwarg only."""
    rid = mem.log_action("some_tool", {"x": 1}, "ok", success=False)
    assert isinstance(rid, int) and rid > 0
    conn = sqlite3.connect(mem.DB_PATH)
    try:
        row = conn.execute(
            "SELECT success, agent, inverse_tool FROM actions_performed WHERE id=?", (rid,)
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == 0
    assert row[1] is None
    assert row[2] is None


# ── revert_action ────────────────────────────────────────────────────────────

def test_revert_action_executes_inverse_and_flips_flag(mem, monkeypatch):
    import brain.tools.registry as reg

    calls = {}

    @reg.tool(
        description="dummy inverse tool",
        parameters={"id": {"type": "integer", "description": "id"}},
    )
    def _safety_test_undo(id: int) -> str:  # noqa: A002 - matches inverse_args key
        calls["id"] = id
        return f"undid {id}"

    rid = mem.log_action(
        "create_thing", {"name": "x"}, "created", success=True,
        agent="JARVIS", risk="high",
        inverse_tool="_safety_test_undo", inverse_args={"id": 42},
    )

    msg = mem.revert_action(rid)
    assert calls.get("id") == 42
    assert "_safety_test_undo" in msg

    conn = sqlite3.connect(mem.DB_PATH)
    try:
        reverted, reverted_at = conn.execute(
            "SELECT reverted, reverted_at FROM actions_performed WHERE id=?", (rid,)
        ).fetchone()
    finally:
        conn.close()
    assert reverted == 1
    assert reverted_at is not None

    # Second revert is a no-op with a clear message.
    msg2 = mem.revert_action(rid)
    assert "already reverted" in msg2.lower()


def test_revert_action_no_inverse_does_nothing(mem):
    rid = mem.log_action("noop_tool", {}, "done", success=True)
    msg = mem.revert_action(rid)
    assert "no inverse" in msg.lower()
    conn = sqlite3.connect(mem.DB_PATH)
    try:
        reverted = conn.execute(
            "SELECT reverted FROM actions_performed WHERE id=?", (rid,)
        ).fetchone()[0]
    finally:
        conn.close()
    assert reverted == 0


def test_revert_action_missing_id(mem):
    assert "no action found" in mem.revert_action(999999).lower()


# ── get_flag / set_flag ───────────────────────────────────────────────────────

def test_flags_round_trip_bools_and_strings(mem):
    # Unset bool returns the bool default.
    assert mem.get_flag("away_mode", default=False) is False

    mem.set_flag("away_mode", True)
    assert mem.get_flag("away_mode", default=False) is True
    assert mem.get_flag("away_mode", default=False) is True  # stable

    mem.set_flag("paused", False)
    assert mem.get_flag("paused", default=True) is False

    # String round-trip.
    mem.set_flag("mode_label", "vacation")
    assert mem.get_flag("mode_label", default="") == "vacation"

    # Unset string default.
    assert mem.get_flag("never_set", default="fallback") == "fallback"
    # Unset with no default → None.
    assert mem.get_flag("also_never_set") is None


# ── pending_confirmations lifecycle ──────────────────────────────────────────

def test_confirmation_lifecycle(mem):
    cid = mem.enqueue_confirmation(
        "wire_transfer", {"amount": 5000}, agent="JARVIS",
        risk="critical", reason="large outbound transfer",
    )
    assert isinstance(cid, int) and cid > 0

    pending = mem.get_pending_confirmations()
    assert len(pending) == 1
    p = pending[0]
    assert p["id"] == cid
    assert p["tool_name"] == "wire_transfer"
    assert p["args"] == {"amount": 5000}
    assert p["agent"] == "JARVIS"
    assert p["risk"] == "critical"
    assert p["reason"] == "large outbound transfer"
    assert p["status"] == "pending"
    assert p["resolved_at"] is None

    single = mem.get_confirmation(cid)
    assert single is not None and single["id"] == cid

    mem.set_confirmation_status(cid, "approved", result="user tapped approve")
    after = mem.get_confirmation(cid)
    assert after["status"] == "approved"
    assert after["result"] == "user tapped approve"
    assert after["resolved_at"] is not None  # terminal → stamped

    # No longer pending.
    assert mem.get_pending_confirmations() == []


def test_get_confirmation_missing_returns_none(mem):
    assert mem.get_confirmation(424242) is None


def test_set_confirmation_status_non_terminal_no_resolved_at(mem):
    cid = mem.enqueue_confirmation("x", {}, agent="JARVIS", risk="low")
    mem.set_confirmation_status(cid, "in_progress")
    row = mem.get_confirmation(cid)
    assert row["status"] == "in_progress"
    assert row["resolved_at"] is None
