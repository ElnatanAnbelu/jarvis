"""P2(b/c) — synthesized insights persist to the vault (deduped) and old synthesized
observations are archived out of the staging store via TTL. Temp vault + temp obs db only."""
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory import memory, migrations
from brain import synthesis


def _make_obs_db(path, rows):
    """rows: list of (content, hint, synthesized, captured_at)."""
    c = sqlite3.connect(str(path))
    c.execute(
        "CREATE TABLE observations (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, "
        "source_detail TEXT, content TEXT, relevance_hint TEXT, tags TEXT, sensitivity TEXT, "
        "quality TEXT, content_hash TEXT, captured_at TEXT, synthesized INTEGER DEFAULT 0)"
    )
    for content, hint, synth, cap in rows:
        c.execute(
            "INSERT INTO observations (content,relevance_hint,synthesized,captured_at) "
            "VALUES (?,?,?,?)", (content, hint, synth, cap),
        )
    c.commit()
    c.close()


@pytest.fixture
def env(tmp_path, monkeypatch):
    p = str(tmp_path / "j.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    # Point the vault at a throwaway dir — never the owner's real Desktop vault.
    monkeypatch.setenv("SECONDBRAIN_PATH", str(tmp_path / "SecondBrain"))
    # vault.DEFAULT_VAULT_PATH is computed at import — patch it so a fresh
    # VaultManager() picks up the temp path.
    from memory import vault as vmod
    monkeypatch.setattr(vmod, "DEFAULT_VAULT_PATH", tmp_path / "SecondBrain")
    yield tmp_path


def test_synthesize_persists_insight_to_vault(env):
    now = datetime.now(timezone.utc).isoformat()
    _make_obs_db(env / "observations.db", [
        ("works late often on the startup", "Habits", 0, now),
        ("ships features in focused bursts", "Habits", 0, now),
    ])
    item = synthesis.synthesize_one()
    assert item is not None and item["kind"] == "insight"
    # Habits → Personal/medium → routed through the proposal flow. The insight
    # must now exist as a pending proposal in the vault (grew on disk).
    from memory.vault import VaultManager
    vm = VaultManager(vault_path=env / "SecondBrain")
    pending = vm.get_pending_proposals().lower()
    assert "habits" in pending or "personal model" in pending


def test_synthesize_persist_is_deduped(env):
    """The same insight, re-synthesized, must NOT spawn additional proposals — the
    pending count is stable (anti-bloat: the '×6' must be impossible)."""
    from memory.vault import VaultManager

    def pending_with_insight():
        proposals_dir = env / "SecondBrain" / "_JARVIS" / "Proposals"
        norm = VaultManager._normalize_fact(
            "Pattern noticed: works late often on the startup")
        return [p for p in proposals_dir.rglob("*.md")
                if "status: pending" in p.read_text()
                and norm in VaultManager._normalize_fact(p.read_text())]

    now = datetime.now(timezone.utc).isoformat()
    db = env / "observations.db"
    _make_obs_db(db, [("works late often on the startup", "Habits", 0, now)])
    synthesis.synthesize_one()
    first = len(pending_with_insight())
    assert first >= 1  # persisted at least once (topical note + personal model)

    # Stage the SAME content again and synthesize once more.
    c = sqlite3.connect(str(db))
    c.execute("INSERT INTO observations (content,relevance_hint,synthesized,captured_at) "
              "VALUES (?,?,0,?)", ("works late often on the startup", "Habits", now))
    c.commit()
    c.close()
    synthesis.synthesize_one()
    # No growth — the dedupe held.
    assert len(pending_with_insight()) == first, "insight bloated on re-synthesis"


def test_archive_synthesized_moves_old_rows(env):
    old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    fresh = datetime.now(timezone.utc).isoformat()
    db = env / "observations.db"
    _make_obs_db(db, [
        ("old synthesized signal", "Habits", 1, old),      # archive
        ("recent synthesized signal", "Habits", 1, fresh), # keep (too fresh)
        ("old but unsynthesized signal", "Habits", 0, old), # keep (not synthesized)
    ])
    n = synthesis.archive_synthesized(ttl_days=30)
    assert n == 1
    c = sqlite3.connect(str(db))
    live = c.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    archived = c.execute("SELECT COUNT(*) FROM observations_archive").fetchone()[0]
    c.close()
    assert live == 2 and archived == 1


def test_archive_is_idempotent_and_nondestructive(env):
    old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    db = env / "observations.db"
    _make_obs_db(db, [("old synthesized signal", "Habits", 1, old)])
    assert synthesis.archive_synthesized(ttl_days=30) == 1
    assert synthesis.archive_synthesized(ttl_days=30) == 0  # nothing left to move
    c = sqlite3.connect(str(db))
    archived = c.execute("SELECT content FROM observations_archive").fetchall()
    c.close()
    assert archived == [("old synthesized signal",)]  # preserved, not destroyed
