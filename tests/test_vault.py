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


def test_update_frontmatter_field_changes_value(vault, tmp_path):
    note_path = tmp_path / "SecondBrain" / "Learning" / "test_fm.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(
        "---\ntitle: Old\njarvis_last_hash: aaa\n---\n\n# Old\n",
        encoding="utf-8"
    )
    vault._update_frontmatter_field(note_path, "jarvis_last_hash", "bbb")
    updated = vault._parse_frontmatter(note_path)
    assert updated["jarvis_last_hash"] == "bbb"
    # title should be unchanged
    assert updated["title"] == "Old"


def test_safe_title_strips_forbidden_chars(vault):
    dirty = 'My: "Note" <with> /special\\chars|?*'
    result = vault._safe_title(dirty)
    for ch in '<>:"/\\|?*':
        assert ch not in result
    assert "Note" in result
    assert "special" in result


def test_safe_title_clean_string_unchanged(vault):
    clean = "Open by Andre Agassi"
    assert vault._safe_title(clean) == clean


def test_log_activity_appends_to_markdown(vault, tmp_path):
    vault._log_activity("create", "Learning/Test.md", "conversation", "test note", "low")
    content = (tmp_path / "SecondBrain" / "_JARVIS" / "_Activity.md").read_text()
    assert "create" in content
    assert "Learning/Test.md" in content
    assert "conversation" in content


def test_log_activity_appends_jsonl_entry(vault, tmp_path):
    import json
    vault._log_activity("update", "Daily/2026-05-28.md", "email", "gym log", "low")
    lines = (tmp_path / "SecondBrain" / "_JARVIS" / "_Activity.jsonl").read_text().strip().splitlines()
    entries = [json.loads(l) for l in lines if l.strip()]
    activity = [e for e in entries if e.get("action") == "update"]
    assert len(activity) == 1
    assert activity[0]["note"] == "Daily/2026-05-28.md"
    assert activity[0]["source"] == "email"
    assert "ts" in activity[0]


def test_log_multiple_activities_accumulate(vault, tmp_path):
    import json
    vault._log_activity("create", "Learning/A.md", "conv", "a", "low")
    vault._log_activity("create", "Learning/B.md", "conv", "b", "low")
    lines = [l for l in
        (tmp_path / "SecondBrain" / "_JARVIS" / "_Activity.jsonl")
        .read_text().strip().splitlines()
        if l.strip()]
    non_init = [l for l in lines if "vault_init" not in l]
    assert len(non_init) == 2


# ── Task 4: create_note / update_note tests ────────────────────────────────────

def test_create_note_low_risk_writes_file(vault, tmp_path):
    result = vault.create_note(
        title="Python Basics",
        content="Python is a high-level language.",
        area="Learning",
        source="conversation, 2026-05-28",
    )
    note_path = tmp_path / "SecondBrain" / "Learning" / "Python Basics.md"
    assert note_path.exists()
    content = note_path.read_text()
    assert "Python is a high-level language" in content
    assert "JARVIS" in content  # attribution blockquote
    assert "created" in result.lower() or "auto_write" in result


def test_create_note_high_risk_creates_proposal(vault, tmp_path):
    result = vault.create_note(
        title="Investor Ahmed",
        content="Met investor Ahmed today.",
        area="Relationships",
        source="conversation, 2026-05-28",
    )
    proposals = list((tmp_path / "SecondBrain" / "_JARVIS" / "Proposals").rglob("*.md"))
    assert len(proposals) == 1
    assert "proposal" in result.lower() or "proposed" in result.lower()
    rel_path = tmp_path / "SecondBrain" / "Relationships" / "Investor Ahmed.md"
    assert not rel_path.exists()


def test_create_note_low_area_high_sensitivity_creates_proposal(vault, tmp_path):
    result = vault.create_note(
        title="Medical Checkup",
        content="Had a checkup. All good.",
        area="Learning",
        source="conversation",
        sensitivity="high",
    )
    proposals = list((tmp_path / "SecondBrain" / "_JARVIS" / "Proposals").rglob("*.md"))
    assert len(proposals) == 1


