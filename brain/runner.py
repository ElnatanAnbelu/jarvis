"""Goal-driven autonomous runner — JARVIS acting on its own.

Everything here runs through the single-JARVIS agent loop with source="autonomous",
so the safety gate governs it: the kill-switch (paused) halts it, supervised mode
proposes every action for approval, and red-list actions always confirm. This is
what the proactive scheduler and away-mode loop call instead of plain think().
"""
from brain import agent, autonomy


def build_digest(limit: int = 15) -> str:
    """A 'here's what I handled while you were away' summary from the action ledger."""
    try:
        from memory.memory import get_recent_actions
        acts = get_recent_actions(limit)
    except Exception:
        acts = ""
    if not acts:
        return "Nothing to report, sir — no autonomous actions logged."
    return "Here's what I handled, sir:\n" + acts


def run_goal(goal: str, label: str = "") -> str:
    """Execute one autonomous goal end-to-end (planning + gated tool use)."""
    try:
        from obs.log import new_correlation, log_event
        new_correlation()
        log_event("autonomous.start", goal=goal[:200], label=label,
                  mode=autonomy.get_autonomy_mode(), paused=autonomy.is_paused())
    except Exception:
        pass

    if autonomy.is_paused():
        return "Paused — autonomous run skipped (kill-switch active)."

    # Checkpoint the ledger so this whole job is undoable after the report
    # ("undo everything Alfred just did") via memory.revert_since(checkpoint).
    from memory import memory as _mem
    checkpoint = _mem.max_action_id()
    _mem.set_flag("last_job_checkpoint", checkpoint)

    try:
        result = agent.run(goal, agent="JARVIS", source="autonomous")
        try:
            from obs.log import log_event
            log_event("autonomous.done", label=label, chars=len(result or ""))
        except Exception:
            pass
        return result
    except Exception as e:
        try:
            from obs.log import log_exception
            log_exception("autonomous.failed", label=label)
        except Exception:
            pass
        return f"Autonomous task failed: {e}"
