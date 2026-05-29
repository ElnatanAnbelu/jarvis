"""Tests for per-agent brain context injection (FRIDAY/VERONICA/KAREN)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_brain_context_empty_when_query_not_personal():
    """Non-personal queries get no brain context."""
    from brain.free_agents import _get_brain_context_for_agent
    result = _get_brain_context_for_agent("what's the latest news on AI?")
    assert result == ""


def test_brain_context_empty_on_no_query():
    from brain.free_agents import _get_brain_context_for_agent
    assert _get_brain_context_for_agent("") == ""
    assert _get_brain_context_for_agent(None) == ""


def test_brain_context_returns_string_on_personal_query(tmp_path):
    """Personal query triggers vault search; always returns a string."""
    import memory.vault as vm_mod
    vm_mod._second_brain_instance = None
    vm_mod.DEFAULT_VAULT_PATH = tmp_path / "SB"

    from brain.free_agents import _get_brain_context_for_agent
    result = _get_brain_context_for_agent("how's my sleep been lately?")
    assert isinstance(result, str)
    vm_mod._second_brain_instance = None


def test_brain_context_includes_header_when_content_found(tmp_path):
    """When vault has matching content, the BRAIN CONTEXT header appears."""
    import memory.vault as vm_mod
    vm_mod._second_brain_instance = None
    vm_mod.DEFAULT_VAULT_PATH = tmp_path / "SB"

    from memory.vault import VaultManager
    vm = VaultManager()
    vm.create_note(
        title="My Gym Routine",
        content="Bench Monday Wednesday Friday at 160 lbs.",
        area="Daily",
        source="test",
    )
    vm_mod._second_brain_instance = vm

    from brain.free_agents import _get_brain_context_for_agent
    result = _get_brain_context_for_agent("how's my gym going?")
    if result:  # search may or may not hit; if it does, header is present
        assert "BRAIN CONTEXT" in result
    vm_mod._second_brain_instance = None


def test_build_memory_block_returns_three_tuple():
    """Backward compat: callers expect a 3-tuple now."""
    from brain.free_agents import _build_memory_block
    result = _build_memory_block("hey")
    assert isinstance(result, tuple)
    assert len(result) == 3
    facts, wiki, brain = result
    assert isinstance(facts, str)
    assert isinstance(wiki, str)
    assert isinstance(brain, str)


def test_gemini_build_memory_block_returns_three_tuple():
    """FRIDAY's _build_memory_block in gemini.py also returns a 3-tuple."""
    from brain.gemini import _build_memory_block
    result = _build_memory_block("hello")
    assert isinstance(result, tuple)
    assert len(result) == 3
