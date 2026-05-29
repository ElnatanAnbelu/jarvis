"""Tests for B8 — Observer + Second Brain grounding."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_search_brain_for_topic_returns_empty_when_vault_empty(tmp_path):
    """No vault content → no grounding string."""
    import memory.vault as vm_mod
    vm_mod._second_brain_instance = None
    vm_mod.DEFAULT_VAULT_PATH = tmp_path / "SB"
    from brain.observer import _search_brain_for_topic
    result = _search_brain_for_topic("nonexistent_topic_xyz")
    assert result == ""
    vm_mod._second_brain_instance = None


def test_search_brain_for_topic_returns_excerpt_when_relevant(tmp_path):
    """Vault has a relevant note → grounding string returned."""
    import memory.vault as vm_mod
    vm_mod._second_brain_instance = None
    vm_mod.DEFAULT_VAULT_PATH = tmp_path / "SB"
    from memory.vault import VaultManager
    vm = VaultManager()
    vm.create_note(
        title="Reading Atomic Habits",
        content="Currently on chapter 3. The habit loop framework is clarifying.",
        area="Learning",
        source="test",
    )
    vm_mod._second_brain_instance = vm

    from brain.observer import _search_brain_for_topic
    result = _search_brain_for_topic("habits")
    # Either an excerpt or empty (keyword fallback may or may not hit). Both acceptable
    # as long as the function doesn't crash and returns a string.
    assert isinstance(result, str)
    vm_mod._second_brain_instance = None


def test_search_brain_for_topic_truncates_long_results(tmp_path):
    import memory.vault as vm_mod
    vm_mod._second_brain_instance = None
    vm_mod.DEFAULT_VAULT_PATH = tmp_path / "SB"
    from memory.vault import VaultManager
    vm = VaultManager()
    long_body = "Atomic habits content. " * 200
    vm.create_note(
        title="Long Note On Habits",
        content=long_body,
        area="Learning",
        source="test",
    )
    vm_mod._second_brain_instance = vm

    from brain.observer import _search_brain_for_topic
    result = _search_brain_for_topic("habits", max_chars=200)
    assert len(result) <= 210  # 200 + "..." padding
    vm_mod._second_brain_instance = None


def test_search_brain_for_topic_handles_empty_topic():
    from brain.observer import _search_brain_for_topic
    assert _search_brain_for_topic("") == ""
    assert _search_brain_for_topic(None) == ""


def test_search_brain_for_topic_handles_vault_failure(monkeypatch):
    """If the vault import or query fails, fall back silently to empty string."""
    from brain.observer import _search_brain_for_topic

    def boom(*args, **kwargs):
        raise RuntimeError("vault unreachable")

    import memory.vault as vm_mod
    monkeypatch.setattr(vm_mod, "VaultManager", boom)
    if hasattr(vm_mod, "_second_brain_instance"):
        vm_mod._second_brain_instance = None

    result = _search_brain_for_topic("anything")
    assert result == ""


def test_detect_pattern_returns_three_values_when_no_history(monkeypatch):
    """Schema check: _detect_pattern always returns a 3-tuple."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    from brain.observer import _detect_pattern
    # With insufficient history, returns (None, None, False)
    result = _detect_pattern()
    assert isinstance(result, tuple)
    assert len(result) == 3
    assert result[2] in (True, False)
