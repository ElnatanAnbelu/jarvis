"""Knows-me synthesis (plan §6): staged observations become a knowing aside, strongest
theme first, and are marked processed so the backlog drains."""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory import memory, migrations
from brain import synthesis


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "j.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    obs = str(tmp_path / "observations.db")
    c = sqlite3.connect(obs)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, "
              "source_detail TEXT, content TEXT, relevance_hint TEXT, tags TEXT, sensitivity TEXT, "
              "quality TEXT, content_hash TEXT, captured_at TEXT, synthesized INTEGER DEFAULT 0)")
    for content, hint in [("works late often", "Habits"),
                          ("ships in bursts", "Habits"),
                          ("close to mom", "Family")]:
        c.execute("INSERT INTO observations (content,relevance_hint,synthesized) VALUES (?,?,0)",
                  (content, hint))
    c.commit()
    c.close()
    yield p


def test_synthesize_surfaces_strongest_theme_and_marks_done(db, tmp_path):
    item = synthesis.synthesize_one()
    assert item and item["kind"] == "insight"
    assert "Habits" in item["title"]                       # the largest group (2 obs)
    assert "works late" in item["text"] or "bursts" in item["text"]
    c = sqlite3.connect(str(tmp_path / "observations.db"))
    left = c.execute("SELECT COUNT(*) FROM observations WHERE synthesized=0 AND relevance_hint='Habits'").fetchone()[0]
    c.close()
    assert left == 0                                       # those observations are now processed


def test_synthesize_drains_then_returns_none(db):
    assert synthesis.synthesize_one() is not None          # Habits
    assert synthesis.synthesize_one() is not None          # Family
    assert synthesis.synthesize_one() is None              # nothing left to learn
