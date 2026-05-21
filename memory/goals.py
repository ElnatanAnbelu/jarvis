import sqlite3
from pathlib import Path
from datetime import date

DB_PATH = Path(__file__).parent / "jarvis.db"


def _conn():
    conn = sqlite3.connect(str(DB_PATH))
    # Migrate: ensure active column exists on goals
    try:
        conn.execute("ALTER TABLE goals ADD COLUMN active INTEGER DEFAULT 1")
        conn.execute("UPDATE goals SET active=1 WHERE status='active' OR status IS NULL")
        conn.commit()
    except Exception:
        pass
    # Ensure habit_logs exists
    conn.execute("""CREATE TABLE IF NOT EXISTS habit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        habit_id INTEGER,
        logged_date TEXT,
        UNIQUE(habit_id, logged_date)
    )""")
    conn.commit()
    return conn


def add_goal(title: str, category: str = "general") -> str:
    conn = _conn()
    # Use actual DB schema: title, description, category, status
    try:
        conn.execute(
            "INSERT INTO goals (title, category, status, active) VALUES (?, ?, 'active', 1)",
            (title, category)
        )
    except Exception:
        conn.execute("INSERT INTO goals (title, category) VALUES (?, ?)", (title, category))
    conn.commit()
    conn.close()
    return f"Goal added: {title}"


def add_habit(title: str) -> str:
    conn = _conn()
    # DB uses 'name' column
    try:
        conn.execute("INSERT INTO habits (name, frequency, active) VALUES (?, 'daily', 1)", (title,))
    except Exception:
        try:
            conn.execute("INSERT INTO habits (title, active) VALUES (?, 1)", (title,))
        except Exception:
            pass
    conn.commit()
    conn.close()
    return f"Habit added: {title}"


def _get_habits(conn):
    try:
        return conn.execute("SELECT id, name FROM habits WHERE active=1").fetchall()
    except Exception:
        try:
            return conn.execute("SELECT id, title FROM habits WHERE active=1").fetchall()
        except Exception:
            return []


def check_habit(title: str) -> str:
    today = str(date.today())
    conn = _conn()
    habits = _get_habits(conn)
    match = next((h for h in habits if title.lower() in h[1].lower()), None)
    if not match:
        conn.close()
        return f"No habit found matching '{title}'"
    try:
        conn.execute("INSERT INTO habit_logs (habit_id, logged_date) VALUES (?, ?)", (match[0], today))
        conn.commit()
        result = f"Habit logged: {match[1]} ✓"
    except sqlite3.IntegrityError:
        result = f"Already logged today: {match[1]}"
    conn.close()
    return result


def get_goals() -> str:
    conn = _conn()
    try:
        rows = conn.execute("SELECT title, category FROM goals WHERE active=1").fetchall()
    except Exception:
        rows = conn.execute("SELECT title, category FROM goals").fetchall()
    conn.close()
    if not rows:
        return "No goals set."
    return "\n".join(f"• [{r[1]}] {r[0]}" for r in rows)


def get_habits_status() -> str:
    today = str(date.today())
    conn = _conn()
    habits = _get_habits(conn)
    if not habits:
        conn.close()
        return "No habits tracked."
    lines = []
    for hid, name in habits:
        done = conn.execute(
            "SELECT 1 FROM habit_logs WHERE habit_id=? AND logged_date=?", (hid, today)
        ).fetchone()
        lines.append(f"{'✓' if done else '✗'} {name}")
    conn.close()
    return "\n".join(lines)


def get_missed_habits() -> list:
    today = str(date.today())
    conn = _conn()
    habits = _get_habits(conn)
    missed = []
    for hid, name in habits:
        done = conn.execute(
            "SELECT 1 FROM habit_logs WHERE habit_id=? AND logged_date=?", (hid, today)
        ).fetchone()
        if not done:
            missed.append(name)
    conn.close()
    return missed
