"""
Tool registry — the @tool decorator registers functions here at import time.

TOOL_REGISTRY maps tool_name → {schema, fn}.
get_tools() returns the schema list Claude reads to know what tools exist.
execute_tool(name, args) looks up and calls the function.
"""
from typing import Callable

TOOL_REGISTRY: dict = {}


def tool(description: str, parameters: dict) -> Callable:
    """Decorator that registers a function as a JARVIS tool.

    Usage:
        @tool(
            description="What this tool does",
            parameters={"arg": {"type": "string", "description": "..."}}
        )
        def my_tool(arg: str) -> str:
            return "result"
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
        }
        return fn
    return decorator


def get_tools() -> list:
    """Return list of tool schemas in the format Claude's API expects."""
    return [entry["schema"] for entry in TOOL_REGISTRY.values()]


def execute_tool(name: str, args: dict) -> str:
    """Call a registered tool by name with the given arguments."""
    if name not in TOOL_REGISTRY:
        return f"Unknown tool: '{name}'. Available: {', '.join(TOOL_REGISTRY.keys())}"
    try:
        return str(TOOL_REGISTRY[name]["fn"](**args))
    except Exception as e:
        return f"Tool '{name}' failed: {e}"
