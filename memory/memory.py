import sqlite3
import json
import threading
from datetime import datetime, timedelta
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
    # Every tool execution — survives the 30-message window
    c.execute("""
        CREATE TABLE IF NOT EXISTS actions_performed (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            tool_name TEXT,
            args TEXT,
            result TEXT,
            success INTEGER DEFAULT 1
        )
    """)
    # User-defined recurring tasks JARVIS can register at runtime
    c.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            description TEXT,
            schedule TEXT,
            last_run TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()
    # Apply versioned schema migrations (ledger reversibility columns,
    # pending_confirmations table, …). Idempotent — safe every startup.
    try:
        from .migrations import run_migrations
        run_migrations(DB_PATH)
    except Exception:
        pass


# ── Conversations ──────────────────────────────────────────────────────────────

def save_message(role: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO conversations (timestamp, role, content) VALUES (?, ?, ?)",
              (datetime.now().isoformat(), role, content))
    conn.commit()
    conn.close()
    # Trigger background compression every 15 messages — non-blocking
    try:
        maybe_compress_history()
    except Exception:
        pass


def get_recent_history(limit: int = 10) -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role, content FROM conversations ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return list(reversed(rows))


# ── Meta ───────────────────────────────────────────────────────────────────────

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


# ── Facts ──────────────────────────────────────────────────────────────────────

def save_fact(category: str, key: str, value: str):
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
    try:
        count = int(_meta_get("facts_since_consolidation", "0")) + 1
        _meta_set("facts_since_consolidation", str(count))
        if count >= 10:
            import threading
            threading.Thread(target=consolidate_facts, daemon=True).start()
    except Exception:
        pass


def consolidate_facts():
    raw = get_facts()
    if not raw or len(raw.splitlines()) < 4:
        return
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
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            messages=[{"role": "user", "content": f"""Memory consolidation. Remove duplicates, resolve contradictions (keep newer), keep all distinct facts.
Output ONLY cleaned facts, one per line: [category] key: value

FACTS:
{raw}

CLEANED:"""}],
        )
        cleaned = msg.content[0].text.strip()
        if not cleaned:
            return
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
    return "\n".join(f"[{cat}] {key}: {val}" for cat, key, val in rows)


# ── Session Summary ────────────────────────────────────────────────────────────

def save_session_summary(summary: str):
    """Overwrite the session summary. Only the most recent session matters."""
    _meta_set("session_summary", summary)
    _meta_set("session_summary_at", datetime.now().isoformat())


def get_last_session_summary() -> str:
    """Return the last session summary if saved within 14 days, else empty."""
    summary = _meta_get("session_summary", "")
    if not summary:
        return ""
    saved_at = _meta_get("session_summary_at", "")
    if saved_at:
        try:
            saved_dt = datetime.fromisoformat(saved_at)
            if (datetime.now() - saved_dt).days > 14:
                return ""
        except Exception:
            pass
    return summary


# ── History Compression ───────────────────────────────────────────────────────
#
# Every 15 new messages, a background Haiku call compresses all messages older
# than the last 10 into a dense summary paragraph stored in the meta table.
# The summary is injected into the system context by brain/think.py so JARVIS
# retains full strategic continuity while the messages array stays small.

_compression_active = [False]  # mutable flag — thread-safe under CPython GIL


def get_history_summary() -> str:
    """Return the rolling compressed history summary, or empty string if none yet."""
    return _meta_get("history_summary", "")


def save_history_summary(summary: str):
    """Persist the compressed summary and record the message count it covers."""
    _meta_set("history_summary", summary)
    _meta_set("history_summary_at", datetime.now().isoformat())
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM conversations")
    count = c.fetchone()[0]
    conn.close()
    _meta_set("history_summary_count", str(count))


