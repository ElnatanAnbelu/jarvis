"""
Tool registry — the @tool decorator registers functions here at import time.

TOOL_REGISTRY maps tool_name → {schema, fn, allowed_agents}.
get_tools(agent=None) returns the schema list; pass agent to filter.
execute_tool(name, args, agent=None) looks up and calls the function;
pass agent to enforce per-agent access control.
"""
from typing import Callable, Optional, List

TOOL_REGISTRY: dict = {}


def tool(description: str, parameters: dict,
         allowed_agents: Optional[List[str]] = None) -> Callable:
    """Decorator that registers a function as a JARVIS tool.

    Usage:
        @tool(
            description="What this tool does",
            parameters={"arg": {"type": "string", "description": "..."}},
            allowed_agents=["JARVIS"],   # optional: restrict to specific agents
        )
        def my_tool(arg: str) -> str:
            return "result"

    allowed_agents=None (default) → tool is available to all agents.
    allowed_agents=["JARVIS"]     → only JARVIS may call it; other agents
                                    are blocked at execute_tool time and the
                                    tool is hidden from get_tools(agent=other).
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


def execute_tool(name: str, args: dict, agent: Optional[str] = None) -> str:
    """Call a registered tool by name with the given arguments.

    If agent is given and the tool restricts allowed_agents, the call is
    refused with a clear message instead of being executed.
    """
    if name not in TOOL_REGISTRY:
        return f"Unknown tool: '{name}'. Available: {', '.join(TOOL_REGISTRY.keys())}"
    entry = TOOL_REGISTRY[name]
    if not _agent_can_call(entry, agent):
        return (f"Tool '{name}' is not available to {agent}. "
                f"JARVIS handles this — suggest it via [BRAIN: suggest → ...] instead.")
    try:
        result = str(entry["fn"](**args))
        try:
            from memory.memory import log_action
            log_action(name, args, result, success=True)
        except Exception:
            pass
        return result
    except Exception as e:
        err = f"Tool '{name}' failed: {e}"
        try:
            from memory.memory import log_action
            log_action(name, args, err, success=False)
        except Exception:
            pass
        return err