def test_create_note_writes_attribution_header(vault, tmp_path):
    vault.create_note("Book Notes", "Key takeaway here.", "Learning", "email, 2026-05-28")
    note = (tmp_path / "SecondBrain" / "Learning" / "Book Notes.md").read_text()
    assert "*JARVIS:" in note
    assert "email, 2026-05-28" in note


def test_update_note_appends_when_no_conflict(vault, tmp_path):
    vault.create_note("My Log", "Entry 1.", "Daily", "conv")
    result = vault.update_note("Daily/My Log", "Entry 2.", "conv")
    note = (tmp_path / "SecondBrain" / "Daily" / "My Log.md").read_text()
    assert "Entry 1" in note
    assert "Entry 2" in note
    assert "proposed" not in result.lower()


def test_update_note_proposes_when_human_edited(vault, tmp_path):
    vault.create_note("My Log", "Entry 1.", "Daily", "conv")
    note_path = tmp_path / "SecondBrain" / "Daily" / "My Log.md"
    note_path.write_text(note_path.read_text() + "\n*human addition*\n", encoding="utf-8")
    result = vault.update_note("Daily/My Log", "Entry 2.", "conv")
    assert "proposal" in result.lower() or "proposed" in result.lower()
    proposals = list((tmp_path / "SecondBrain" / "_JARVIS" / "Proposals").rglob("*.md"))
    assert len(proposals) == 1


# ── Task 5: Proposal System tests ─────────────────────────────────────────────

def test_propose_change_creates_file_in_proposals_dir(vault, tmp_path):
    vault.propose_change(
        title="Addis Market Revenue",
        proposed_content="Revenue hit $1000 this month.",
        action="create",
        area="Business",
        source="conversation, 2026-05-28",
        reason="Elnatan mentioned hitting first revenue milestone",
    )
    proposals = list((tmp_path / "SecondBrain" / "_JARVIS" / "Proposals").rglob("*.md"))
    assert len(proposals) == 1


def test_proposal_file_has_required_frontmatter(vault, tmp_path):
    vault.propose_change("Test", "content", "create", "Business", "conv", "test")
    p = list((tmp_path / "SecondBrain" / "_JARVIS" / "Proposals").rglob("*.md"))[0]
    text = p.read_text()
    assert "proposal_id:" in text
    assert "status: pending" in text
    assert "target_note:" in text
    assert "action: create" in text
    assert "reason:" in text


def test_proposals_organized_by_subfolder(vault, tmp_path):
    """Proposals live under Proposals/{Area}/ subfolders, not flat."""
    vault.propose_change("A", "c", "create", "Business", "conv", "r")
    vault.propose_change("B", "c", "create", "Business", "conv", "r")
    proposals_root = tmp_path / "SecondBrain" / "_JARVIS" / "Proposals"
    business_files = sorted((proposals_root / "Business").glob("*.md"))
    stems = {p.stem for p in business_files}
    assert "A" in stems
    assert "B" in stems


def test_propose_change_returns_proposal_id_in_result(vault):
    result = vault.propose_change("X", "c", "create", "Business", "conv", "r")
    assert "proposal" in result.lower()
    # Clean proposal ID: just the title (subfolder shows area)
    assert "X" in result


def test_proposal_collision_appends_counter(vault, tmp_path):
    """Two proposals targeting the same note get unique filenames within
    their area subfolder."""
    vault.propose_change("Same Target", "c1", "create", "Business", "conv", "r1")
    vault.propose_change("Same Target", "c2", "create", "Business", "conv", "r2")
    business_dir = tmp_path / "SecondBrain" / "_JARVIS" / "Proposals" / "Business"
    stems = {p.stem for p in business_dir.glob("*.md")}
    assert "Same Target" in stems
    assert "Same Target (2)" in stems


