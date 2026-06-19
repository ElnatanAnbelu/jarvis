"""P6 — iMessage as Alfred's PRIMARY remote surface (Telegram demoted to fail-safe).

The owner texts Alfred from his phone; Alfred reads new owner messages from the
local Messages database (``~/Library/Messages/chat.db``, read-only), runs the SAME
owner-command set as the Telegram channel (approve/reject/pause/…), and replies via
iMessage. Everything stays on-device.

SAFETY (mirrors telegram_bot.py exactly — this is a command-executing surface):
  * OWNER-HANDLE ALLOWLIST. Only messages whose sender handle is in
    ALFRED_IMESSAGE_OWNER act on anything. No owner configured → the channel is
    DISABLED (no polling, no actions). This is the spoofing guard.
  * source="external". Free-text (non-command) messages route to the brain tagged
    external, so the gate treats them as untrusted — red-list ALWAYS confirms, and
    injected instructions in a message body can't fire an unconfirmed action.
  * READ-ONLY db access (sqlite uri ?mode=ro) — Alfred never writes chat.db.
  * Off by default; nothing runs until the owner handle is set AND run_loop() is
    started (wired from the app, not import-time).

Note: macOS stores some message bodies in ``attributedBody`` (a binary plist) with
a NULL ``text`` column. This reads the ``text`` column (populated for the typed
messages owner commands arrive as); attributedBody decoding is a follow-up.
"""
import os
import re
import sqlite3
from pathlib import Path

DEFAULT_DB = Path.home() / "Library" / "Messages" / "chat.db"
_ROWID_FLAG = "imessage_last_rowid"


def _norm_handle(h: str) -> str:
    """Normalize a handle for comparison: emails lowercased; phone numbers reduced
    to their digits (so '+1 (415) 555-1212' == '14155551212')."""
    h = (h or "").strip()
    if "@" in h:
        return h.lower()
    digits = re.sub(r"\D", "", h)
    return digits.lstrip("0") or digits


def owner_handles() -> set:
    """The owner's allowed iMessage handles (phone/email), normalized. Empty = channel off."""
    raw = os.environ.get("ALFRED_IMESSAGE_OWNER", "")
    return {_norm_handle(h) for h in raw.split(",") if h.strip()}


def enabled() -> bool:
    return bool(owner_handles())


def _fetch_new(db_path, owners: set, since_rowid: int):
    """Return [(rowid, handle, text)] for incoming (is_from_me=0) messages newer than
    since_rowid whose sender is an owner handle. Pure + testable (takes a db_path)."""
    if not owners:
        return []
    uri = f"file:{db_path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=5)
    except Exception:
        return []
    try:
        rows = conn.execute(
            "SELECT m.ROWID, h.id, m.text "
            "FROM message m JOIN handle h ON m.handle_id = h.ROWID "
            "WHERE m.is_from_me = 0 AND m.ROWID > ? AND m.text IS NOT NULL "
            "ORDER BY m.ROWID ASC",
            (int(since_rowid),),
        ).fetchall()
    except Exception:
        return []
    finally:
        conn.close()
    out = []
    for rowid, handle, text in rows:
        if _norm_handle(handle) in owners:
            out.append((rowid, handle, (text or "").strip()))
    return out


def handle_text(handle: str, text: str) -> str:
    """Process one owner message → reply text. Owner-gated by the caller.

    Control commands (approve/reject/pause/…) run through the SAME handler the
    Telegram channel uses. Anything else routes to the brain tagged source=external
    (so the gate confirms red-list / treats it as untrusted)."""
    from telegram_bot import parse_owner_command, _handle_owner_command

    parsed = parse_owner_command(text)
    if parsed is not None:
        cmd, arg = parsed
        return _handle_owner_command(cmd, arg)
    # Not a control command — it's a request. Route through the brain as EXTERNAL.
    from brain.router import route
    response, _model = route(text, source="external")
    return response or ""


def send(text: str, to_handle: str) -> str:
    """Send an iMessage reply via the injection-safe sender."""
    from control.messages import send_imessage
    return send_imessage(to_handle, text)


def poll_once(db_path=None) -> int:
    """Process any new owner messages once; reply to each. Returns count handled.
    No-op when the channel is disabled. Persists the high-water ROWID."""
    owners = owner_handles()
    if not owners:
        return 0
    from memory import memory
    db_path = db_path or DEFAULT_DB
    if not Path(db_path).exists():
        return 0
    try:
        since = int(memory.get_flag(_ROWID_FLAG, 0) or 0)
    except (TypeError, ValueError):
        since = 0
    new = _fetch_new(db_path, owners, since)
    handled = 0
    for rowid, handle, text in new:
        if text:
            try:
                reply = handle_text(handle, text)
                if reply:
                    send(reply, handle)
                handled += 1
            except Exception:
                pass
        memory.set_flag(_ROWID_FLAG, rowid)  # advance even on empty/failed so we don't loop
    return handled


def run_loop(interval: float = 6.0, db_path=None):
    """Daemon poll loop. Off unless an owner handle is configured. Wire from the app."""
    import time
    if not enabled():
        print("[iMessage] disabled — set ALFRED_IMESSAGE_OWNER to enable.", flush=True)
        return
    print(f"[iMessage] primary away-channel armed for {len(owner_handles())} owner handle(s).", flush=True)
    while True:
        try:
            poll_once(db_path)
        except Exception:
            pass
        time.sleep(interval)
