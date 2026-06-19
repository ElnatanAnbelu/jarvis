"""Learned quiet-hours (plan §7): routine proactivity is held while sir sleeps, but
urgent items always break through — never fully silent. Plus the initiative damping."""
import datetime as dt
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory import memory, migrations, rhythm
from brain import initiative


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "r.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    initiative._seen.clear()
    yield p


def _at(hour):
    return dt.datetime(2026, 6, 20, hour, 0, 0)


def test_is_quiet_now_respects_window(db):
    rhythm._flag_set("quiet_window", "23,7")
    assert rhythm.is_quiet_now(_at(2)) is True     # 2am — quiet
    assert rhythm.is_quiet_now(_at(14)) is False    # 2pm — active


def test_should_surface_holds_routine_but_passes_urgent(db):
    rhythm._flag_set("quiet_window", "23,7")
    routine = {"kind": "plan", "visibility": "normal", "key": "g1"}
    alert = {"kind": "alert", "visibility": "surface", "key": "a1"}
    assert rhythm.should_surface(routine, _at(2)) is False   # held at night
    assert rhythm.should_surface(alert, _at(2)) is True      # urgent breaks through
    assert rhythm.should_surface(routine, _at(14)) is True   # active → passes


def test_learn_rhythm_finds_the_low_activity_window(db):
    c = sqlite3.connect(db)
    for h in list(range(9, 18)) * 10:   # heavy activity 9–17, none overnight
        c.execute("INSERT INTO actions_performed (timestamp,tool_name,args,result,success) "
                  "VALUES (?,?,?,?,?)", (dt.datetime(2026, 6, 20, h).isoformat(), "x", "{}", "ok", 1))
    c.commit()
    c.close()
    win = rhythm.learn_rhythm()
    assert win == (0, 8)   # the empty overnight stretch is taken as quiet


def test_initiative_holds_routine_in_quiet_passes_alerts(db):
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE IF NOT EXISTS goals (id INTEGER PRIMARY KEY AUTOINCREMENT, "
              "title TEXT, description TEXT, category TEXT, status TEXT, created_at TEXT, "
              "deadline TEXT, active INTEGER DEFAULT 1)")
    c.execute("INSERT INTO goals (title,status,created_at) VALUES ('Launch Addis Market','active','2026-05-11')")
    c.execute("INSERT INTO actions_performed (timestamp,tool_name,args,result,success,reverted) "
              "VALUES (?,?,?,?,?,?)", (dt.datetime.now().isoformat(), "send_email", "{}", "fail", 0, 0))
    c.commit()
    c.close()
    rhythm._flag_set("quiet_window", "0,24")   # force "always quiet" for the assertion
    pushed = []
    initiative.run_once(pushed.append)
    kinds = [p["kind"] for p in pushed]
    assert "alert" in kinds        # the failure breaks through the quiet window
    assert "plan" not in kinds     # the routine goal offer is held for the active window
