"""
Tool registry — the @tool decorator registers functions here at import time.

TOOL_REGISTRY maps tool_name → {schema, fn, allowed_agents}.
get_tools(agent=None) returns the schema list; pass agent to filter.
execute_tool(name, args, agent=None) looks up and calls the function;
pass agent to enforce per-agent access control.
"""
import json as _json
import os as _os
import time as _time
from typing import Callable, Optional, List

TOOL_REGISTRY: dict = {}

# Largest file we'll snapshot for undo (keeps the ledger from bloating). Files
# bigger than this get no content-inverse — the red-list confirmation is then
# the only compensating control, which is the documented honest behavior.
_MAX_SNAPSHOT_BYTES = 256 * 1024

# Structured observability (safe no-op if obs is unavailable).
try:
    from obs.log import log_event as _obs
except Exception:
    def _obs(*a, **k):
        pass


def tool(description: str, parameters: dict,
         allowed_agents: Optional[List[str]] = None,
         risk: str = "low") -> Callable:
    """Decorator that registers a function as a JARVIS tool.

    Usage:
        @tool(
            description="What this tool does",
            parameters={"arg": {"type": "string", "description": "..."}},
            allowed_agents=["JARVIS"],   # optional: restrict to specific agents
            risk="red",                  # optional: risk band (default "low")
        )
        def my_tool(arg: str) -> str:
            return "result"

    allowed_agents=None (default) → tool is available to all agents.
    allowed_agents=["JARVIS"]     → only JARVIS may call it; other agents
                                    are blocked at execute_tool time and the
                                    tool is hidden from get_tools(agent=other).

    risk="low" (default) → ordinary tool.
    risk="medium"        → notable but reversible.
    risk="red"           → irreversible / high-stakes. The central autonomy gate
                           routes red-list calls to human confirmation when the
                           user is away or the call came from an untrusted source.
    """
    def decorator(fn: Callable) -> Callable:
        TOOL_REGISTRY[fn.__name__] = {
            "schema": {
                "name": fn.__name__,
                "description": description,
                "input_schema": {
                    "type": "object",
                    "properties": parameters,
                    "required": list(parameters.keys()),
                },
            },
            "fn": fn,
            "allowed_agents": allowed_agents,
            "risk": risk,
        }
        return fn
    return decorator


def _agent_can_call(entry: dict, agent: Optional[str]) -> bool:
    """Return True if `agent` is permitted to call this tool entry.

    If agent is None (caller didn't specify), no filtering — preserves
    backward compatibility for code paths that don't pass an agent.
    If the tool has no allowed_agents restriction, any agent may call it.
    """
    if agent is None:
        return True
    allowed = entry.get("allowed_agents")
    if allowed is None:
        return True
    return agent in allowed


def get_tools(agent: Optional[str] = None) -> list:
    """Return list of tool schemas in the format Claude's API expects.

    If agent is given, only tools that agent is allowed to call are returned.
    """
    return [entry["schema"] for entry in TOOL_REGISTRY.values()
            if _agent_can_call(entry, agent)]


def _abspath(path: str) -> str:
    return _os.path.abspath(_os.path.expanduser(str(path)))


def _capture_prestate(name: str, args: dict) -> Optional[dict]:
    """Snapshot just-enough state BEFORE a reversible file op runs so a correct
    inverse can be built afterward. Called pre-execution (the prior on-disk
    content is gone once write_file overwrites). Returns None for tools that
    need no snapshot. Best-effort: never raises into the caller."""
    try:
        if name == "write_file":
            full = _abspath((args or {}).get("path", ""))
            if _os.path.isfile(full):
                if _os.path.getsize(full) <= _MAX_SNAPSHOT_BYTES:
                    with open(full, "r", encoding="utf-8", errors="replace") as f:
                        return {"existed": True, "content": f.read()}
                return {"existed": True, "content": None, "toobig": True}
            return {"existed": False}
    except Exception:
        pass
    return None


def _inverse_for(name: str, args: dict, prestate: Optional[dict] = None):
    """Return (inverse_tool, inverse_args) for the reversible ledger so panic()
    and per-action Undo can truly restore prior state, or (None, None) when no
    correct inverse is knowable.

    Reversible subset:
      - create_file → delete the new file.
      - write_file  → restore the prior content (snapshotted in prestate); if
                      the file didn't exist before, the inverse is to delete it;
                      if it was too big to snapshot, no inverse (honest).
      - move_file   → move it back.
    Genuinely irreversible tools (send_email/transfer_money/run_shell/…) stay
    (None, None) and rely on the red-list confirmation gate — they must never
    auto-fire unconfirmed in the first place.
    """
    args = args or {}
    if name == "create_file":
        path = args.get("path")
        if path:
            return "delete_file", {"path": path}
    elif name == "write_file":
        path = args.get("path")
        if path and prestate is not None:
            if prestate.get("existed") and prestate.get("content") is not None:
                return "write_file", {"path": path, "content": prestate["content"]}
            if not prestate.get("existed"):
                return "delete_file", {"path": path}
            # existed but too big to snapshot → no safe inverse
    elif name == "move_file":
        src, dst = args.get("src"), args.get("dst")
        if src and dst:
            return "move_file", {"src": dst, "dst": src}
    return None, None


