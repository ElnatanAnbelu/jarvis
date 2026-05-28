"""
Observation staging layer for the Personal Second Brain.

Raw life signals (email, calendar, conversation, manual) are buffered
here in SQLite before synthesis. Only quality-scored observations reach
the vault write layer.
"""
import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).parent / "observations.db"
_conn: Optional[sqlite3.Connection] = None
_lock = threading.Lock()

_SIGNAL_WORDS = {
    "decided", "starting", "reading", "working", "building", "learned",
    "realized", "want", "goal", "plan", "going", "feels", "noticed",
    "met", "talked", "interested", "thinking", "worried", "excited",
    "finished", "launched", "shipped", "hired", "quit", "moved",
    "started", "stopped", "changed", "discovered", "feeling", "chose",
    "productive", "focused", "called", "discussed", "shared", "planning",
}

_PERSONAL_ANCHORS = {"i ", "i'", "my ", "me ", "we ", "our ", "you ", "your ",
                     "elnatan", "jarvis"}

_LOW_CREDIBILITY_SOURCES = {"system", "unknown", "test"}


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _create_schema(_conn)
    return _conn


def _create_schema(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            source         TEXT NOT NULL,
            source_detail  TEXT,
            content        TEXT NOT NULL,
            relevance_hint TEXT,
            tags           TEXT,
            sensitivity    TEXT DEFAULT 'low',
            quality        INTEGER DEFAULT 0,
            content_hash   TEXT,
            captured_at    TEXT NOT NULL,
            synthesized    INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS suppressed_topics (
            topic      TEXT PRIMARY KEY,
            added_at   TEXT NOT NULL
        )
    """)
    conn.commit()


def score_observation_quality(obs: dict) -> bool:
    """Apply 4-criterion quality filter. Returns True if observation is worth staging."""
    content = obs.get("content", "").strip()
    source  = obs.get("source", "")

    # 1. Length floor — at least 7 words
    if len(content.split()) < 7:
        return False

    # 2. Information density — at least one signal word
    words = set(content.lower().split())
    if not words.intersection(_SIGNAL_WORDS):
        return False

    # 3. Personal relevance — contains a personal anchor
    lower = content.lower()
    if not any(anchor in lower for anchor in _PERSONAL_ANCHORS):
        return False

    # 4. Source credibility
    if source.lower() in _LOW_CREDIBILITY_SOURCES:
        return False

    return True


def add_observation(source: str, source_detail: str, content: str,
                    relevance_hint: str = "", tags: str = "",
                    sensitivity: str = "low") -> int:
    """Stage an observation. Applies quality filter and deduplication. Returns row id."""
    quality = 1 if score_observation_quality({"content": content, "source": source}) else 0
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    now = datetime.now(timezone.utc).isoformat()

    with _lock:
        conn = _get_conn()

        # Deduplication: skip identical observations captured in last 24h
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        existing = conn.execute(
            "SELECT id FROM observations WHERE content_hash = ? AND captured_at > ?",
            (content_hash, cutoff)
        ).fetchone()
        if existing:
            return existing["id"]

        # Check suppressed topics — mark quality=0 if suppressed
        if quality == 1 and relevance_hint:
            suppressed = conn.execute(
                "SELECT topic FROM suppressed_topics WHERE INSTR(?, topic) > 0",
                (relevance_hint,)
            ).fetchone()
            if suppressed:
                quality = 0

        cursor = conn.execute(
            """INSERT INTO observations
               (source, source_detail, content, relevance_hint, tags,
                sensitivity, quality, content_hash, captured_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (source, source_detail, content, relevance_hint, tags,
             sensitivity, quality, content_hash, now)
        )
        conn.commit()
        return cursor.lastrowid


def get_pending_observations(limit: int = 20,
                             include_high_sensitivity: bool = False) -> list:
    """Return pending (unsynthesized) quality observations."""
    with _lock:
        conn = _get_conn()
        if include_high_sensitivity:
            rows = conn.execute(
                "SELECT * FROM observations WHERE synthesized = 0 AND quality = 1 "
                "ORDER BY captured_at DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM observations WHERE synthesized = 0 AND quality = 1 "
                "AND sensitivity != 'high' ORDER BY captured_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def mark_synthesized(observation_id: int):
    """Mark an observation as synthesized (remove from pending)."""
    with _lock:
        conn = _get_conn()
        conn.execute("UPDATE observations SET synthesized = 1 WHERE id = ?",
                     (observation_id,))
        conn.commit()


def get_recent_observations(hours: int = 24) -> list:
    """Return all observations (any quality) from the past N hours."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with _lock:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM observations WHERE captured_at > ? ORDER BY captured_at DESC",
            (cutoff,)
        ).fetchall()
        return [dict(r) for r in rows]


def suppress_topic(topic: str):
    """Suppress a topic — mark matching pending observations as quality=0."""
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO suppressed_topics (topic, added_at) VALUES (?, ?)",
            (topic, now)
        )
        conn.commit()
        # Retroactively mark matching pending observations as low quality
        conn.execute(
            "UPDATE observations SET quality = 0 WHERE synthesized = 0 "
            "AND INSTR(relevance_hint, ?) > 0", (topic,)
        )
        conn.commit()


def get_suppressed_topics() -> list:
    with _lock:
        conn = _get_conn()
        rows = conn.execute("SELECT topic FROM suppressed_topics").fetchall()
        return [r["topic"] for r in rows]
