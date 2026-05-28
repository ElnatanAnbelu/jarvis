import pytest
from pathlib import Path


@pytest.fixture
def vault(tmp_path):
    """VaultManager pointed at a temp directory."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from memory.vault import VaultManager
    return VaultManager(vault_path=tmp_path / "SecondBrain")


def test_vault_creates_root_directory(vault, tmp_path):
    assert (tmp_path / "SecondBrain").exists()


def test_vault_creates_all_area_folders(vault, tmp_path):
    sb = tmp_path / "SecondBrain"
    for area in ["Personal", "Business", "Learning", "Relationships",
                 "Goals", "Decisions", "Daily", "Archive"]:
        assert (sb / area).is_dir(), f"Missing area folder: {area}"


def test_vault_creates_jarvis_folders(vault, tmp_path):
    sb = tmp_path / "SecondBrain"
    assert (sb / "_JARVIS").is_dir()
    assert (sb / "_JARVIS" / "Proposals").is_dir()


def test_vault_creates_activity_logs(vault, tmp_path):
    sb = tmp_path / "SecondBrain"
    assert (sb / "_JARVIS" / "_Activity.md").exists()
    assert (sb / "_JARVIS" / "_Activity.jsonl").exists()


def test_vault_creates_personal_model(vault, tmp_path):
    sb = tmp_path / "SecondBrain"
    assert (sb / "_JARVIS" / "_PersonalModel.md").exists()
    content = (sb / "_JARVIS" / "_PersonalModel.md").read_text()
    assert "Personal Model" in content
    assert "Interests" in content


def test_vault_creates_anchor_notes(vault, tmp_path):
    sb = tmp_path / "SecondBrain"
    assert (sb / "Personal" / "About Me.md").exists()
    assert (sb / "Goals" / "Long-Term Goals.md").exists()


def test_vault_bootstrap_is_idempotent(tmp_path):
    """Running VaultManager() twice must not duplicate any file or log entry."""
    from memory.vault import VaultManager
    VaultManager(vault_path=tmp_path / "SecondBrain")
    VaultManager(vault_path=tmp_path / "SecondBrain")
    sb = tmp_path / "SecondBrain"
    activity = (sb / "_JARVIS" / "_Activity.md").read_text()
    assert activity.count("vault_init") == 1  # logged exactly once
