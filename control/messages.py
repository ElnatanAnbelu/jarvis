import subprocess
import re
import json
import sqlite3
from pathlib import Path

CONTACTS_FILE = Path(__file__).parent.parent / "contacts.json"
CHATDB_PATH = Path.home() / "Library" / "Messages" / "chat.db"


def _osa_str(s) -> str:
    """Escape an arbitrary value for safe embedding inside an AppleScript
    double-quoted string literal.

    Without this, a value like `a@b" \\n do shell script "rm -rf ~" \\n "` would
    close the literal and inject a `do shell script` line — an AppleScript→shell
    RCE. We escape backslashes and quotes and strip newlines/control chars
    (an AppleScript string literal can't span lines, so a raw newline is itself
    a breakout primitive)."""
    s = str(s)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\r", " ").replace("\n", " ")
    return "".join(ch for ch in s if ch >= " " or ch == "\t")


def _load_contacts() -> dict:
    try:
        data = json.loads(CONTACTS_FILE.read_text())
        return {k.lower(): v for k, v in data.items() if v}
    except Exception:
        return {}


def _resolve_contact(name: str) -> str:
    """Check contacts.json first (exact then fuzzy), then fall back to Contacts app."""
    book = _load_contacts()
    needle = name.lower().strip()

    # Exact match
    if needle in book:
        return book[needle]

    # Fuzzy: contact name starts with or contains the search term
    for contact_name, phone in book.items():
        if contact_name.startswith(needle) or needle in contact_name:
            return phone

    # Fall back to macOS Contacts app
    script = f'''
    tell application "Contacts"
        launch
        set matches to (every person whose name contains "{_osa_str(name)}")
        if (count of matches) = 0 then return ""
        set p to item 1 of matches
        set allPhones to phones of p
        repeat with ph in allPhones
            if label of ph is "mobile" or label of ph is "iPhone" then
                return value of ph
            end if
        end repeat
        if (count of allPhones) > 0 then return value of item 1 of allPhones
        set allEmails to emails of p
        if (count of allEmails) > 0 then return value of item 1 of allEmails
        return ""
    end tell
    '''
    result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    return result.stdout.strip()


_PHONE_RE = re.compile(r'^[\d\+\-\(\)\s]{7,}$')
# A real email: exactly one @, no quotes/whitespace/control chars that could be
# used to break out of the AppleScript literal. NOT "any string containing @".
_EMAIL_RE = re.compile(r'^[^@\s"\'\\]+@[^@\s"\'\\]+\.[^@\s"\'\\]+$')


def _looks_like_handle(s: str) -> bool:
    s = (s or "").strip()
    return bool(_PHONE_RE.match(s) or _EMAIL_RE.match(s))


def send_imessage(contact: str, message: str) -> str:
    handle = contact.strip()

    if not _looks_like_handle(handle):
        resolved = _resolve_contact(handle)
        if not resolved:
            return f"Could not find '{contact}'. Add their number to contacts.json in the JARVIS folder."
        handle = resolved

    script = f'''
    tell application "Messages"
        set targetService to 1st service whose service type = iMessage
        set targetBuddy to buddy "{_osa_str(handle)}" of targetService
        send "{_osa_str(message)}" to targetBuddy
    end tell
    '''
    result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    if result.returncode == 0:
        label = f"{contact} ({handle})" if handle != contact else contact
        return f"Message sent to {label}."
    return f"Could not send message: {result.stderr.strip()}"


def read_imessages(contact: str = None, count: int = 5) -> str:
    try:
        count = max(1, min(int(count), 200))  # coerce: it is interpolated into the script
    except (TypeError, ValueError):
        count = 5
    if contact:
        handle = contact.strip()
        if not _looks_like_handle(handle):
            resolved = _resolve_contact(handle)
            if resolved:
                handle = resolved
        script = f'''
        tell application "Messages"
            set output to ""
            repeat with c in chats
                repeat with p in participants of c
                    if handle of p = "{_osa_str(handle)}" then
                        set msgs to messages of c
                        set n to count of msgs
                        if n > {count} then set msgs to items (n - {count} + 1) thru n of msgs
                        repeat with m in msgs
                            set output to output & (text of m) & "\\n"
                        end repeat
                    end if
                end repeat
            end repeat
            return output
        end tell
        '''
    else:
        script = f'''
        tell application "Messages"
            set output to ""
            set n to 0
            repeat with c in chats
                if n >= {count} then exit repeat
                try
                    set output to output & (name of c) & ": " & (text of last message of c) & "\\n"
                    set n to n + 1
                end try
            end repeat
            return output
        end tell
        '''
    result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    return result.stdout.strip() or "No messages found."


