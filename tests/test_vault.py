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


def test_compute_hash_is_deterministic(vault):
    h1 = vault._compute_hash("hello world")
    h2 = vault._compute_hash("hello world")
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_compute_hash_differs_on_change(vault):
    assert vault._compute_hash("abc") != vault._compute_hash("xyz")


def test_build_frontmatter_includes_required_fields(vault):
    fm = vault._build_frontmatter(
        title="Test Note", area="Learning", source="conversation, 2026-05-28",
        sensitivity="low", created_by="jarvis"
    )
    assert "title: Test Note" in fm
    assert "area: Learning" in fm
    assert "sensitivity: low" in fm
    assert "created_by: jarvis" in fm
    assert "jarvis_last_hash:" in fm
    assert fm.startswith("---\n")
    assert fm.strip().endswith("---")


def test_parse_frontmatter_extracts_hash(vault, tmp_path):
    note_path = tmp_path / "SecondBrain" / "Learning" / "test.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(
        "---\ntitle: Test\njarvis_last_hash: abc123\n---\n\n# Test\n",
        encoding="utf-8"
    )
    fm = vault._parse_frontmatter(note_path)
    assert fm.get("jarvis_last_hash") == "abc123"


def test_should_propose_high_risk_area(vault):
    assert vault._should_propose("Business", "low", False) is True
    assert vault._should_propose("Relationships", "low", False) is True
    assert vault._should_propose("Decisions", "medium", False) is True


def test_should_propose_low_area_high_sensitivity(vault):
    # Sensitivity always wins — low area + high sensitivity → propose
    assert vault._should_propose("Learning", "high", False) is True


def test_should_not_propose_low_risk_low_sensitivity(vault):
    assert vault._should_propose("Learning", "low", False) is False
    assert vault._should_propose("Daily", "low", False) is False


def test_should_propose_when_human_edited(vault):
    # Human edits always trigger proposal regardless of risk
    assert vault._should_propose("Learning", "low", has_human_edits=True) is True
