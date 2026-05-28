import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_all_ten_tools_register():
    import brain.tools.second_brain  # noqa: triggers registration
    from brain.tools.registry import TOOL_REGISTRY
    expected = [
        "create_brain_note", "update_brain_note", "propose_brain_change",
        "search_brain", "get_brain_note", "list_brain_notes",
        "review_proposals", "approve_proposal", "reject_proposal",
        "update_personal_model",
    ]
    for name in expected:
        assert name in TOOL_REGISTRY, f"Tool not registered: {name}"


def test_tool_schemas_have_required_fields():
    import brain.tools.second_brain  # noqa
    from brain.tools.registry import TOOL_REGISTRY
    for name in ["create_brain_note", "search_brain", "approve_proposal"]:
        schema = TOOL_REGISTRY[name]["schema"]
        assert "description" in schema
        assert "input_schema" in schema
        assert schema["input_schema"]["type"] == "object"


def test_create_brain_note_tool_executes(tmp_path, monkeypatch):
    import memory.vault as vault_mod
    vault_mod.DEFAULT_VAULT_PATH = tmp_path / "SB"
    vault_mod._vm_instance = None  # no-op but kept for clarity

    import brain.tools.second_brain as sb_mod
    sb_mod._vault_instance = None  # reset module singleton

    from brain.tools.registry import execute_tool
    import brain.tools.second_brain  # noqa
    result = execute_tool("create_brain_note", {
        "title": "Test Book",
        "content": "Great book about resilience.",
        "area": "Learning",
        "source": "conversation",
    })
    assert "created" in result.lower() or "proposal" in result.lower()
    sb_mod._vault_instance = None  # cleanup


def test_search_brain_tool_executes(tmp_path, monkeypatch):
    import memory.vault as vault_mod
    vault_mod.DEFAULT_VAULT_PATH = tmp_path / "SB"

    import brain.tools.second_brain as sb_mod
    sb_mod._vault_instance = None

    from brain.tools.registry import execute_tool
    import brain.tools.second_brain  # noqa
    result = execute_tool("search_brain", {"query": "gym workout"})
    assert isinstance(result, str)
    sb_mod._vault_instance = None


def test_review_proposals_tool_executes(tmp_path, monkeypatch):
    import memory.vault as vault_mod
    vault_mod.DEFAULT_VAULT_PATH = tmp_path / "SB"

    import brain.tools.second_brain as sb_mod
    sb_mod._vault_instance = None

    from brain.tools.registry import execute_tool
    import brain.tools.second_brain  # noqa
    result = execute_tool("review_proposals", {})
    assert "pending" in result.lower() or "no pending" in result.lower()
    sb_mod._vault_instance = None