def execute_tool(name: str, args: dict, agent: Optional[str] = None,
                 source: str = "user", _bypass_gate: bool = False) -> str:
    """Call a registered tool by name with the given arguments.

    Access control:
        If agent is given and the tool restricts allowed_agents, the call is
        refused with a clear message instead of being executed.

    Safety gate (Block: risk gate):
        Unless _bypass_gate is True, every call funnels through the central
        autonomy gate (brain.autonomy.gate). The gate decides one of:
          - "execute": fall through and run the tool.
          - "deny":    the kill-switch (paused) blocked a non-user action —
                       return a clear message, do NOT run, log success=False.
          - "confirm": a red-list action while away / from an untrusted source —
                       it was enqueued for human approval; return a "needs
                       approval" message, do NOT run, log a pending entry.

    source:
        "user"       — a direct, present-human request (most permissive).
        "autonomous" — JARVIS acting on its own.
        "external"   — triggered by untrusted inbound content.

    _bypass_gate=True skips the gate entirely (used by autonomy.approve once the
    human has already approved a queued action) but the execution is still logged.
    """
    if name not in TOOL_REGISTRY:
        return f"Unknown tool: '{name}'. Available: {', '.join(TOOL_REGISTRY.keys())}"
    entry = TOOL_REGISTRY[name]
    risk = entry.get("risk")
    if not _agent_can_call(entry, agent):
        return (f"Tool '{name}' is not available to {agent}. "
                f"JARVIS handles this — suggest it via [BRAIN: suggest → ...] instead.")

    if not _bypass_gate:
        # Guarded import — autonomy imports the registry (approve path), so a
        # module-level import here would be circular.
        try:
            from brain import autonomy
            decision = autonomy.gate(name, args, agent=agent, risk=risk, source=source)
        except Exception as gate_err:
            # A safety gate MUST fail CLOSED. If gate() itself raises (schema
            # drift, sqlite lock, import error, …) we do NOT run the tool — we
            # deny it loudly. Failing open here would silently bypass red-list /
            # away-mode / pause / blocklist for the highest-risk tools.
            _obs("tool.gate_error", level="error", tool=name, agent=agent, risk=risk,
                 source=source, error=str(gate_err))
            decision = {"action": "deny",
                        "reason": f"safety gate unavailable ({gate_err}) — failing closed"}

        if decision is not None:
            action = decision.get("action")
            if action == "deny":
                msg = f"🚫 '{name}' was blocked: {decision.get('reason', 'denied by safety gate')}"
                _obs("tool.denied", level="warning", tool=name, agent=agent, risk=risk,
                     source=source, reason=decision.get("reason"))
                try:
                    from memory.memory import log_action
                    log_action(name, args, msg, success=False, agent=agent, risk=risk)
                except Exception:
                    pass
                return msg
            if action == "confirm":
                cid = decision.get("confirm_id")
                msg = (f"⏳ '{name}' needs your approval (#{cid}) — sent to Telegram.")
                _obs("tool.confirm_required", tool=name, agent=agent, risk=risk,
                     source=source, confirm_id=cid)
                try:
                    from memory.memory import log_action
                    log_action(name, args, msg, success=False, agent=agent, risk=risk)
                except Exception:
                    pass
                return msg
            # action == "execute" → fall through and run.

    # Snapshot prior state BEFORE running, so a reversible op (write/create/move)
    # can record a correct inverse for panic()/Undo.
    prestate = _capture_prestate(name, args)

    _start = _time.time()
    try:
        result = str(entry["fn"](**args))
        _obs("tool.executed", tool=name, agent=agent, risk=risk, source=source, ok=True,
             duration_ms=round((_time.time() - _start) * 1000), arg_keys=list(args.keys()))
        try:
            from memory.memory import log_action
            inverse_tool, inverse_args = _inverse_for(name, args, prestate)
            log_action(name, args, result, success=True, agent=agent, risk=risk,
                       inverse_tool=inverse_tool, inverse_args=inverse_args)
        except Exception:
            pass
        return result
    except Exception as e:
        err = f"Tool '{name}' failed: {e}"
        _obs("tool.failed", level="error", tool=name, agent=agent, risk=risk, source=source,
             duration_ms=round((_time.time() - _start) * 1000), error=str(e))
        try:
            from memory.memory import log_action
            log_action(name, args, err, success=False, agent=agent, risk=risk)
        except Exception:
            pass
        return err
