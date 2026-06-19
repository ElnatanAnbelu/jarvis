"""brain/synthesis.py — the 'knows me' loop (plan §6).

Staged observations (memory/observations.py) become a *knowing aside* — "I've noticed a
pattern about your …, sir." One theme per pass (low-frequency, companion-toned, never
noisy); the observations behind it are marked synthesized so the backlog drains over time
instead of re-surfacing.
"""
import os
import sqlite3
from collections import defaultdict


def _obs_path():
    from memory import memory as _m
    return os.path.join(os.path.dirname(_m.DB_PATH), "observations.db")


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
    body = " ".join(contents)
    return {
        "kind": "insight", "source": "synthesis", "key": f"knows:{hint}",
        "title": f"About your {hint}",
        "text": f"I've been noticing a pattern about your {hint}, sir: {body}",
        "visibility": "normal",
    }
