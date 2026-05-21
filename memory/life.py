import sqlite3
import json
from datetime import datetime, date
from pathlib import Path

DB_PATH = Path(__file__).parent / "jarvis.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_life_tables():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, description TEXT, category TEXT,
        status TEXT DEFAULT 'active',
        created_at TEXT, deadline TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS habits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, frequency TEXT, streak INTEGER DEFAULT 0,
        last_checked TEXT, active INTEGER DEFAULT 1
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS people (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE, relationship TEXT,
        notes TEXT, last_contact TEXT, birthday TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, priority TEXT DEFAULT 'medium',
        due_date TEXT, done INTEGER DEFAULT 0,
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount REAL, category TEXT, description TEXT,
        date TEXT
    )""")
    conn.commit()
    conn.close()

# Goals
def add_goal(title, description="", category="personal", deadline=None):
    conn = get_conn()
    conn.execute("INSERT INTO goals (title,description,category,created_at,deadline) VALUES (?,?,?,?,?)",
                 (title, description, category, datetime.now().isoformat(), deadline))
    conn.commit(); conn.close()
    return f"Goal added: {title}"

def get_goals(status="active"):
    conn = get_conn()
    rows = conn.execute("SELECT title,category,deadline FROM goals WHERE status=?", (status,)).fetchall()
    conn.close()
    if not rows: return "No active goals."
    return "\n".join([f"• [{r[1]}] {r[0]}" + (f" (due {r[2]})" if r[2] else "") for r in rows])

def complete_goal(title):
    conn = get_conn()
    conn.execute("UPDATE goals SET status='completed' WHERE title LIKE ?", (f'%{title}%',))
    conn.commit(); conn.close()
    return f"Goal completed: {title}"

# Habits
def add_habit(name, frequency="daily"):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO habits (name,frequency) VALUES (?,?)", (name, frequency))
    conn.commit(); conn.close()
    return f"Habit tracked: {name}"

def check_habit(name):
    conn = get_conn()
    today = date.today().isoformat()
    row = conn.execute("SELECT id,streak,last_checked FROM habits WHERE name LIKE ?", (f'%{name}%',)).fetchone()
    if not row: conn.close(); return "Habit not found."
    hid, streak, last = row
    if last == today:
        conn.close(); return f"Already checked in for {name} today. Streak: {streak} days."
    new_streak = streak + 1
    conn.execute("UPDATE habits SET streak=?,last_checked=? WHERE id=?", (new_streak, today, hid))
    conn.commit(); conn.close()
    return f"✓ {name} — streak: {new_streak} days."

def get_habits():
    conn = get_conn()
    rows = conn.execute("SELECT name,frequency,streak,last_checked FROM habits WHERE active=1").fetchall()
    conn.close()
    if not rows: return "No habits tracked."
    today = date.today().isoformat()
    out = []
    for name, freq, streak, last in rows:
        done = "✓" if last == today else "○"
        out.append(f"{done} {name} ({freq}) — {streak} day streak")
    return "\n".join(out)

# People
def add_person(name, relationship="", notes="", birthday=None):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO people (name,relationship,notes,birthday) VALUES (?,?,?,?)",
                 (name, relationship, notes, birthday))
    conn.commit(); conn.close()
    return f"Remembered {name}."

def get_person(name):
    conn = get_conn()
    row = conn.execute("SELECT name,relationship,notes,last_contact,birthday FROM people WHERE name LIKE ?",
                       (f'%{name}%',)).fetchone()
    conn.close()
    if not row: return f"No info on {name}."
    return f"{row[0]} ({row[1]})\n{row[2]}\nLast contact: {row[3] or 'never'}\nBirthday: {row[4] or 'unknown'}"

def log_contact(name):
    conn = get_conn()
    conn.execute("UPDATE people SET last_contact=? WHERE name LIKE ?", (date.today().isoformat(), f'%{name}%'))
    conn.commit(); conn.close()
    return f"Logged contact with {name}."

# Tasks
def add_task(title, priority="medium", due_date=None):
    conn = get_conn()
    conn.execute("INSERT INTO tasks (title,priority,due_date,created_at) VALUES (?,?,?,?)",
                 (title, priority, due_date, datetime.now().isoformat()))
    conn.commit(); conn.close()
    return f"Task added: {title}"

def get_tasks():
    conn = get_conn()
    rows = conn.execute("SELECT title,priority,due_date FROM tasks WHERE done=0 ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END").fetchall()
    conn.close()
    if not rows: return "No pending tasks."
    return "\n".join([f"• [{r[1].upper()}] {r[0]}" + (f" — due {r[2]}" if r[2] else "") for r in rows])

def complete_task(title):
    conn = get_conn()
    conn.execute("UPDATE tasks SET done=1 WHERE title LIKE ?", (f'%{title}%',))
    conn.commit(); conn.close()
    return f"Task done: {title}"

# Expenses
def log_expense(amount, category, description=""):
    conn = get_conn()
    conn.execute("INSERT INTO expenses (amount,category,description,date) VALUES (?,?,?,?)",
                 (amount, category, description, date.today().isoformat()))
    conn.commit(); conn.close()
    return f"Logged ${amount} — {category}"

def get_spending_summary():
    conn = get_conn()
    rows = conn.execute("SELECT category, SUM(amount) FROM expenses WHERE date >= date('now','-30 days') GROUP BY category").fetchall()
    conn.close()
    if not rows: return "No expenses logged this month."
    total = sum(r[1] for r in rows)
    lines = [f"• {r[0]}: ${r[1]:.2f}" for r in rows]
    lines.append(f"Total this month: ${total:.2f}")
    return "\n".join(lines)

# Morning briefing
def morning_briefing():
    today = date.today().strftime("%A, %B %d")
    goals = get_goals()
    habits = get_habits()
    tasks = get_tasks()

    # Birthdays today
    conn = get_conn()
    today_md = date.today().strftime("-%m-%d")
    bdays = conn.execute("SELECT name FROM people WHERE birthday LIKE ?", (f'%{today_md}',)).fetchall()
    conn.close()

    briefing = f"Good morning, Elnatan. Today is {today}.\n\n"

    if bdays:
        briefing += f"🎂 BIRTHDAYS TODAY: {', '.join(b[0] for b in bdays)}\n\n"

    briefing += f"YOUR GOALS:\n{goals}\n\n"
    briefing += f"TODAY'S HABITS:\n{habits}\n\n"
    briefing += f"PENDING TASKS:\n{tasks}"

    return briefing

init_life_tables()
