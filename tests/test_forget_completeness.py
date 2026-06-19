"""Regression: right-to-be-forgotten must purge a subject from ALL stores, not
just conversations/facts/ledger (the four second-audit RTBF gaps):
  - facts saved under a space-normalized key ("john_doe_phone")
  - the people registry (PII + flags) and life tables (tasks/goals/expenses)
  - the separate wiki "_Memory" vault + its FAISS index
  - observations.db (staged email sender/subject/body)

All stores are redirected to temp paths so the real vault/DBs are never touched.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def stores(tmp_path, monkeypatch):
    from memory import memory, migrations, observations, wiki
    import brain.privacy as privacy

    db = str(tmp_path / "jarvis.db")
    monkeypatch.setattr(memory, "DB_PATH", db)
    monkeypatch.setattr(migrations, "DB_PATH", db)
    memory.init_db()

    # observations.db → temp (force a reconnect to the patched path)
    monkeypatch.setattr(observations, "_DB_PATH", tmp_path / "obs.db")
    monkeypatch.setattr(observations, "_conn", None)

    # wiki _Memory vault → temp dir, pretend its index was already built
    wpath = tmp_path / "wiki"
    wpath.mkdir()
    monkeypatch.setattr(wiki, "WIKI_PATH", wpath)
    monkeypatch.setattr(wiki, "_last_build", 123.0)

    # SecondBrain vault → temp dir (never the real one)
    vpath = tmp_path / "vault"
    vpath.mkdir()
    monkeypatch.setattr(privacy, "VAULT", vpath)

    return memory, observations, wiki, privacy


def test_forget_purges_every_store(stores):
    memory, observations, wiki, privacy = stores
    from memory import people

    # ── seed every store with the subject ──
    memory.save_message("user", "remember to call Alice Johnson tomorrow")
    memory.save_fact("contact", "Alice Johnson phone", "+15551230000")  # key→alice_johnson_phone
    people.add_person("Alice Johnson", "alice@example.com", vip=True, blocked=True)

    conn = sqlite3.connect(memory.DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, title TEXT, done INTEGER)")
    conn.execute("INSERT INTO tasks (title, done) VALUES (?, 0)", ("Buy gift for Alice Johnson",))
    conn.commit()
    conn.close()

    observations.add_observation(
        "email", "from Alice Johnson <alice@example.com>",
        "Alice Johnson emailed about the project deadline coming up next week",
    )
    (wiki.WIKI_PATH / "AliceJohnson.md").write_text("Alice Johnson is a close colleague.")

    # ── forget ──
    out = privacy.forget_subject("Alice Johnson")

    # ── assert nothing about the subject survives ──
    conn = sqlite3.connect(memory.DB_PATH)
    assert conn.execute("SELECT COUNT(*) FROM conversations WHERE content LIKE '%Alice Johnson%'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM facts WHERE key LIKE '%alice_johnson%'").fetchone()[0] == 0, \
        "normalized-key fact survived the purge"
    assert conn.execute("SELECT COUNT(*) FROM people WHERE name LIKE '%Alice%'").fetchone()[0] == 0, \
        "people row survived the purge"
    assert conn.execute("SELECT COUNT(*) FROM tasks WHERE title LIKE '%Alice%'").fetchone()[0] == 0, \
        "life task survived the purge"
    conn.close()

    oc = observations._get_conn()
    assert oc.execute("SELECT COUNT(*) FROM observations WHERE content LIKE '%Alice Johnson%'").fetchone()[0] == 0, \
        "observation survived the purge"

    assert not (wiki.WIKI_PATH / "AliceJohnson.md").exists(), "wiki note not archived"
    assert wiki._last_build == 0.0, "wiki FAISS index not invalidated"
