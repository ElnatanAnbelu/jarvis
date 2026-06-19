"""Morning prep (plan §1.2): a warm 'here's your day, sir' built from open goals + tasks,
fired once at the learned wake hour."""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory import memory, migrations, rhythm
from brain import morning, initiative


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "m.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    initiative._seen.clear()
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE IF NOT EXISTS goals (id INTEGER PRIMARY KEY AUTOINCREMENT, "
              "title TEXT, description TEXT, category TEXT, status TEXT, created_at TEXT, "
              "deadline TEXT, active INTEGER DEFAULT 1)")
    c.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, "
              "title TEXT, priority TEXT, due_date TEXT, done INTEGER DEFAULT 0, created_at TEXT)")
    c.execute("INSERT INTO goals (title,status) VALUES ('Launch Addis Market','active')")
    c.execute("INSERT INTO tasks (title,done) VALUES ('finish landing page',0)")
    c.commit()
    c.close()
    yield p


def test_morning_card_opens_warmly_with_goals_and_tasks(db):
    card = morning.build_morning_prep()
    assert card is not None
    assert "Good morning, sir" in card["text"]
    assert "Launch Addis Market" in card["text"]
    assert "landing page" in card["text"]
    assert card["kind"] == "morning" and card["visibility"] == "surface"


def test_morning_card_is_none_when_nothing_to_say(tmp_path, monkeypatch):
    p = str(tmp_path / "empty.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    assert morning.build_morning_prep() is None


def test_trigger_fires_at_wake_hour(db, monkeypatch):
    monkeypatch.setattr(rhythm, "quiet_window", lambda: (0, datetime.now().hour))   # wake == now
    items = initiative._trigger_morning()
    assert items and items[0]["kind"] == "morning"


def test_trigger_silent_off_hour(db, monkeypatch):
    off = (datetime.now().hour + 3) % 24
    monkeypatch.setattr(rhythm, "quiet_window", lambda: (0, off))   # wake != now
    assert initiative._trigger_morning() == []
