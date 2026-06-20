"""Goal tools — let Alfred ACT on sir's goals when he approves an offer (closes the
proactive loop). work_on_goal kicks off the autonomous runner in the BACKGROUND
(act-then-tell): every action the runner takes still routes through the safety gate
(source='autonomous' → red-list always confirms), and it reports back via the digest.
"""
import threading

from brain.tools.registry import tool


@tool(
    description=(
        "Start working on one of sir's goals or a task in the background — research, draft, "
        "and stage progress, then report. Use when sir APPROVES an offer like 'shall I move "
        "<goal> forward?' or says 'work on <goal>'. Returns immediately; the work runs "
        "autonomously behind the safety gate (anything irreversible still needs his approval)."
    ),
    parameters={
        "goal": {"type": "string", "description": "The goal or task to advance, e.g. 'Launch my marketplace'."},
    },
    risk="low",
    allowed_agents=["JARVIS"],
)
def work_on_goal(goal) -> str:
    g = str(goal or "").strip()
    if not g:
        return "Which goal shall I work on, sir?"

    def _run():
        try:
            from brain.runner import run_goal
            run_goal(
                f"Make concrete progress on: {g}. Research, draft, and stage what you can; "
                f"leave anything irreversible for sir's approval.",
                label=f"goal:{g}",
            )
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()
    return f"On it, sir — I'm working on “{g}” now. I'll report back with what I've staged."
