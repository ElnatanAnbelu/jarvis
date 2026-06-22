"""P2(a/b/c) — the brain GROWS correctly: check → register-if-missing → vault, with
HARD dedupe and risk-tiered routing. All tests use a throwaway temp vault — never the
owner's real ~/Desktop one."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.vault import VaultManager


@pytest.fixture
def vault(tmp_path):
    return VaultManager(vault_path=tmp_path / "SecondBrain")


# ── normalization (the dedupe key) ──────────────────────────────────────────────

def test_normalize_collapses_bullets_dates_punctuation():
    n = VaultManager._normalize_fact
    a = n("- Alfred is used for generating reports *(learned 2026-06-22)*")
    b = n("Alfred is used for generating reports.")
    c = n("* alfred IS used for   generating reports (learned 2026-01-01)")
    assert a == b == c
    assert a == "alfred is used for generating reports"


# ── routing → area + risk tier ──────────────────────────────────────────────────

def test_low_risk_interest_autowrites_no_proposal(vault, tmp_path):
    res = vault.register_fact("Interests", "I enjoy long-distance running", "conversation")
    assert "Created" in res or "Updated" in res
    # Lands in Learning (low risk) and auto-writes — no proposal created.
    note = tmp_path / "SecondBrain" / "Learning" / "Interests.md"
    assert note.exists()
    assert "long-distance running" in note.read_text()


def test_family_fact_routes_through_proposal(vault, tmp_path):
    res = vault.register_fact("Family", "My sister just started university", "conversation")
    assert "Proposal created" in res
    # High-risk: NO direct note write — it sits in the proposal queue.
    direct = tmp_path / "SecondBrain" / "Relationships" / "Family.md"
    assert not direct.exists()
    assert "pending" in vault.get_pending_proposals().lower()


def test_health_fact_routes_through_proposal(vault, tmp_path):
    res = vault.register_fact("Health", "I have started taking medication daily", "conversation")
    assert "Proposal created" in res


# ── HARD dedupe — the "×6 bloat" must be impossible ──────────────────────────────

def test_duplicate_low_risk_fact_written_once(vault, tmp_path):
    f = "Alfred is used for generating reports"
    first = vault.register_fact("Interests", f, "conversation")
    assert "Created" in first or "Updated" in first
    # Re-learn the same fact six more times, with cosmetic variation each time.
    for variant in [f + ".", f.upper(), "  " + f + "  ", f, f, f]:
        again = vault.register_fact("Interests", variant, "conversation")
        assert again.startswith("duplicate"), f"expected dedupe for {variant!r}, got {again!r}"
    note = (tmp_path / "SecondBrain" / "Learning" / "Interests.md").read_text()
    assert note.lower().count("alfred is used for generating reports") == 1


def test_duplicate_high_risk_fact_proposed_once(vault):
    f = "My mom lives in Addis Ababa"
    assert "Proposal created" in vault.register_fact("Family", f, "conversation")
    # Second attempt sees the pending proposal and dedupes — no second proposal.
    second = vault.register_fact("Family", f.upper(), "conversation")
    assert second.startswith("duplicate")


def test_fact_exists_matches_substring_and_normalized(vault):
    vault.register_fact("Interests", "I love reading sci-fi novels", "conversation")
    assert vault.fact_exists("Learning", "Interests", "i LOVE reading sci-fi novels.")
    assert not vault.fact_exists("Learning", "Interests", "I play chess on weekends")


def test_unknown_topic_defaults_to_proposal_not_silent_write(vault, tmp_path):
    # An unrecognized topic must NOT silently auto-write — it defaults to
    # Personal/medium which routes through the proposal flow.
    res = vault.register_fact("Mysterious", "I once climbed a mountain", "conversation")
    assert "Proposal created" in res
