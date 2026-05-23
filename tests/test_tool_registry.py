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
