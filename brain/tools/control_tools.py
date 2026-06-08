"""Safety-control tools — let JARVIS (and the user, by voice/chat) drive the
safety state: undo an action, pause/resume the autonomy kill-switch, toggle
away-mode, and report current safety status.

These are *controls over* the safety substrate, so they are themselves low-risk
(reversible, no side effects beyond flipping a flag) and JARVIS-only. Imports of
the autonomy/memory layers are done inside each function to avoid any circular
import at package-load time (this module is imported from brain/tools/__init__).
"""
from brain.tools.registry import tool

_AGENTS = ["JARVIS"]

# Values that count as "turn it on" for away-mode.
_TRUTHY = {"1", "true", "t", "yes", "y", "on", "enable", "enabled", "away"}


def _truthy(value) -> bool:
    """Parse a loose on/off value (str/bool/int) into a bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if value is None:
        return False
    return str(value).strip().lower() in _TRUTHY


@tool(
    description=(
        "Undo a previously performed action by its action id. Executes the "
        "recorded inverse and reports the result. Use when the user says "
        "'undo that' or 'revert that action'."
    ),
    parameters={
        "action_id": {
            "type": "string",
            "description": "The numeric id of the action to undo, e.g. '42'.",
        },
    },
    risk="low",
    allowed_agents=_AGENTS,
)
def tool_undo(action_id) -> str:
    from memory import memory
    try:
        aid = int(action_id)
    except (TypeError, ValueError):
        return f"Can't undo: '{action_id}' isn't a valid action id."
    return memory.revert_action(aid)


@tool(
    description=(
        "Pause JARVIS — engage the kill-switch so no autonomous actions fire "
        "until resumed. Use when the user says 'pause', 'stop', or 'hold off'."
    ),
    parameters={},
    risk="low",
    allowed_agents=_AGENTS,
)
def tool_pause() -> str:
    from brain import autonomy
    autonomy.set_paused(True)
    return "Paused — autonomous actions halted."


@tool(
    description=(
        "Resume JARVIS — release the kill-switch so autonomous actions may "
        "fire again. Use when the user says 'resume', 'go ahead', or 'unpause'."
    ),
    parameters={},
    risk="low",
    allowed_agents=_AGENTS,
)
def tool_resume() -> str:
    from brain import autonomy
    autonomy.set_paused(False)
    return "Resumed."


@tool(
    description=(
        "Turn away-mode on or off. In away-mode, irreversible / high-stakes "
        "actions require the user's explicit confirmation. Pass 'on' or 'off'."
    ),
    parameters={
        "on": {
            "type": "string",
            "description": "Whether away-mode should be on: 'on'/'off' (also accepts true/false, yes/no, 1/0).",
        },
    },
    risk="low",
    allowed_agents=_AGENTS,
)
def tool_set_away(on) -> str:
    from brain import autonomy
    value = _truthy(on)
    autonomy.set_away(value)
    return "Away-mode is ON." if value else "Away-mode is OFF."


@tool(
    description=(
        "Report the current safety status: whether JARVIS is paused, whether "
        "away-mode is on, and any actions waiting for the user's approval."
    ),
    parameters={},
    risk="low",
    allowed_agents=_AGENTS,
)
def tool_safety_status() -> str:
    from brain import autonomy
    paused = "yes" if autonomy.is_paused() else "no"
    away = "yes" if autonomy.is_away() else "no"
    return (
        f"Safety status — paused: {paused}, away-mode: {away}.\n"
        f"{autonomy.pending_summary()}"
    )