# --- Read-only iMessage reader (local chat.db) -----------------------------
#
# Reads recent INCOMING+outgoing iMessages straight from the on-device Messages
# database (~/Library/Messages/chat.db) in READ-ONLY mode (sqlite ?mode=ro), the
# same store imessage_channel.py polls. This is read-only: Alfred never writes
# chat.db and this never auto-replies to anyone.
#
# Full Disk Access: macOS guards chat.db behind FDA. If the running process
# (Terminal / the app) hasn't been granted it, sqlite raises "authorization
# denied" / "unable to open database". We catch that and return a clear,
# actionable message instead of crashing.

_FDA_HINT = (
    "Can't read iMessages — macOS Full Disk Access isn't granted to this app. "
    "Grant it under System Settings → Privacy & Security → Full Disk Access "
    "(add Terminal and/or the Alfred app), then try again."
)


def _decode_attributed_body(blob) -> str:
    """macOS sometimes stores the message body in the `attributedBody` BLOB (a
    binary archive) with a NULL `text` column. We don't unarchive the full plist;
    we extract the human-readable run of text it always contains. Best-effort —
    returns "" if nothing legible is found. Never raises."""
    if not blob:
        return ""
    try:
        raw = bytes(blob)
    except Exception:
        return ""
    try:
        # The body text in NSAttributedString archives sits right after the
        # "NSString" marker, length-prefixed. Pull the printable run.
        marker = raw.find(b"NSString")
        if marker == -1:
            return ""
        segment = raw[marker + 8:]
        # Skip class/structural bytes, then take the longest printable ASCII/UTF-8
        # run, which is the visible message.
        text = segment.decode("utf-8", errors="ignore")
        # Strip leading control/length bytes and trailing archive markers.
        m = re.search(r"[ -~ -￿]{2,}", text)
        if not m:
            return ""
        body = m.group(0)
        # Cut at the next archive keyword if present.
        for kw in ("iI", "NSDictionary", "NSAttributeInfo", "__kIM", "NSNumber", "NSValue"):
            idx = body.find(kw)
            if idx > 0:
                body = body[:idx]
        return body.strip()
    except Exception:
        return ""


def _read_chatdb_recent(db_path, count: int, contact: str = None) -> str:
    """Read recent messages from chat.db, newest threads first, latest `count`
    messages per thread. Pure + testable (takes a db_path). Returns a formatted
    string, or a clear message on permission failure / no data."""
    def _is_fda(err) -> bool:
        m = str(err).lower()
        return "authorization denied" in m or "unable to open database" in m

    uri = f"file:{db_path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=5)
        # Force the actual open/authorization to happen now (sqlite is lazy);
        # FDA denial surfaces here as sqlite3.DatabaseError "authorization denied".
        conn.execute("SELECT 1")
    except sqlite3.Error as e:
        if _is_fda(e):
            return _FDA_HINT
        return f"Could not open Messages database (read-only): {e}"
    except Exception as e:
        return f"Could not open Messages database: {e}"

    try:
        # Detect optional columns so this also works against the minimal test
        # schema (which only has ROWID/text/handle_id/is_from_me).
        cols = {row[1] for row in conn.execute("PRAGMA table_info(message)")}
        has_date = "date" in cols
        has_attr = "attributedBody" in cols

        select_cols = ["m.ROWID", "h.id", "m.text", "m.is_from_me"]
        select_cols.append("m.date" if has_date else "0")
        select_cols.append("m.attributedBody" if has_attr else "NULL")
        order = "m.date DESC, m.ROWID DESC" if has_date else "m.ROWID DESC"

        where = []
        params = []
        if contact:
            handle = contact.strip()
            if not _looks_like_handle(handle):
                resolved = _resolve_contact(handle)
                if resolved:
                    handle = resolved
            where.append("h.id = ?")
            params.append(handle)

        # Pull a generous window (count threads * count msgs, capped) then group
        # in Python — chat.db has no cheap per-thread limit in plain SQL.
        window = max(count * 12, 60)
        sql = (
            f"SELECT {', '.join(select_cols)} "
            "FROM message m JOIN handle h ON m.handle_id = h.ROWID "
            + ("WHERE " + " AND ".join(where) + " " if where else "")
            + f"ORDER BY {order} LIMIT ?"
        )
        rows = conn.execute(sql, (*params, window)).fetchall()
    except sqlite3.Error as e:
        if _is_fda(e):
            return _FDA_HINT
        return f"Could not read Messages database: {e}"
    except Exception as e:
        return f"Could not read Messages database: {e}"
    finally:
        conn.close()

    if not rows:
        return "No recent iMessages found."

    # Group by handle (thread), keeping newest-first order; latest `count` per thread.
    threads = {}
    order_seen = []
    for rowid, handle, text, is_from_me, _date, attr in rows:
        body = (text or "").strip() or _decode_attributed_body(attr)
        if not body:
            continue
        if handle not in threads:
            threads[handle] = []
            order_seen.append(handle)
        if len(threads[handle]) < count:
            who = "Me" if is_from_me else (handle or "Unknown")
            threads[handle].append(f"{who}: {body}")

    if not threads:
        return "No recent iMessages found."

    blocks = []
    for handle in order_seen:
        msgs = threads[handle]
        if not msgs:
            continue
        # Oldest→newest within a thread reads naturally.
        blocks.append(f"[{handle}]\n" + "\n".join(reversed(msgs)))
    return "\n\n---\n\n".join(blocks) if blocks else "No recent iMessages found."


