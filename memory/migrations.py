"""
Schema migration framework for JARVIS's memory DB.

Versioned, ordered, transactional, idempotent. Driven by SQLite's built-in
`PRAGMA user_version`. On every startup `run_migrations()` reads the current
user_version, applies every migration with a higher version inside its own
transaction, and bumps user_version. Safe to call on every boot and safe on a
DB that already has the legacy tables (additive / IF NOT EXISTS only).

To add schema changes, append a `(version, callable_or_sql)` tuple to
MIGRATIONS with the next integer version. Each migration is either a SQL
string (executed via executescript) or a callable taking a sqlite3 cursor.
"""
import sqlite3

from .memory import DB_PATH


def _column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    """True if `column` already exists on `table`. Older SQLite cannot do
    `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, so additive column migrations
    must guard themselves with this check to stay idempotent."""
    cur.execute("PRAGMA table_info(%s)" % table)
    return any(row[1] == column for row in cur.fetchall())


def _add_column_if_missing(cur: sqlite3.Cursor, table: str, column: str, decl: str):
    """ALTER TABLE ADD COLUMN, but only if the column isn't already present."""
    if not _column_exists(cur, table, column):
        cur.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, decl))


def _migration_1(cur: sqlite3.Cursor):
    """Block A safety substrate: extend the action ledger with reversibility /
    risk metadata, and add the pending-confirmations queue.

    Additive only — `actions_performed` rows are preserved. Safe whether or not
    the legacy tables already exist.
    """
    # Ensure the base table exists (in case migrations run before init_db's
    # CREATE TABLEs on a brand-new DB).
    cur.execute("""
        CREATE TABLE IF NOT EXISTS actions_performed (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            tool_name TEXT,
            args TEXT,
            result TEXT,
            success INTEGER DEFAULT 1
        )
    """)
    # Additive columns for the action ledger (reversibility + risk metadata).
    _add_column_if_missing(cur, "actions_performed", "agent", "TEXT")
    _add_column_if_missing(cur, "actions_performed", "risk", "TEXT")
    _add_column_if_missing(cur, "actions_performed", "inverse_tool", "TEXT")
    _add_column_if_missing(cur, "actions_performed", "inverse_args", "TEXT")
    _add_column_if_missing(cur, "actions_performed", "reverted", "INTEGER DEFAULT 0")
    _add_column_if_missing(cur, "actions_performed", "reverted_at", "TEXT")

    # Human-in-the-loop approval queue for risky tool calls.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pending_confirmations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            tool_name TEXT,
            args TEXT,
            agent TEXT,
            risk TEXT,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            result TEXT,
            resolved_at TEXT
        )
    """)


def _migration_2(cur: sqlite3.Cursor):
    """Reconcile the `people` table schema collision.

    Two modules historically declared `CREATE TABLE IF NOT EXISTS people` with
    DIFFERENT columns: memory/life.py (name/relationship/notes/last_contact/
    birthday) and memory/people.py (name/identifier/vip/family/blocked — the
    SAFETY columns the contact-aware gate reads). Whichever ran first won, and
    on the live DB life.py's create won, so people.list_people()'s
    `SELECT ... identifier, vip, family, blocked` raised OperationalError. That
    exception propagated into autonomy.gate(), which the registry swallowed and
    FAILED OPEN — silently bypassing the safety gate for every send-with-a-
    recipient. This migration makes the table the UNION of both schemas so both
    modules work and the gate can never raise on a schema mismatch again.
    """
    cur.execute("""
        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            identifier TEXT,
            vip INTEGER DEFAULT 0,
            family INTEGER DEFAULT 0,
            blocked INTEGER DEFAULT 0,
            relationship TEXT,
            notes TEXT,
            last_contact TEXT,
            birthday TEXT,
            created_at TEXT
        )
    """)
    # Backfill whichever columns a pre-existing legacy table is missing.
    for col, decl in (
        ("identifier", "TEXT"),
        ("vip", "INTEGER DEFAULT 0"),
        ("family", "INTEGER DEFAULT 0"),
        ("blocked", "INTEGER DEFAULT 0"),
        ("relationship", "TEXT"),
        ("notes", "TEXT"),
        ("last_contact", "TEXT"),
        ("birthday", "TEXT"),
        ("created_at", "TEXT"),
    ):
        _add_column_if_missing(cur, "people", col, decl)


# Ordered list of (version, sql_string_or_callable). Append new migrations with
# strictly increasing version numbers; never edit or reorder shipped ones.
MIGRATIONS = [
    (1, _migration_1),
    (2, _migration_2),
]


def _current_version(cur: sqlite3.Cursor) -> int:
    cur.execute("PRAGMA user_version")
    return cur.fetchone()[0]


def run_migrations(db_path=DB_PATH) -> int:
    """Apply every migration newer than the DB's current user_version.

    - Idempotent: re-running applies nothing once the DB is current.
    - Ordered: migrations run in ascending version order.
    - Transactional: each migration commits on its own; a failure rolls back
      that migration and leaves user_version pointing at the last good one.

    Returns the user_version after all applicable migrations have run.
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        current = _current_version(cur)
        for version, migration in sorted(MIGRATIONS, key=lambda m: m[0]):
            if version <= current:
                continue
            try:
                cur.execute("BEGIN")
                if callable(migration):
                    migration(cur)
                else:
                    cur.executescript(migration)
                # PRAGMA user_version doesn't accept bound params.
                cur.execute("PRAGMA user_version = %d" % version)
                conn.commit()
                current = version
            except Exception:
                conn.rollback()
                raise
        return current
    finally:
        conn.close()
