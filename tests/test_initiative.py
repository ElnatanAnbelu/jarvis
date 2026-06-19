"""The soul, v1: goals reach Alfred's live context, and the initiative engine surfaces
goal-driven offers + an honesty alert. Seeded temp DB — never the real brain."""
import datetime
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory import memory, migrations
from brain import initiative, agent


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "j.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    initiative._seen.clear()
    c = sqlite3.connect(p)
    # goals/tasks are created lazily by memory.goals/life on first use — create them
    # here with the real schema so the test is self-contained.
    c.execute("CREATE TABLE IF NOT EXISTS goals (id INTEGER PRIMARY KEY AUTOINCREMENT, "
              "title TEXT, description TEXT, category TEXT, status TEXT, created_at TEXT, "
              "deadline TEXT, active INTEGER DEFAULT 1)")
    c.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, "
              "title TEXT, priority TEXT, due_date TEXT, done INTEGER DEFAULT 0, created_at TEXT)")
    c.execute("INSERT INTO goals (title,description,category,status,created_at,deadline,active) "
              "VALUES (?,?,?,?,?,?,?)",
              ("Launch Addis Market", "", "business", "active", "2026-05-11T00:00:00", None, 1))
    c.execute("INSERT INTO tasks (title,priority,due_date,done,created_at) VALUES (?,?,?,?,?)",
              ("finish landing page", "medium", None, 0, "2026-05-11T00:00:00"))
    c.commit()
    c.close()
    yield p


def test_goals_reach_the_live_system_prompt(db):
    g = agent._goals_grounding()
    assert "Launch Addis Market" in g
    sysp = agent._system_for("JARVIS", "hello there")
    assert "Launch Addis Market" in sysp   # the goal is in front of Alfred every turn


def test_scan_surfaces_goal_and_tasks(db):
    items = initiative.scan()
    keys = [i["key"] for i in items]
    assert any(k.startswith("goal:") for k in keys)
    assert "tasks:open" in keys
    blob = " ".join(i["text"] for i in items)
    assert "Launch Addis Market" in blob and "landing page" in blob


def test_caught_mistake_is_surfaced_not_hidden(db):
    c = sqlite3.connect(db)
    c.execute("INSERT INTO actions_performed (timestamp,tool_name,args,result,success,reverted) "
              "VALUES (?,?,?,?,?,?)",
              (datetime.datetime.now().isoformat(), "send_email", "{}", "smtp error", 0, 0))
    c.commit()
    c.close()
    items = initiative.scan()
    fails = [i for i in items if i["kind"] == "alert" and "send_email" in i["text"]]
    assert fails and fails[0]["visibility"] == "surface"   # honesty: surfaced, not collapsed


def test_run_once_dedupes_so_alfred_doesnt_nag(db, monkeypatch):
    from memory import rhythm
    monkeypatch.setattr(rhythm, "is_quiet_now", lambda *a, **k: False)   # active window, clock-independent
    pushed = []
    n1 = initiative.run_once(pushed.append)
    n2 = initiative.run_once(pushed.append)
    assert n1 > 0 and n2 == 0


def test_initiative_never_executes_only_surfaces(db):
    """Every item is a surfaced offer/alert — none carries an executed side effect."""
    for it in initiative.scan():
        assert it["kind"] in ("plan", "insight", "alert")
        assert "text" in it and it.get("source") == "initiative"
