"""P8: right-to-be-forgotten purge across jarvis.db (model-free)."""
import sqlite3

import pytest

from memory import memory, migrations


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "privacy.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    yield p


def test_forget_subject_purges_all_stores(db):
    memory.save_message("user", "Call Mallory about the deal tomorrow")
    memory.save_message("user", "Unrelated note about groceries")
    memory.log_action("send_email", {"to": "mallory@x.com"}, "sent to Mallory", success=True)
    # a fact mentioning the subject
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO facts (category, key, value, updated_at) VALUES (?,?,?,?)",
                 ("people", "Mallory", "knows Mallory from work", "now"))
    conn.commit()
    conn.close()

    out = memory.forget_subject("Mallory")
    assert "removed" in out.lower()

    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM conversations WHERE content LIKE '%Mallory%'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM facts WHERE value LIKE '%Mallory%' OR key LIKE '%Mallory%'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM actions_performed WHERE result LIKE '%Mallory%'").fetchone()[0] == 0
    # unrelated data survives
    assert conn.execute("SELECT COUNT(*) FROM conversations WHERE content LIKE '%groceries%'").fetchone()[0] == 1
    conn.close()


def test_forget_subject_refuses_broad_identifier(db):
    out = memory.forget_subject("a")
    assert "refusing" in out.lower()


def test_full_forget_archives_vault_notes(tmp_path, monkeypatch):
    # isolated db
    p = str(tmp_path / "pv.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    # isolated vault
    vault = tmp_path / "vault"
    (vault / "Relationships").mkdir(parents=True)
    note = vault / "Relationships" / "Mallory.md"
    note.write_text("Notes about Mallory and the deal", encoding="utf-8")
    keep = vault / "Relationships" / "Dana.md"
    keep.write_text("Notes about Dana", encoding="utf-8")

    from brain import privacy
    monkeypatch.setattr(privacy, "VAULT", vault)
    memory.save_message("user", "email Mallory tomorrow")

    out = privacy.forget_subject("Mallory")
    assert not note.exists()                                        # archived out
    assert (vault / "_Archive" / "Forgotten" / "Mallory.md").exists()
    assert keep.exists()                                            # unrelated untouched
    assert "archived 1" in out.lower()
    import sqlite3
    conn = sqlite3.connect(p)
    assert conn.execute("SELECT COUNT(*) FROM conversations WHERE content LIKE '%Mallory%'").fetchone()[0] == 0
    conn.close()
