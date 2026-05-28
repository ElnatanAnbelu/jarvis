import pytest
from brain.tools.registry import tool, TOOL_REGISTRY, get_tools, execute_tool


def test_tool_decorator_registers_function():
    @tool(
        description="A test tool",
        parameters={"value": {"type": "string", "description": "A value"}}
    )
    def my_test_tool(value: str) -> str:
        return f"got: {value}"

    assert "my_test_tool" in TOOL_REGISTRY


def test_get_tools_returns_schema_list():
    tools = get_tools()
    assert isinstance(tools, list)
    assert len(tools) > 0
    first = tools[0]
    assert "name" in first
    assert "description" in first
    assert "input_schema" in first


def test_execute_tool_calls_function():
    @tool(
        description="Another test tool",
        parameters={"x": {"type": "integer", "description": "A number"}}
    )
    def add_one(x: int) -> str:
        return str(x + 1)

    result = execute_tool("add_one", {"x": 5})
    assert result == "6"


def test_execute_unknown_tool_returns_error():
    result = execute_tool("this_tool_does_not_exist", {})
    assert "unknown" in result.lower() or "not found" in result.lower()


# ── B4: Agent-aware access control ────────────────────────────────────────────

def test_tool_with_allowed_agents_registers():
    @tool(
        description="JARVIS-only test tool",
        parameters={"x": {"type": "string", "description": "anything"}},
        allowed_agents=["JARVIS"],
    )
    def jarvis_only_tool(x: str) -> str:
        return f"got: {x}"

    assert TOOL_REGISTRY["jarvis_only_tool"].get("allowed_agents") == ["JARVIS"]


def test_execute_tool_allows_jarvis_for_jarvis_only_tool():
    @tool(
        description="restricted",
        parameters={"v": {"type": "string", "description": "v"}},
        allowed_agents=["JARVIS"],
    )
    def restricted_one(v: str) -> str:
        return f"ok: {v}"

    result = execute_tool("restricted_one", {"v": "abc"}, agent="JARVIS")
    assert "not available" not in result.lower()
    assert "ok: abc" in result


def test_execute_tool_blocks_friday_from_jarvis_only_tool():
    @tool(
        description="restricted",
        parameters={"v": {"type": "string", "description": "v"}},
        allowed_agents=["JARVIS"],
    )
    def restricted_two(v: str) -> str:
        return f"should not run: {v}"

    result = execute_tool("restricted_two", {"v": "x"}, agent="FRIDAY")
    assert "not available" in result.lower()
    assert "should not run" not in result


def test_execute_tool_blocks_veronica_from_create_brain_note():
    # Real production tool, real production block
    import brain.tools.second_brain  # noqa: F401 — triggers registration
    result = execute_tool("create_brain_note", {
        "title": "X", "content": "y", "area": "Learning", "source": "test",
    }, agent="VERONICA")
    assert "not available" in result.lower()


def test_get_tools_for_friday_excludes_writes():
    import brain.tools.second_brain  # noqa: F401
    schemas = get_tools(agent="FRIDAY")
    names = [s["name"] for s in schemas]
    # Write tools are blocked
    assert "create_brain_note" not in names
    assert "update_brain_note" not in names
    assert "propose_brain_change" not in names
    assert "approve_proposal" not in names
    assert "reject_proposal" not in names
    assert "update_personal_model" not in names
    # Read tools remain
    assert "search_brain" in names
    assert "get_brain_note" in names
    assert "list_brain_notes" in names
    assert "review_proposals" in names


def test_get_tools_for_jarvis_includes_writes():
    import brain.tools.second_brain  # noqa: F401
    schemas = get_tools(agent="JARVIS")
    names = [s["name"] for s in schemas]
    assert "create_brain_note" in names
    assert "update_personal_model" in names
    assert "approve_proposal" in names


def test_get_tools_no_agent_returns_all():
    """Backward compat: get_tools() with no agent returns everything."""
    import brain.tools.second_brain  # noqa: F401
    schemas = get_tools()
    names = [s["name"] for s in schemas]
    assert "create_brain_note" in names
    assert "search_brain" in names


def test_execute_tool_no_agent_does_not_block():
    """Backward compat: execute_tool with no agent param does not enforce ACL."""
    import brain.tools.second_brain  # noqa: F401
    # Pre-existing callers that don't pass agent must still work.
    @tool(
        description="restricted, no agent caller",
        parameters={"v": {"type": "string", "description": "v"}},
        allowed_agents=["JARVIS"],
    )
    def restricted_three(v: str) -> str:
        return f"ran: {v}"

    result = execute_tool("restricted_three", {"v": "ok"})  # no agent kwarg
    assert "ran: ok" in result
