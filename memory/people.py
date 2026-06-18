"""People registry — VIPs, family, and the never-touch blocklist.

Backs the red-list refinement: a message/email to a VIP or family member always
needs the user's nod, and a blocked subject can never be actioned autonomously —
regardless of away-mode or autonomy mode. The user populates this (CLI/Telegram/
control room); it lives in jarvis.db (gitignored) since the names are personal.

Matching is substring-based and case-insensitive against each person's `name`
and `identifier` (email / phone / handle), in both directions, so "Reply to
nitsuh@x.com" matches a person stored as "nitsuh@x.com" or "Nitsuh".
"""
import sqlite3
from datetime import datetime

from . import memory


def init_people():
    conn = sqlite3.connect(memory.DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            identifier TEXT,
            vip INTEGER DEFAULT 0,
            family INTEGER DEFAULT 0,
            blocked INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def add_person(name: str, identifier: str = "", vip: bool = False,
               family: bool = False, blocked: bool = False) -> str:
    init_people()
    conn = sqlite3.connect(memory.DB_PATH)
    conn.execute(
        "INSERT INTO people (name, identifier, vip, family, blocked, created_at) VALUES (?,?,?,?,?,?)",
        (name, identifier, int(vip), int(family), int(blocked), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    tags = [t for t, on in (("VIP", vip), ("family", family), ("blocked", blocked)) if on]
    return f"Added {name}" + (f" ({', '.join(tags)})" if tags else "")


def list_people() -> list:
    init_people()
    conn = sqlite3.connect(memory.DB_PATH)
    rows = conn.execute(
        "SELECT name, identifier, vip, family, blocked FROM people ORDER BY name"
    ).fetchall()
    conn.close()
    return [{"name": n, "identifier": i, "vip": bool(v), "family": bool(f), "blocked": bool(b)}
            for n, i, v, f, b in rows]


def _hit(person_token: str, recipient: str) -> bool:
    person_token = (person_token or "").strip().lower()
    if not person_token:
        return False
    recipient = (recipient or "").lower()
    return person_token in recipient or recipient in person_token


def match(recipient: str) -> dict:
    """Return {vip, family, blocked} — True if ANY matching person carries that flag."""
    out = {"vip": False, "family": False, "blocked": False}
    if not recipient:
        return out
    for p in list_people():
        if _hit(p["name"], recipient) or _hit(p["identifier"], recipient):
            out["vip"] = out["vip"] or p["vip"]
            out["family"] = out["family"] or p["family"]
            out["blocked"] = out["blocked"] or p["blocked"]
    return out


def is_vip(recipient: str) -> bool:
    return match(recipient)["vip"]


def is_family(recipient: str) -> bool:
    return match(recipient)["family"]


def is_blocked(recipient: str) -> bool:
    return match(recipient)["blocked"]
