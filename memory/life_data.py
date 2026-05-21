"""
Life OS database — health, personal finance, reading, relationships.
"""
import sqlite3
from datetime import datetime, date
from pathlib import Path

DB_PATH = Path(__file__).parent / "life.db"


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _now():
    return datetime.now().isoformat(timespec="seconds")


def init_db():
    with _conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS health_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            type       TEXT NOT NULL,
            value      REAL,
            unit       TEXT,
            notes      TEXT,
            date       TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS personal_finance (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            type       TEXT NOT NULL,
            amount     REAL NOT NULL,
            category   TEXT,
            notes      TEXT,
            date       TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS reading_list (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT NOT NULL,
            author     TEXT,
            status     TEXT DEFAULT 'want',
            notes      TEXT,
            started_at TEXT,
            finished_at TEXT,
            rating     INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS relationship_dates (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            person     TEXT NOT NULL,
            event_type TEXT,
            date       TEXT NOT NULL,
            notes      TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS relationship_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            person     TEXT NOT NULL,
            notes      TEXT,
            date       TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS decisions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            question    TEXT NOT NULL,
            context     TEXT,
            chosen      TEXT,
            reasoning   TEXT,
            outcome     TEXT,
            status      TEXT DEFAULT 'pending',
            created_at  TEXT DEFAULT (datetime('now')),
            resolved_at TEXT
        );

        CREATE TABLE IF NOT EXISTS learning_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            skill      TEXT NOT NULL,
            type       TEXT,
            title      TEXT,
            notes      TEXT,
            date       TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """)


init_db()


# ── HEALTH ────────────────────────────────────────────────────────────────────

def log_health(type: str, value: float, unit: str = "", notes: str = "", date_str: str = "") -> str:
    d = date_str or date.today().isoformat()
    with _conn() as conn:
        conn.execute("INSERT INTO health_logs (type, value, unit, notes, date) VALUES (?,?,?,?,?)",
                     (type, value, unit, notes, d))
    return f"Logged: {type} = {value} {unit} on {d}"


def get_health_summary(type: str = "", days: int = 7) -> list:
    with _conn() as conn:
        if type:
            rows = conn.execute(
                "SELECT type, value, unit, notes, date FROM health_logs WHERE lower(type)=lower(?) AND date >= date('now', ?) ORDER BY date DESC",
                (type, f"-{days} days")
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT type, value, unit, notes, date FROM health_logs WHERE date >= date('now', ?) ORDER BY date DESC",
                (f"-{days} days",)
            ).fetchall()
    return [dict(r) for r in rows]


# ── PERSONAL FINANCE ──────────────────────────────────────────────────────────

def log_personal_finance(type: str, amount: float, category: str = "", notes: str = "", date_str: str = "") -> str:
    d = date_str or date.today().isoformat()
    with _conn() as conn:
        conn.execute("INSERT INTO personal_finance (type, amount, category, notes, date) VALUES (?,?,?,?,?)",
                     (type, amount, category, notes, d))
    label = "Income" if type == "income" else "Expense"
    return f"Personal {label}: ${amount:,.2f} ({category}) on {d}"


def get_personal_finance_summary(period: str = "month") -> dict:
    with _conn() as conn:
        if period == "month":
            where = "AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')"
        elif period == "year":
            where = "AND strftime('%Y', date) = strftime('%Y', 'now')"
        else:
            where = ""
        rows = conn.execute(
            f"SELECT type, amount, category, date FROM personal_finance WHERE 1=1 {where} ORDER BY date DESC",
        ).fetchall()
    income = sum(r["amount"] for r in rows if r["type"] == "income")
    expenses = sum(r["amount"] for r in rows if r["type"] == "expense")
    by_cat = {}
    for r in rows:
        if r["type"] == "expense":
            by_cat[r["category"] or "other"] = by_cat.get(r["category"] or "other", 0) + r["amount"]
    return {
        "period": period,
        "income": income,
        "expenses": expenses,
        "net": income - expenses,
        "by_category": by_cat,
        "transactions": [dict(r) for r in rows[:20]],
    }


# ── READING LIST ──────────────────────────────────────────────────────────────

def add_book(title: str, author: str = "", status: str = "want", notes: str = "") -> str:
    with _conn() as conn:
        conn.execute("INSERT INTO reading_list (title, author, status, notes) VALUES (?,?,?,?)",
                     (title, author, status, notes))
    return f"Added to reading list: '{title}' by {author or 'unknown'} [{status}]"


def update_book(title: str, status: str, rating: int = None, notes: str = "") -> str:
    with _conn() as conn:
        row = conn.execute("SELECT id FROM reading_list WHERE lower(title) LIKE lower(?)", (f"%{title}%",)).fetchone()
        if not row:
            return f"Book '{title}' not found."
        updates = {"status": status}
        if status == "reading":
            updates["started_at"] = _now()[:10]
        if status == "done":
            updates["finished_at"] = _now()[:10]
        if rating:
            updates["rating"] = rating
        if notes:
            updates["notes"] = notes
        set_clause = ", ".join(f"{k}=?" for k in updates)
        conn.execute(f"UPDATE reading_list SET {set_clause} WHERE id=?", list(updates.values()) + [row["id"]])
    return f"'{title}' updated to [{status}]" + (f" — rated {rating}/5" if rating else "")


def get_reading_list(status: str = "") -> list:
    with _conn() as conn:
        if status:
            rows = conn.execute("SELECT * FROM reading_list WHERE status=? ORDER BY created_at DESC", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM reading_list ORDER BY status, created_at DESC").fetchall()
    return [dict(r) for r in rows]


# ── RELATIONSHIPS ─────────────────────────────────────────────────────────────

def add_relationship_date(person: str, event_type: str, date_str: str, notes: str = "") -> str:
    with _conn() as conn:
        conn.execute("INSERT INTO relationship_dates (person, event_type, date, notes) VALUES (?,?,?,?)",
                     (person, event_type, date_str, notes))
    return f"Saved: {person}'s {event_type} on {date_str}"


def get_upcoming_dates(days: int = 30) -> list:
    today = date.today()
    results = []
    with _conn() as conn:
        rows = conn.execute("SELECT person, event_type, date, notes FROM relationship_dates").fetchall()
    for row in rows:
        try:
            evt_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
            this_year = evt_date.replace(year=today.year)
            if this_year < today:
                this_year = this_year.replace(year=today.year + 1)
            delta = (this_year - today).days
            if 0 <= delta <= days:
                results.append({**dict(row), "days_away": delta, "this_year_date": str(this_year)})
        except Exception:
            pass
    return sorted(results, key=lambda x: x["days_away"])


def log_relationship(person: str, notes: str, date_str: str = "") -> str:
    d = date_str or date.today().isoformat()
    with _conn() as conn:
        conn.execute("INSERT INTO relationship_logs (person, notes, date) VALUES (?,?,?)", (person, notes, d))
    return f"Logged conversation with {person} on {d}"


def get_relationship_history(person: str, limit: int = 10) -> list:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT notes, date FROM relationship_logs WHERE lower(person) LIKE lower(?) ORDER BY date DESC LIMIT ?",
            (f"%{person}%", limit)
        ).fetchall()
    return [dict(r) for r in rows]


# ── DECISIONS ─────────────────────────────────────────────────────────────────

def log_decision(question: str, chosen: str, reasoning: str = "", context: str = "") -> str:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO decisions (question, chosen, reasoning, context, status) VALUES (?,?,?,?,'active')",
            (question, chosen, reasoning, context)
        )
    return f"Decision logged: '{question}' → '{chosen}'"


def resolve_decision(question: str, outcome: str) -> str:
    with _conn() as conn:
        row = conn.execute("SELECT id FROM decisions WHERE lower(question) LIKE lower(?) AND status='active'",
                           (f"%{question}%",)).fetchone()
        if not row:
            return f"Decision not found: '{question}'"
        conn.execute("UPDATE decisions SET outcome=?, status='resolved', resolved_at=? WHERE id=?",
                     (outcome, _now(), row["id"]))
    return f"Decision resolved. Outcome logged: {outcome}"


def get_decisions(status: str = "") -> list:
    with _conn() as conn:
        if status:
            rows = conn.execute("SELECT * FROM decisions WHERE status=? ORDER BY created_at DESC", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM decisions ORDER BY created_at DESC LIMIT 20").fetchall()
    return [dict(r) for r in rows]


# ── LEARNING ──────────────────────────────────────────────────────────────────

def log_learning(skill: str, type: str = "session", title: str = "", notes: str = "", date_str: str = "") -> str:
    d = date_str or date.today().isoformat()
    with _conn() as conn:
        conn.execute("INSERT INTO learning_log (skill, type, title, notes, date) VALUES (?,?,?,?,?)",
                     (skill, type, title, notes, d))
    return f"Logged learning: {skill} — {title or type} on {d}"


def get_learning_summary(days: int = 7) -> list:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT skill, type, title, notes, date FROM learning_log WHERE date >= date('now', ?) ORDER BY date DESC",
            (f"-{days} days",)
        ).fetchall()
    return [dict(r) for r in rows]