# ── Task 6: Proposal Review Flow tests ────────────────────────────────────────

def test_get_pending_proposals_lists_pending_only(vault, tmp_path):
    vault.propose_change("A", "c1", "create", "Business", "conv", "r1")
    vault.propose_change("B", "c2", "create", "Decisions", "conv", "r2")
    result = vault.get_pending_proposals()
    # New format: target_note shown in the listing, IDs are clean titles
    assert "Business/A" in result
    assert "Decisions/B" in result


def test_approve_proposal_writes_note(vault, tmp_path):
    vault.propose_change("New Insight", "This is the content.", "create",
                         "Learning", "conversation", "test insight")
    proposals = list((tmp_path / "SecondBrain" / "_JARVIS" / "Proposals").rglob("*.md"))
    pid = proposals[0].stem
    result = vault.approve_proposal(pid)
    note_path = tmp_path / "SecondBrain" / "Learning" / "New Insight.md"
    assert note_path.exists()
    assert "This is the content." in note_path.read_text()
    assert "approved" in result.lower()


def test_approve_proposal_marks_status_approved(vault, tmp_path):
    vault.propose_change("X", "content", "create", "Learning", "conv", "r")
    proposals_root = tmp_path / "SecondBrain" / "_JARVIS" / "Proposals"
    proposal_files = list(proposals_root.rglob("*.md"))
    pid = proposal_files[0].stem
    vault.approve_proposal(pid)
    # After approval the file moves to _Archive/approved/...
    archived = list((proposals_root / "_Archive" / "approved").rglob("*.md"))
    assert any("status: approved" in p.read_text() for p in archived)


def test_approve_proposal_stale_when_note_changed(vault, tmp_path):
    # Create a note, then propose an update to it
    vault.create_note("Existing Note", "original content", "Learning", "conv")
    vault.propose_change("Existing Note", "updated content", "update",
                         "Learning", "conv", "update reason")
    pid = list((tmp_path / "SecondBrain" / "_JARVIS" / "Proposals").rglob("*.md"))[0].stem
    # Human edits the note AFTER the proposal was created
    note_path = tmp_path / "SecondBrain" / "Learning" / "Existing Note.md"
    note_path.write_text(note_path.read_text() + "\n*human edit*\n", encoding="utf-8")
    result = vault.approve_proposal(pid)
    assert "stale" in result.lower()
    assert "updated content" not in note_path.read_text()


def test_approve_proposal_overwrites_init_stub(vault, tmp_path):
    """Approval can land on a vault-init stub (Personal/About Me, etc.)
    without hitting the stale guard — the stub is recognized as a
    placeholder and overwritten."""
    sb = tmp_path / "SecondBrain"
    # The About Me stub is created during vault init
    about_path = sb / "Personal" / "About Me.md"
    assert about_path.exists()  # init created it
    assert "This is your space" in about_path.read_text()  # confirm stub content

    # Stage a proposal targeting About Me
    vault.propose_change("About Me", "Real content here.", "create",
                         "Personal", "test", "seed about me")
    proposal_files = list((sb / "_JARVIS" / "Proposals").rglob("*.md"))
    pid = proposal_files[0].stem

    # Approval should succeed (not stale) because target is an init stub
    result = vault.approve_proposal(pid)
    assert "stale" not in result.lower()
    assert "applied" in result.lower() or "approved" in result.lower()
    assert "Real content here." in about_path.read_text()


def test_approve_proposal_still_stale_on_real_human_content(vault, tmp_path):
    """The stale guard still fires when the target file has real content
    (not a known init stub) — we don't silently overwrite human writes."""
    sb = tmp_path / "SecondBrain"
    real_path = sb / "Personal" / "Manually Written.md"
    real_path.write_text("This is real content I wrote myself.\n", encoding="utf-8")

    vault.propose_change("Manually Written", "JARVIS wants to overwrite", "create",
                         "Personal", "test", "should refuse")
    proposal_files = list((sb / "_JARVIS" / "Proposals").rglob("*.md"))
    pid = proposal_files[0].stem

    result = vault.approve_proposal(pid)
    assert "stale" in result.lower()
    # Real human content is preserved unchanged
    assert "This is real content I wrote myself." in real_path.read_text()
    assert "JARVIS wants to overwrite" not in real_path.read_text()


