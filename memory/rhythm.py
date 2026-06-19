"""memory/rhythm.py — Alfred's LEARNED rhythm + quiet-hours damping (plan §7).

No hardcoded hours: the quiet window is INFERRED from when sir is actually inactive
(the 8-hour stretch with the least logged activity), continuously, and stored locally.
"Never fully silent" is the rule — in a quiet window routine proactivity is held for the
next active window, but URGENT items (a failure, a hard-stop, anything surface-level)
always break through.
"""
import sqlite3
from datetime import datetime

_DEFAULT_QUIET = (23, 7)   # fallback until enough activity is learned
_MIN_SAMPLES = 50


def _flag_get(key, default=None):
    try:
        from memory import memory as _m
        return _m.get_flag(key, default)
    except Exception:
        return default


def _flag_set(key, val):
    try:
        from memory import memory as _m
        _m.set_flag(key, val)
    except Exception:
        pass


def _hour_of(ts) -> int:
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "")).hour
    except Exception:
        return None


def _table_exists(conn, name) -> bool:
    try:
        return bool(conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())
    except Exception:
        return False


def learn_rhythm() -> tuple:
    """Infer (quiet_start_hour, quiet_end_hour) from activity timestamps; persist it.
    The 8-hour contiguous window with the LEAST activity is taken as quiet hours."""
    from memory import memory as _m
    rows = []
    try:
        c = sqlite3.connect(_m.DB_PATH)
    except Exception:
        return quiet_window()
    # Gather timestamps defensively — a missing table/column must not abort learning.
    for table, cols in (("actions_performed", ["timestamp"]),
                        ("conversations", ["created_at", "timestamp", "ts"])):
        if not _table_exists(c, table):
            continue
        for col in cols:
            try:
                rows += c.execute(f"SELECT {col} FROM {table}").fetchall()
                break   # got a usable column for this table
            except Exception:
                continue
    c.close()

    hours = [0] * 24
    for (ts,) in rows:
        h = _hour_of(ts)
        if h is not None:
            hours[h] += 1
    if sum(hours) < _MIN_SAMPLES:
        return quiet_window()   # not enough to learn — keep current/default

    best_start, best_sum = 0, None
    for start in range(24):
        s = sum(hours[(start + i) % 24] for i in range(8))
        if best_sum is None or s < best_sum:
            best_sum, best_start = s, start
    win = (best_start, (best_start + 8) % 24)
    _flag_set("quiet_window", f"{win[0]},{win[1]}")
    return win


def quiet_window() -> tuple:
    raw = _flag_get("quiet_window")
    if raw:
        try:
            a, b = str(raw).split(",")
            return (int(a), int(b))
        except Exception:
            pass
    return _DEFAULT_QUIET


def is_quiet_now(now=None) -> bool:
    h = (now or datetime.now()).hour
    s, e = quiet_window()
    return (s <= h < e) if s < e else (h >= s or h < e)   # handle midnight wrap


def should_surface(item, now=None) -> bool:
    """Never fully silent: urgent items (kind 'alert' or surface visibility) always pass;
    routine proactivity is held during a learned-quiet window."""
    if not is_quiet_now(now):
        return True
    if not isinstance(item, dict):
        return True
    return item.get("kind") == "alert" or item.get("visibility") == "surface"
