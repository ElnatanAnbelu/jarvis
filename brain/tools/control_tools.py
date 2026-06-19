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
        "Undo the entire last autonomous job — reverts every reversible action "
        "Alfred performed since that job's checkpoint. Use when the user says "
        "'undo that whole job' / 'undo everything you just did'."
    ),
    parameters={},
    risk="low",
    allowed_agents=_AGENTS,
)
def tool_undo_last_job() -> str:
    from memory import memory
    cp = memory.get_flag("last_job_checkpoint", None)
    if cp is None:
        return "No autonomous job checkpoint on record yet."
    try:
        cp = int(cp)
    except (TypeError, ValueError):
        return "The last-job checkpoint is unreadable."
    return f"Undoing the last job (since #{cp}): {memory.revert_since(cp)}"


@tool(
    description=(
        "Set a domain's autonomy mode — 'auto' (Alfred acts on its own in that "
        "domain) or 'supervised' (it proposes, you approve). Domains: comms, money, "
        "system, files, code, web, calendar, business, school, personal, general. "
        "Red-list and money >= $100 still always confirm regardless. Use when the "
        "user says e.g. 'let comms run on auto' or 'put money back on supervised'."
    ),
    parameters={
        "domain": {"type": "string", "description": "The domain, e.g. 'comms', 'money', 'system'."},
        "mode": {"type": "string", "description": "'auto' or 'supervised'."},
    },
    risk="low",
    allowed_agents=_AGENTS,
)
def tool_set_domain_mode(domain, mode) -> str:
    from brain import autonomy
    dom = str(domain).strip().lower()
    want = "auto" if str(mode).strip().lower() == "auto" else "supervised"
    autonomy.set_domain_mode(dom, want)
    return f"Domain '{dom}' is now {want}, sir."


@tool(
    description="List each domain's current autonomy mode (auto vs supervised) + the global default.",
    parameters={},
    risk="low",
    allowed_agents=_AGENTS,
)
def tool_list_domain_modes() -> str:
    from brain import autonomy
    modes = autonomy._load_domain_modes()
    glob = autonomy.get_autonomy_mode()
    if not modes:
        return f"All domains follow the global mode: {glob}."
    lines = "\n".join(f"  {d}: {m}" for d, m in sorted(modes.items()))
    return f"Global default: {glob}\nPer-domain overrides:\n{lines}"


@tool(
    description=(
        "Report the current safety status: whether JARVIS is paused, whether "
        "away-mode is on, per-domain autonomy modes, and any actions waiting for "
        "the user's approval."
    ),
    parameters={},
    risk="low",
    allowed_agents=_AGENTS,
)
def tool_safety_status() -> str:
    from brain import autonomy
    paused = "yes" if autonomy.is_paused() else "no"
    away = "yes" if autonomy.is_away() else "no"
    modes = autonomy._load_domain_modes()
    dom_line = ("  domains: " + ", ".join(f"{d}={m}" for d, m in sorted(modes.items()))
                if modes else f"  domains: all follow global ({autonomy.get_autonomy_mode()})")
    return (
        f"Safety status — paused: {paused}, away-mode: {away}.\n{dom_line}\n"
        f"{autonomy.pending_summary()}"
    )