def _compress_history_bg(messages_to_compress):
    """
    Background: call Haiku to compress old messages → dense summary paragraph.
    Runs in a daemon thread — zero hot-path latency impact.
    """
    try:
        import os as _os
        api_key = (
            _os.environ.get("ANTHROPIC_API_KEY", "").strip() or
            _os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
        )
        if not api_key or not messages_to_compress:
            return

        lines = []
        for role, content in messages_to_compress:
            label = "Elnatan" if role == "user" else "JARVIS"
            lines.append("{}: {}".format(label, (content or "")[:300]))
        convo_text = "\n".join(lines)

        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": (
                    "Compress this conversation into a dense summary paragraph for an AI assistant's context.\n\n"
                    "PRESERVE: decisions made, tasks started or completed, business context "
                    "(Addis Market, Nexel, goals, contacts), instructions given to JARVIS, "
                    "important facts shared, tools used and their outcomes.\n"
                    "DISCARD: pleasantries, small talk, questions whose answers are captured above.\n\n"
                    "Write ONE dense paragraph (150-200 words). Be specific. Past tense. No filler.\n\n"
                    "CONVERSATION:\n{}\n\nSUMMARY:".format(convo_text)
                )
            }]
        )
        summary = (resp.content[0].text or "").strip()
        if summary and len(summary) > 30:
            save_history_summary(summary)
    except Exception:
        pass
    finally:
        _compression_active[0] = False


def maybe_compress_history():
    """
    Trigger point: called after each message save. Spawns background compression
    when the conversation has grown 15+ messages since the last compression run.
    The check itself is <2ms — no hot-path impact.
    """
    if _compression_active[0]:
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM conversations")
        total = c.fetchone()[0]
        conn.close()

        last_count = int(_meta_get("history_summary_count", "0"))
        if total - last_count < 15:
            return

        # Only compress when there are more than 10 messages to trim
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT role, content FROM conversations ORDER BY id DESC")
        all_msgs = c.fetchall()
        conn.close()

        if len(all_msgs) <= 10:
            return

        # Compress everything beyond the last 10 verbatim messages
        older = list(reversed(all_msgs[10:]))
        _compression_active[0] = True
        threading.Thread(
            target=_compress_history_bg,
            args=(older,),
            daemon=True,
        ).start()
    except Exception:
        _compression_active[0] = False


def build_messages_compressed(current_input, recent_limit=10):
    """
    Messages array using compressed history.

    When a summary exists:
      Returns only the last `recent_limit` verbatim messages.
      The summary is injected into the system context by _build_context()
      in brain/think.py — this function just keeps the array small.

    When no summary exists yet (early conversation):
      Falls back to the standard 30-message window so nothing is lost.
    """
    if get_history_summary():
        return build_messages_for_prompt(current_input, limit=recent_limit)
    return build_messages_for_prompt(current_input, limit=30)


# ── Actions Performed Log ──────────────────────────────────────────────────────

def log_action(tool_name: str, args: dict, result: str, success: bool = True,
               agent=None, risk=None, inverse_tool=None, inverse_args=None) -> int:
    """Persist every tool call so JARVIS remembers actions beyond the 30-message window.

    Extended for the safety substrate (Block A): records the calling `agent`,
    the assessed `risk` band, and an optional inverse operation
    (`inverse_tool` + `inverse_args` as a JSON string or dict) so the action can
    be reverted later via revert_action(). Returns the inserted row id.

    Backward compatible: existing callers passing (tool_name, args, result,
    success=...) positionally keep working unchanged.
    """
    if inverse_args is not None and not isinstance(inverse_args, str):
        inverse_args = json.dumps(inverse_args)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO actions_performed "
        "(timestamp, tool_name, args, result, success, agent, risk, inverse_tool, inverse_args) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), tool_name, json.dumps(args), str(result)[:500],
         int(success), agent, risk, inverse_tool, inverse_args)
    )
    row_id = c.lastrowid
    conn.commit()
    conn.close()
    return row_id


