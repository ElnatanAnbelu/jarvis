import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "jarvis.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            role TEXT,
            content TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            key TEXT,
            value TEXT,
            updated_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_message(role: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO conversations (timestamp, role, content) VALUES (?, ?, ?)",
              (datetime.now().isoformat(), role, content))
    conn.commit()
    conn.close()

def get_recent_history(limit: int = 10) -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role, content FROM conversations ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return list(reversed(rows))

def _meta_get(key: str, default: str = "") -> str:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM meta WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def _meta_set(key: str, value: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def save_fact(category: str, key: str, value: str):
    # Normalize key for better dedup
    norm_key = key.strip().lower().replace(" ", "_")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM facts WHERE category=? AND key=?", (category, norm_key))
    existing = c.fetchone()
    if existing:
        c.execute("UPDATE facts SET value=?, updated_at=? WHERE id=?",
                  (value, datetime.now().isoformat(), existing[0]))
    else:
        c.execute("INSERT INTO facts (category, key, value, updated_at) VALUES (?, ?, ?, ?)",
                  (category, norm_key, value, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    # Track unsaved count for auto-consolidation trigger
    try:
        count = int(_meta_get("facts_since_consolidation", "0")) + 1
        _meta_set("facts_since_consolidation", str(count))
        if count >= 10:
            import threading
            threading.Thread(target=consolidate_facts, daemon=True).start()
    except Exception:
        pass


def consolidate_facts():
    """Ask Claude to deduplicate and resolve contradictions in the fact list.
    Runs in background. Replaces the facts table with a clean version.
    """
    raw = get_facts()
    if not raw or len(raw.splitlines()) < 4:
        return  # Not enough facts to bother

    try:
        import os, sys
        from pathlib import Path as _P
        sys.path.insert(0, str(_P(__file__).parent.parent))
        api_key = (
            os.environ.get("ANTHROPIC_API_KEY", "").strip() or
            os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
        )
        if not api_key:
            return

        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        prompt = f"""You are a memory consolidation system. Below is a list of personal facts about Elnatan.

Your task:
1. Remove exact and semantic duplicates (same fact stored with different keys).
2. If two facts contradict each other (e.g., different cities listed as current location), keep the more recent/specific one and discard the older/vaguer one.
3. Merge related facts where logical (e.g., "age: 20" and "born: 2004" can coexist — don't merge those).
4. Keep ALL facts that are genuinely distinct.
5. Output ONLY the cleaned facts, one per line, in this exact format: [category] key: value
6. No commentary, no explanation, no markdown.

CURRENT FACTS:
{raw}

CLEANED FACTS:"""

        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        cleaned = msg.content[0].text.strip()
        if not cleaned:
            return

        # Parse cleaned facts back into (category, key, value)
        new_facts = []
        for line in cleaned.splitlines():
            line = line.strip()
            if not line or not line.startswith("["):
                continue
            try:
                cat_end = line.index("]")
                category = line[1:cat_end].strip()
                rest = line[cat_end + 1:].strip()
                if ":" not in rest:
                    continue
                key, value = rest.split(":", 1)
                new_facts.append((category, key.strip().lower().replace(" ", "_"), value.strip()))
            except Exception:
                continue

        if not new_facts:
            return

        # Atomic replace of facts table
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM facts")
        now = datetime.now().isoformat()
        for category, key, value in new_facts:
            c.execute("INSERT INTO facts (category, key, value, updated_at) VALUES (?, ?, ?, ?)",
                      (category, key, value, now))
        conn.commit()
        conn.close()
        _meta_set("facts_since_consolidation", "0")
        _meta_set("last_consolidation", datetime.now().isoformat())

    except Exception:
        pass

def get_facts() -> str:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT category, key, value FROM facts ORDER BY category")
    rows = c.fetchall()
    conn.close()
    if not rows:
        return ""
    lines = []
    for category, key, value in rows:
        lines.append(f"[{category}] {key}: {value}")
    return "\n".join(lines)

def format_history_for_prompt(limit: int = 10) -> str:
    history = get_recent_history(limit)
    if not history:
        return ""
    lines = []
    for role, content in history:
        label = "ELNATAN" if role == "user" else role.upper()
        lines.append(f"{label}: {content[:800]}")
    return "\n".join(lines)


def build_messages_for_prompt(current_input: str, limit: int = 15) -> list:
    """Return a proper multi-turn messages list for API calls.
    Maps all agent roles to 'assistant'. Merges consecutive same-role turns.
    Assumes current_input is already saved to the DB before this is called.
    """
    history = get_recent_history(limit)
    msgs = []
    for role, content in history:
        api_role = "user" if role == "user" else "assistant"
        text = content[:800]
        if msgs and msgs[-1]["role"] == api_role:
            msgs[-1]["content"] += "\n" + text
        else:
            msgs.append({"role": api_role, "content": text})
    # Must start with user
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    # If history didn't include current input, add it
    if not msgs or msgs[-1]["role"] != "user":
        msgs.append({"role": "user", "content": current_input})
    return msgs or [{"role": "user", "content": current_input}]

init_db()
