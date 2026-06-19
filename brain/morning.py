"""brain/morning.py — Morning prep (plan §1.2): "here's your day, sir, already staged."

A model-free assembly of the day's open goals, today's tasks, and anything waiting for
sir's approval — surfaced once, at his learned wake hour, as a warm Alfred open. Nothing
is sent (draft-only). When comms/calendar are connected, the staged drafts and resolved
conflicts slot straight into this card.
"""
import sqlite3
from datetime import date, datetime


def _conn():
    from memory import memory as _m
    return sqlite3.connect(_m.DB_PATH)


def _table(c, name) -> bool:
    try:
        return bool(c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())
    except Exception:
        return False


def build_morning_prep():
    """Assemble the morning item, or None if there's nothing worth opening the day with."""
    goals, tasks, pending = [], [], 0
    try:
        c = _conn()
        if _table(c, "goals"):
            goals = [r[0] for r in c.execute(
                "SELECT title FROM goals WHERE status='active' ORDER BY id LIMIT 5")]
        if _table(c, "tasks"):
            tasks = [r[0] for r in c.execute(
                "SELECT title FROM tasks WHERE done=0 ORDER BY id DESC LIMIT 5")]
        if _table(c, "pending_confirmations"):
            pending = c.execute(
                "SELECT COUNT(*) FROM pending_confirmations WHERE status='pending'").fetchone()[0]
        c.close()
    except Exception:
        return None

    if not (goals or tasks or pending):
        return None

    lines = ["Good morning, sir."]
    if pending:
        lines.append(f"{pending} item{'s' if pending != 1 else ''} waiting for your nod.")
    if tasks:
        lines.append("On your plate: " + "; ".join(tasks[:3]) + ("…" if len(tasks) > 3 else "."))
    if goals:
        lines.append("Toward your goals — " + ", ".join(goals[:3]) + ".")
    lines.append("Everything else I've kept watch on. Where shall we start?")

    return {
        "kind": "morning", "source": "initiative",
        "key": f"morning:{date.today().isoformat()}",
        "title": "Good morning, sir",
        "text": " ".join(lines),
        "visibility": "surface",
    }