def revert_action(action_id: int) -> str:
    """Undo a previously logged action by executing its recorded inverse tool.

    Loads the action row; if it was already reverted or has no inverse_tool,
    returns a clear message and does nothing. Otherwise executes the inverse via
    the tool registry, marks the row reverted (reverted=1 + reverted_at), and
    returns a human-readable result.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT tool_name, inverse_tool, inverse_args, reverted FROM actions_performed WHERE id=?",
        (action_id,)
    )
    row = c.fetchone()
    if row is None:
        conn.close()
        return f"No action found with id {action_id}."
    tool_name, inverse_tool, inverse_args, reverted = row
    if reverted:
        conn.close()
        return f"Action {action_id} ({tool_name}) was already reverted."
    if not inverse_tool:
        conn.close()
        return f"Action {action_id} ({tool_name}) has no inverse — it cannot be undone."
    conn.close()

    # Guarded import — avoids a circular import at module load time.
    try:
        from brain.tools.registry import execute_tool
    except Exception as e:
        return f"Cannot revert action {action_id}: tool registry unavailable ({e})."

    try:
        inv_args = json.loads(inverse_args or "{}")
    except Exception:
        inv_args = {}

    try:
        # A revert is an explicitly user-authorized compensating action, so it
        # bypasses the gate — otherwise undoing a red-list action would itself
        # need confirmation (deadlock), and panic couldn't revert in away-mode.
        # The self-write firewall in control/files.py still applies, so a revert
        # can never be used to write into JARVIS's own install tree.
        result = execute_tool(inverse_tool, inv_args, _bypass_gate=True)
    except Exception as e:
        return f"Revert of action {action_id} ({tool_name}) failed: {e}"

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE actions_performed SET reverted=1, reverted_at=? WHERE id=?",
        (datetime.now().isoformat(), action_id)
    )
    conn.commit()
    conn.close()
    return f"Reverted action {action_id} ({tool_name}) via {inverse_tool}: {result}"


def revert_recent(minutes: int = 1440) -> str:
    """Revert every reversible (has an inverse, not yet reverted) action logged in
    the last `minutes`. Used by the panic control."""
    cutoff = (datetime.now() - timedelta(minutes=minutes)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id FROM actions_performed "
        "WHERE timestamp >= ? AND inverse_tool IS NOT NULL AND inverse_tool != '' "
        "AND (reverted IS NULL OR reverted = 0) ORDER BY id DESC",
        (cutoff,)
    )
    ids = [r[0] for r in c.fetchall()]
    conn.close()
    if not ids:
        return "no reversible actions in that window"
    for i in ids:
        revert_action(i)
    return f"reverted {len(ids)} action(s)"


def forget_subject(identifier: str) -> str:
    """Right-to-be-forgotten across jarvis.db — purge a person/topic from
    conversations, facts, and the action ledger. (Vault/observations purge is
    layered on top by the caller.) Refuses dangerously-broad identifiers."""
    ident = (identifier or "").strip()
    if len(ident) < 3:
        return "Refusing to forget — give a specific name/identifier (3+ chars)."
    like = f"%{ident}%"
    counts = {}
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    def _purge_text_table(table):
        """Delete any row of `table` whose TEXT columns mention the subject.
        Schema-agnostic (introspects columns) so people/goals/tasks/expenses are
        all covered without hardcoding columns; tolerant of missing tables."""
        try:
            cols = [r[1] for r in c.execute("PRAGMA table_info(%s)" % table).fetchall()
                    if (r[2] or "").upper() in ("TEXT", "")]
            if not cols:
                return
            where = " OR ".join("%s LIKE ?" % col for col in cols)
            c.execute("DELETE FROM %s WHERE %s" % (table, where), tuple(like for _ in cols))
            if c.rowcount:
                counts[table] = counts.get(table, 0) + c.rowcount
        except Exception:
            pass

    try:
        c.execute("DELETE FROM conversations WHERE content LIKE ?", (like,))
        counts["conversations"] = c.rowcount
        c.execute("DELETE FROM facts WHERE key LIKE ? OR value LIKE ?", (like, like))
        counts["facts"] = c.rowcount
        # save_fact normalizes keys (lower, spaces→underscores), so a multi-word
        # subject ("John Doe") lands under "john_doe_*" and the raw LIKE misses it.
        norm = ident.strip().lower().replace(" ", "_")
        if norm and norm != ident.lower():
            c.execute("DELETE FROM facts WHERE key LIKE ?", ("%" + norm + "%",))
            counts["facts"] += c.rowcount
        c.execute("DELETE FROM actions_performed WHERE args LIKE ? OR result LIKE ?", (like, like))
        counts["actions"] = c.rowcount
        # People registry (phone/email/notes/relationship/flags) + life data that
        # names the subject — all in this same jarvis.db, previously left intact.
        for tbl in ("people", "goals", "tasks", "expenses"):
            _purge_text_table(tbl)
        conn.commit()
    finally:
        conn.close()
    total = sum(counts.values())
    try:
        from obs.log import log_event
        log_event("privacy.forget_subject", level="warning", subject=ident, removed=total, by_store=counts)
    except Exception:
        pass
    return f"Forgot '{ident}' from local memory: removed {total} record(s) — {counts}."


# ── Flags (booleans/strings over the meta table) ────────────────────────────────

def get_flag(key: str, default=None):
    """Read a runtime flag from the meta table (e.g. away_mode, paused).

    Stored as 'true'/'false' for booleans. When `default` is a bool, returns a
    bool (the stored 'true'/'false', or `default` if unset). Otherwise returns
    the stored string, or `default` if unset.
    """
    sentinel = "\x00__unset__"
    raw = _meta_get(key, sentinel)
    if raw == sentinel:
        return default
    if isinstance(default, bool):
        return raw == "true"
    return raw


def set_flag(key: str, value):
    """Persist a runtime flag to the meta table. Bools are stored as
    'true'/'false'; everything else is stored as its string form."""
    if isinstance(value, bool):
        stored = "true" if value else "false"
    else:
        stored = str(value)
    _meta_set(key, stored)


# ── Pending Confirmations (human-in-the-loop approval queue) ─────────────────────

_CONFIRMATION_TERMINAL = {"approved", "rejected", "executed", "failed", "cancelled"}


def enqueue_confirmation(tool_name: str, args: dict, agent=None, risk=None, reason: str = "") -> int:
    """Queue a risky tool call awaiting human approval. Returns the row id."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO pending_confirmations "
        "(created_at, tool_name, args, agent, risk, reason, status) "
        "VALUES (?, ?, ?, ?, ?, ?, 'pending')",
        (datetime.now().isoformat(), tool_name, json.dumps(args), agent, risk, reason)
    )
    row_id = c.lastrowid
    conn.commit()
    conn.close()
    return row_id