def test_reject_proposal_preserves_file(vault, tmp_path):
    vault.propose_change("Sensitive", "data", "create", "Decisions", "conv", "reason")
    proposals_root = tmp_path / "SecondBrain" / "_JARVIS" / "Proposals"
    proposal_files = list(proposals_root.rglob("*.md"))
    pid = proposal_files[0].stem
    vault.reject_proposal(pid)
    # File is preserved (moved to _Archive/rejected/) with status updated
    rejected = list((proposals_root / "_Archive" / "rejected").rglob("*.md"))
    assert len(rejected) == 1
    assert "status: rejected" in rejected[0].read_text()


def test_get_pending_proposals_empty(vault):
    result = vault.get_pending_proposals()
    assert "no pending" in result.lower() or result == "" or "0" in result


# ── Task 7: Navigation + Search tests ─────────────────────────────────────────

def test_get_note_returns_content(vault, tmp_path):
    vault.create_note("React Hooks", "useState is fundamental.", "Learning", "conv")
    result = vault.get_note("Learning/React Hooks")
    assert "useState" in result


def test_get_note_not_found(vault):
    result = vault.get_note("Learning/Nonexistent Note")
    assert "not found" in result.lower()


def test_list_notes_returns_notes_in_area(vault, tmp_path):
    vault.create_note("Note A", "content a", "Learning", "conv")
    vault.create_note("Note B", "content b", "Learning", "conv")
    result = vault.list_notes("Learning")
    assert "Note A" in result
    assert "Note B" in result


def test_list_notes_all_areas(vault, tmp_path):
    vault.create_note("Topic X", "x", "Learning", "conv")
    result = vault.list_notes()
    assert "Learning" in result


def test_search_vault_keyword_fallback(vault, tmp_path):
    vault.create_note("Gym Schedule", "I go to gym on Mon/Wed/Fri.", "Daily", "conv")
    result = vault.search_vault("gym workout schedule")
    assert "gym" in result.lower() or "Gym" in result


def test_search_vault_returns_empty_when_no_match(vault):
    result = vault.search_vault("xylophone concerto baroque")
    assert result == "" or "no results" in result.lower()


# ── Task 8: Personal Model tests ───────────────────────────────────────────────

def test_update_personal_model_always_proposes(vault, tmp_path):
    result = vault.update_personal_model(
        section="Interests & Hobbies",
        content="Elnatan has been discussing anime in every session this week.",
        source="conversation pattern, 2026-05-28",
        supporting_observations="3 sessions mentioned anime",
    )
    proposals = list((tmp_path / "SecondBrain" / "_JARVIS" / "Proposals").rglob("*.md"))
    assert len(proposals) == 1
    assert "proposal" in result.lower()


def test_update_personal_model_never_auto_writes(vault, tmp_path):
    vault.update_personal_model("Energy Patterns", "Prefers late night work.",
                                "observation", "5 late-night sessions")
    pm = tmp_path / "SecondBrain" / "_JARVIS" / "_PersonalModel.md"
    assert "Prefers late night work" not in pm.read_text()


def test_update_personal_model_proposal_includes_evidence(vault, tmp_path):
    vault.update_personal_model(
        section="Decision-Making Style",
        content="Tends to delay decisions under uncertainty.",
        source="conversation",
        supporting_observations="Mentioned hesitation 4 times this week",
    )
    p = list((tmp_path / "SecondBrain" / "_JARVIS" / "Proposals").rglob("*.md"))[0]
    text = p.read_text()
    assert "Mentioned hesitation" in text
    assert "Decision-Making Style" in text
