"""brain/synthesis.py — the 'knows me' loop (plan §6).

Staged observations (memory/observations.py) become a *knowing aside* — "I've noticed a
pattern about your …, sir." One theme per pass (low-frequency, companion-toned, never
noisy); the observations behind it are marked synthesized so the backlog drains over time
instead of re-surfacing.
"""
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone

# Synthesized observations older than this are archived out of the active
# staging store so it stays clean (the backlog drains over time instead of
# accumulating forever). They are MOVED to an `observations_archive` table in
# the same db — never destroyed — so nothing real is lost.
_SYNTH_ARCHIVE_TTL_DAYS = 30


def _obs_path():
    from memory import memory as _m
    return os.path.join(os.path.dirname(_m.DB_PATH), "observations.db")


def _vault():
    """Lazily build a VaultManager (honors SECONDBRAIN_PATH). Returns None on failure."""
    try:
        from memory.vault import VaultManager
        return VaultManager()
    except Exception:
        return None


def _persist_insight(hint: str, contents: list):
    """Persist a freshly synthesized insight to the Second Brain vault, deduped.

    Writes a one-line summary to the topical note (routed + risk-tiered via
    vault.register_fact) AND proposes the same insight as a Personal Model
    update so the long-term self-model grows. Never raises."""
    vm = _vault()
    if vm is None:
        return
    summary = " ".join(c for c in contents if c).strip()
    if not summary:
        return
    topic = (hint or "you").strip() or "you"
    insight_line = f"Pattern noticed: {summary}"
    try:
        # Topical note (e.g. Habits, Family) — register_fact dedupes hard and
        # routes high-risk topics through the proposal flow.
        vm.register_fact(topic, insight_line, source="synthesis")
    except Exception:
        pass
    try:
        # Personal Model — only propose if this exact insight isn't already
        # present/pending for the model, so synthesis can't bloat it.
        if not vm.fact_exists("_JARVIS", "_PersonalModel", insight_line):
            section = topic if topic.lower() != "you" else "General"
            vm.update_personal_model(
                section=section,
                content=insight_line,
                source="synthesis",
                supporting_observations=summary[:200],
            )
    except Exception:
        pass


def archive_synthesized(ttl_days: int = _SYNTH_ARCHIVE_TTL_DAYS) -> int:
    """TTL housekeeping: move synthesized observations older than `ttl_days` out
    of the active `observations` table into `observations_archive` so the staging
    store stays small. Non-destructive (rows are copied, not dropped). Returns the
    number of rows archived. Safe to call repeatedly; no-op if nothing is stale."""
    p = _obs_path()
    if not os.path.exists(p):
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=ttl_days)).isoformat()
    c = sqlite3.connect(p)
    try:
        # Discover the live schema so the archive table mirrors it exactly.
        cols = [r[1] for r in c.execute("PRAGMA table_info(observations)").fetchall()]
        if not cols:
            return 0
        col_list = ", ".join(cols)
        c.execute(
            f"CREATE TABLE IF NOT EXISTS observations_archive AS "
            f"SELECT {col_list} FROM observations WHERE 0"
        )
        # Only rows that are both synthesized AND old enough. captured_at may be
        # NULL on hand-rolled rows — guard against that so we never archive fresh
        # work just because it lacks a timestamp.
        stale = c.execute(
            "SELECT id FROM observations WHERE synthesized=1 "
            "AND captured_at IS NOT NULL AND captured_at < ?",
            (cutoff,),
        ).fetchall()
        ids = [r[0] for r in stale]
        if not ids:
            return 0
        qmarks = ",".join("?" * len(ids))
        c.execute(
            f"INSERT INTO observations_archive ({col_list}) "
            f"SELECT {col_list} FROM observations WHERE id IN ({qmarks})",
            ids,
        )
        c.execute(f"DELETE FROM observations WHERE id IN ({qmarks})", ids)
        c.commit()
        return len(ids)
    except Exception:
        return 0
    finally:
        c.close()


def synthesize_one():
    """Pick the strongest unsynthesized theme, surface one knowing aside, mark it done.
    Returns an insight item dict (for the proactive queue) or None. Has a side effect
    (marks the observations synthesized) — call from the worker, not from pure scan()."""
    p = _obs_path()
    if not os.path.exists(p):
        return None
    try:
        c = sqlite3.connect(p)
        rows = c.execute(
            "SELECT id, content, relevance_hint FROM observations WHERE synthesized=0 "
            "ORDER BY id DESC LIMIT 50"
        ).fetchall()
    except Exception:
        return None
    if not rows:
        c.close()
        return None

    groups = defaultdict(list)
    for oid, content, hint in rows:
        groups[(hint or "you").strip() or "you"].append((oid, content))
    hint, items = max(groups.items(), key=lambda kv: len(kv[1]))
    ids = [oid for oid, _ in items]
    contents = [c2 for _, c2 in items if c2]
    contents = list(dict.fromkeys(contents))[:3]   # distinct, up to 3

    try:
        c.executemany("UPDATE observations SET synthesized=1 WHERE id=?", [(i,) for i in ids])
        c.commit()
    finally:
        c.close()

    if not contents:
        return None

    # Persist the insight to the Second Brain vault (topical note + Personal
    # Model), deduped — so a learned pattern GROWS the brain on disk instead of
    # only flashing on the HUD once and being lost.
    _persist_insight(hint, contents)

    body = " ".join(contents)
    return {
        "kind": "insight", "source": "synthesis", "key": f"knows:{hint}",
        "title": f"About your {hint}",
        "text": f"I've been noticing a pattern about your {hint}, sir: {body}",
        "visibility": "normal",
    }