def _confirmation_row_to_dict(row) -> dict:
    cid, created_at, tool_name, args_str, agent, risk, reason, status, result, resolved_at = row
    try:
        args = json.loads(args_str) if args_str else {}
    except Exception:
        args = {}
    return {
        "id": cid,
        "created_at": created_at,
        "tool_name": tool_name,
        "args": args,
        "agent": agent,
        "risk": risk,
        "reason": reason,
        "status": status,
        "result": result,
        "resolved_at": resolved_at,
    }


_CONFIRMATION_COLUMNS = (
    "id, created_at, tool_name, args, agent, risk, reason, status, result, resolved_at"
)


def get_pending_confirmations() -> list:
    """Return all confirmations still in 'pending' status, oldest first."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT %s FROM pending_confirmations WHERE status='pending' ORDER BY id ASC"
        % _CONFIRMATION_COLUMNS
    )
    rows = c.fetchall()
    conn.close()
    return [_confirmation_row_to_dict(r) for r in rows]


def get_confirmation(cid: int):
    """Return a single confirmation by id as a dict, or None if not found."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT %s FROM pending_confirmations WHERE id=?" % _CONFIRMATION_COLUMNS,
        (cid,)
    )
    row = c.fetchone()
    conn.close()
    return _confirmation_row_to_dict(row) if row else None


def set_confirmation_status(cid: int, status: str, result=None):
    """Update a confirmation's status (and optional result). Stamps resolved_at
    when the status is terminal (approved/rejected/executed/failed/cancelled)."""
    resolved_at = datetime.now().isoformat() if status in _CONFIRMATION_TERMINAL else None
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if result is not None:
        c.execute(
            "UPDATE pending_confirmations SET status=?, result=?, resolved_at=? WHERE id=?",
            (status, str(result), resolved_at, cid)
        )
    else:
        c.execute(
            "UPDATE pending_confirmations SET status=?, resolved_at=? WHERE id=?",
            (status, resolved_at, cid)
        )
    conn.commit()
    conn.close()