def read_recent_imessages(contact: str = None, count: int = 5, db_path=None) -> str:
    """Read recent iMessages read-only from the local Messages database.

    contact: optional handle/name to filter to one conversation; None = recent
             threads. count: latest N messages per thread (1–50).
    Degrades gracefully if Full Disk Access isn't granted (clear message, no crash).
    Never sends or auto-replies."""
    try:
        count = max(1, min(int(count), 50))
    except (TypeError, ValueError):
        count = 5
    db_path = db_path or CHATDB_PATH
    if not Path(db_path).exists():
        return ("No Messages database found on this Mac "
                f"({db_path}). iMessage may not be set up here.")
    return _read_chatdb_recent(str(db_path), count, contact)


# --- Read-only WhatsApp reader ---------------------------------------------

def read_whatsapp_recent(contact: str = None, count: int = 5) -> str:
    """Read recent WhatsApp messages via the local token-protected Node bridge.

    Graceful: if WHATSAPP_TOKEN/bridge isn't configured or reachable, returns a
    clear "not connected" message — never fake data, never a crash. Never sends."""
    import os
    # Load .env the same way the WhatsApp sender does, so the token is visible.
    try:
        from control.whatsapp import _load_env, WHATSAPP_BASE_URL
        _load_env()
    except Exception:
        WHATSAPP_BASE_URL = os.environ.get("WHATSAPP_BASE_URL", "http://127.0.0.1:3001")

    token = os.environ.get("WHATSAPP_TOKEN")
    if not token:
        return ("WhatsApp not connected — needs WHATSAPP_TOKEN. "
                "Set it in .env and start the local WhatsApp bridge to read messages.")
    try:
        count = max(1, min(int(count), 50))
    except (TypeError, ValueError):
        count = 5
    try:
        import requests
    except Exception:
        return "WhatsApp not connected — the `requests` library is unavailable to reach the bridge."

    params = {"count": count}
    if contact:
        params["contact"] = contact
    try:
        r = requests.get(
            f"{WHATSAPP_BASE_URL}/messages",
            params=params,
            headers={"x-whatsapp-token": token},
            timeout=15,
        )
    except Exception as e:
        return ("WhatsApp not connected — couldn't reach the local bridge "
                f"({WHATSAPP_BASE_URL}). Start the WhatsApp service. ({e})")

    if r.status_code == 404:
        return ("WhatsApp bridge is running but doesn't expose a read endpoint yet "
                "(no /messages route). Reading isn't available until the bridge supports it.")
    if r.status_code == 401 or r.status_code == 403:
        return "WhatsApp bridge rejected the token — check WHATSAPP_TOKEN in .env."

    try:
        data = r.json()
    except Exception:
        return "WhatsApp not connected — the bridge returned an unexpected response."

    if not data.get("ok"):
        return f"WhatsApp read error: {data.get('error', 'unknown error')}"

    msgs = data.get("messages", [])
    if not msgs:
        return "No recent WhatsApp messages."
    lines = []
    for m in msgs[:count * 12]:
        who = m.get("from") or m.get("sender") or ("Me" if m.get("fromMe") else "Unknown")
        body = (m.get("body") or m.get("text") or "").strip()
        if body:
            lines.append(f"{who}: {body}")
    return "\n".join(lines) if lines else "No recent WhatsApp messages."
