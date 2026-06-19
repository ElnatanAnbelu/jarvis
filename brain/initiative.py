"""brain/initiative.py — Alfred's proactive brain (plan §1: trigger → plan → present).

GOAL-DRIVEN. On each pass it runs cheap, LOCAL, model-free triggers (no model call to
decide WHETHER to act — the latency contract, plan §8), collects the salient ones, and
SURFACES them as structured items through the proactive queue: goal-focus offers, open
tasks, and an honesty alert when a past action failed.

Safety: this only SURFACES (notifications/offers). It never acts on its own — any action
a proposal would take still routes through brain/autonomy.gate() as source="autonomous",
where the red-list always confirms. v1 proposes; it does not auto-execute.
"""
import sqlite3
from datetime import datetime, timedelta


def _jarvis_conn():
    from memory import memory as _m
    return sqlite3.connect(_m.DB_PATH)


def _obs_conn():
    import os
    from memory import memory as _m
    p = os.path.join(os.path.dirname(_m.DB_PATH), "observations.db")
    return sqlite3.connect(p)


# ── Triggers — each returns a list of items (dicts); pure, no model, no side effects ──

def _trigger_active_goals() -> list:
    """The heart: surface sir's active goals as 'shall I move this forward?' offers."""
    out = []
    try:
        c = _jarvis_conn()
        goals = c.execute(
            "SELECT id, title, category, deadline FROM goals WHERE status='active' ORDER BY id LIMIT 8"
        ).fetchall()
        c.close()
    except Exception:
        return out
    for gid, title, cat, deadline in goals:
        due = f" Due {deadline}." if deadline else ""
        out.append({
            "kind": "plan", "source": "initiative", "key": f"goal:{gid}",
            "title": f"Goal: {title}",
            "text": f"Your goal — “{title}” — is still open, sir.{due} "
                    f"Shall I move it forward?",
            "visibility": "normal",
        })
    return out


def _trigger_open_tasks() -> list:
    """Open tasks (done=0) — surfaced as one actionable offer."""
    try:
        c = _jarvis_conn()
        tasks = c.execute(
            "SELECT title FROM tasks WHERE done=0 ORDER BY id DESC LIMIT 6"
        ).fetchall()
        c.close()
    except Exception:
        return []
    titles = [t[0] for t in tasks if t and t[0]]
    if not titles:
        return []
    listed = "; ".join(titles[:4])
    more = f" (+{len(titles)-4} more)" if len(titles) > 4 else ""
    return [{
        "kind": "plan", "source": "initiative", "key": "tasks:open",
        "title": f"{len(titles)} open tasks",
        "text": f"{len(titles)} things are still on your plate, sir: {listed}{more}. "
                f"Shall I take any of them?",
        "visibility": "normal",
    }]


def _trigger_caught_mistake() -> list:
    """Honesty layer (plan §4): a recent action that failed and wasn't reverted."""
    try:
        c = _jarvis_conn()
        cutoff = (datetime.now() - timedelta(days=2)).isoformat()
        rows = c.execute(
            "SELECT tool_name, result, timestamp FROM actions_performed "
            "WHERE success=0 AND reverted=0 AND timestamp > ? ORDER BY id DESC LIMIT 3",
            (cutoff,),
        ).fetchall()
        c.close()
    except Exception:
        return []
    out = []
    for tool, result, ts in rows:
        if not tool or tool.startswith("_") or "probe" in tool.lower() or "test" in tool.lower():
            continue   # internal / test tools — never cry wolf to sir over a probe
        out.append({
            "kind": "alert", "source": "initiative", "key": f"fail:{tool}:{ts}",
            "title": "An action failed",
            "text": f"I must flag something, sir: “{tool}” didn't succeed "
                    f"({str(result)[:80]}). I haven't hidden it — want me to retry or undo?",
            "visibility": "surface",
        })
    return out


def _trigger_morning() -> list:
    """Morning prep (plan §1.2) — fired ONCE at sir's learned wake hour (end of quiet)."""
    try:
        from memory import rhythm
        wake = rhythm.quiet_window()[1]   # the hour his quiet window ends = wake hour
        if datetime.now().hour != wake:
            return []
        from brain import morning
        card = morning.build_morning_prep()
        return [card] if card else []
    except Exception:
        return []


_TRIGGERS = (_trigger_morning, _trigger_active_goals, _trigger_open_tasks, _trigger_caught_mistake)


def scan() -> list:
    """Run all triggers; return the surfaced items. Pure (no side effects, no model)."""
    items = []
    for trig in _TRIGGERS:
        try:
            items.extend(trig() or [])
        except Exception:
            pass
    # surface-visibility (failures) first
    items.sort(key=lambda it: 0 if it.get("visibility") == "surface" else 1)
    return items


_seen = set()  # per-process dedup so Alfred doesn't repeat the same nudge each tick


def run_once(push_fn, repeat=False) -> int:
    """Scan and push new items via push_fn(item). Dedupes by item key unless repeat=True,
    and honors the learned quiet-hours: routine items are HELD in a quiet window (not
    marked seen, so they resurface when sir is active), but urgent ones always break
    through (never fully silent). Returns the number pushed."""
    try:
        from memory import rhythm
    except Exception:
        rhythm = None
    n = 0
    for it in scan():
        key = it.get("key")
        if not repeat and key in _seen:
            continue
        if rhythm is not None and not rhythm.should_surface(it):
            continue   # held by quiet-hours — NOT marked seen, so it returns when active
        _seen.add(key)
        try:
            push_fn(it)
            n += 1
        except Exception:
            pass
    return n


def run_loop(push_fn, interval: float = 1200.0):
    """Daemon: surface proactive items every `interval` seconds. Wire from the server.
    Re-learns sir's quiet-hours each pass so damping adapts to his actual rhythm."""
    import time
    print(f"[Initiative] proactive engine armed (every {int(interval)}s).", flush=True)
    while True:
        try:
            from memory import rhythm
            rhythm.learn_rhythm()
        except Exception:
            pass
        try:
            run_once(push_fn)
        except Exception:
            pass
        # knows-me synthesis (plan §6): surface one learned theme per pass, quiet-aware.
        try:
            from brain import synthesis
            from memory import rhythm
            item = synthesis.synthesize_one()
            if item and rhythm.should_surface(item):
                push_fn(item)
        except Exception:
            pass
        time.sleep(interval)