def get_recent_actions(limit: int = 20) -> str:
    """Return last N tool executions as a readable string for prompt injection."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT timestamp, tool_name, args, result, success FROM actions_performed ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = c.fetchall()
    conn.close()
    if not rows:
        return ""
    lines = []
    for ts, tool, args_str, result, success in reversed(rows):
        try:
            args = json.loads(args_str)
        except Exception:
            args = {}
        status = "OK" if success else "FAILED"
        short_args = ", ".join(f"{k}={v}" for k, v in list(args.items())[:3])
        lines.append(f"[{ts[:16]}] {tool}({short_args}) → {status}: {result[:80]}")
    return "\n".join(lines)


def get_recent_actions_list(limit: int = 20) -> list:
    """Return last N tool executions as structured rows for the control room UI.

    Rows are dicts {id, ts, tool, success, reverted}, newest first, so the UI can
    render per-row state and an Undo affordance. The `reverted` column is part of
    the ledger migration; if an older DB predates it we degrade to 0 rather than
    raising. Kept separate from get_recent_actions() (text, used by prompts)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute(
            "SELECT id, timestamp, tool_name, success, reverted, inverse_tool "
            "FROM actions_performed ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = c.fetchall()
    except Exception:
        # Older schema without the reverted/inverse_tool columns — degrade.
        c.execute(
            "SELECT id, timestamp, tool_name, success "
            "FROM actions_performed ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = [(r[0], r[1], r[2], r[3], 0, None) for r in c.fetchall()]
    conn.close()
    return [
        {
            "id": rid,
            "ts": ts,
            "tool": tool,
            "success": bool(success),
            "reverted": bool(reverted),
            # The UI should only offer Undo when there's a real inverse and the
            # action succeeded and hasn't already been reverted.
            "reversible": bool(inverse_tool) and bool(success) and not bool(reverted),
        }
        for rid, ts, tool, success, reverted, inverse_tool in rows
    ]


# ── Scheduled Tasks ────────────────────────────────────────────────────────────

def add_scheduled_task(name: str, description: str, schedule: str) -> str:
    """
    Register a recurring task JARVIS should run on a schedule.
    schedule format: "daily@HH:MM" | "every_Nh" | "weekly@dayname@HH:MM"
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT OR REPLACE INTO scheduled_tasks (name, description, schedule, active, created_at) VALUES (?, ?, ?, 1, ?)",
            (name, description, schedule, datetime.now().isoformat())
        )
        conn.commit()
        result = f"Scheduled task '{name}' registered: {schedule}"
    except Exception as e:
        result = f"Failed to save task: {e}"
    conn.close()
    return result


def get_scheduled_tasks(active_only: bool = True) -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if active_only:
        c.execute("SELECT id, name, description, schedule, last_run FROM scheduled_tasks WHERE active=1")
    else:
        c.execute("SELECT id, name, description, schedule, last_run FROM scheduled_tasks")
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "description": r[2], "schedule": r[3], "last_run": r[4]} for r in rows]


def update_task_last_run(task_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE scheduled_tasks SET last_run=? WHERE id=?",
              (datetime.now().isoformat(), task_id))
    conn.commit()
    conn.close()


def disable_scheduled_task(name: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE scheduled_tasks SET active=0 WHERE name=?", (name,))
    conn.commit()
    conn.close()


# ── Prompt Building ────────────────────────────────────────────────────────────

def format_history_for_prompt(limit: int = 30) -> str:
    history = get_recent_history(limit)
    if not history:
        return ""
    lines = []
    for role, content in history:
        label = "ELNATAN" if role == "user" else role.upper()
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


def build_messages_for_prompt(current_input: str, limit: int = 30, include_topic: bool = False) -> list:
    """
    Return multi-turn messages list for API calls.
    Maps all agent roles to 'assistant'. Merges consecutive same-role turns.
    Topic inference removed — eliminated per-prompt Haiku API call.
    """
    history = get_recent_history(limit)
    msgs = []

    for role, content in history:
        api_role = "user" if role == "user" else "assistant"
        if msgs and msgs[-1]["role"] == api_role:
            msgs[-1]["content"] += "\n" + content
        else:
            msgs.append({"role": api_role, "content": content})

    # Must start with user
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)

    # Add current input if not already last user message
    if not msgs or msgs[-1]["role"] != "user":
        msgs.append({"role": "user", "content": current_input})

    return msgs or [{"role": "user", "content": current_input}]


init_db()
