"""Regression tests for the P0 'safety gate silently bypassed' hole.

Two independent defects combined to disarm the gate in the live checkout:
  1. memory/life.py and memory/people.py both declared `people` with DIFFERENT
     columns; the legacy one won, so people.match() raised OperationalError.
  2. brain/tools/registry.execute_tool swallowed any gate() exception and FAILED
     OPEN — running the tool ungated.

Net effect: every send-with-a-recipient (send_email/iMessage/WhatsApp, money
tools) executed with NO red-list / away-mode / pause / blocklist check.

These tests pin the fix: the schema migration reconciles `people`, and the gate
fails CLOSED on any internal error.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def legacy_people_db(tmp_path, monkeypatch):
    """A temp DB seeded with life.py's LEGACY `people` schema (no safety
    columns), exactly like the live jarvis.db that triggered the bug."""
    import memory.memory as m
    import memory.migrations as mig

    db = tmp_path / "jarvis_test.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """CREATE TABLE people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE, relationship TEXT,
            notes TEXT, last_contact TEXT, birthday TEXT
        )"""
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(m, "DB_PATH", db)
    monkeypatch.setattr(mig, "DB_PATH", db)
    return m, db


def test_migration_reconciles_legacy_people_schema(legacy_people_db):
    """The legacy table gains the safety columns instead of staying broken."""
    import memory.people as people
    m, db = legacy_people_db

    m.init_db()  # runs migrations against the legacy table

    cols = {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(people)").fetchall()}
    for required in ("identifier", "vip", "family", "blocked"):
        assert required in cols, f"migration left `people` missing {required}"
    # legacy columns are preserved, not dropped
    for legacy in ("relationship", "notes", "birthday"):
        assert legacy in cols


def test_people_match_does_not_raise_after_migration(legacy_people_db):
    """The exact call that used to raise OperationalError now works, so it can
    never again blow up inside gate()."""
    import memory.people as people
    m, db = legacy_people_db
    m.init_db()

    people.add_person("Mom", "mom@example.com", family=True)
    assert people.match("mom@example.com")["family"] is True
    assert people.match("stranger@example.com") == {"vip": False, "family": False, "blocked": False}


def test_list_people_self_heals_on_stale_schema(legacy_people_db, monkeypatch):
    """Even if migrations somehow hadn't run, list_people() must NOT swallow a
    schema error into an all-False result — it self-heals (migrate+retry) and,
    failing that, raises so the gate fails closed."""
    import memory.people as people
    m, db = legacy_people_db
    # Do NOT call init_db() — table is still the legacy schema here.
    rows = people.list_people()  # should migrate-and-retry, not crash, not lie
    assert rows == []  # empty but correctly-shaped, columns now exist


def test_gate_fails_closed_when_gate_raises(monkeypatch):
    """If autonomy.gate() raises for ANY reason, the tool must be DENIED, never
    executed. A safety gate that fails open is no gate."""
    import brain.tools.registry as r
    import brain.autonomy as autonomy

    ran = {"v": False}

    @r.tool(description="probe", parameters={"to": {"type": "string"}}, risk="red")
    def _failsafe_probe(to=""):
        ran["v"] = True
        return "PROBE_RAN"

    monkeypatch.setattr(
        autonomy, "gate",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    out = r.execute_tool("_failsafe_probe", {"to": "x@y.com"}, source="user")

    assert ran["v"] is False, "tool executed despite gate failure — FAILED OPEN"
    assert "blocked" in out.lower() or "🚫" in out
