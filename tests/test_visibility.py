"""Tests for brain/visibility.py — Smart Visibility classification."""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.visibility import classify


# ── SURFACE rules ─────────────────────────────────────────────────────────────

def test_classifier_surfaces_jarvis_brain_saved():
    result = classify("Note created. [BRAIN: SAVED → Learning/Atomic Habits]",
                      agent="JARVIS")
    assert result["visibility"] == "surface"
    assert any("SAVED" in t for t in result["tags"])


def test_classifier_surfaces_jarvis_brain_proposed():
    result = classify("Proposal staged. [BRAIN: PROPOSED → Relationships/Solomon]",
                      agent="JARVIS")
    assert result["visibility"] == "surface"


def test_classifier_surfaces_sensitive_tag():
    result = classify("Three risk factors here. [SENSITIVE]",
                      agent="VERONICA")
    assert result["visibility"] == "surface"
    assert "SENSITIVE" in result["tags"]


def test_classifier_surfaces_destructive_delete_file():
    result = classify("Confirming delete_file at ~/Desktop/old.md, sir. Proceed?",
                      agent="JARVIS")
    assert result["visibility"] == "surface"
    assert any("TIER3" in t for t in result["tags"])


def test_classifier_surfaces_git_push():
    result = classify("About to git push origin main with 3 commits.",
                      agent="JARVIS")
    assert result["visibility"] == "surface"


def test_classifier_surfaces_send_message():
    result = classify("Sending email to mom: 'Happy birthday'. Proceed?",
                      agent="JARVIS")
    assert result["visibility"] == "surface"


def test_classifier_surfaces_personal_model_reference():
    result = classify("Calling update_personal_model with Energy Patterns.",
                      agent="JARVIS")
    assert result["visibility"] == "surface"
    assert any("PERSONAL_MODEL" in t for t in result["tags"])


def test_classifier_surfaces_observer_insight():
    result = classify("[OBS] You've returned to vendor pricing four times today.",
                      agent="JARVIS", source="observer")
    assert result["visibility"] == "surface"
    assert "OBSERVER" in result["tags"]


# ── COLLAPSED rules ───────────────────────────────────────────────────────────

def test_classifier_collapses_brain_suggest_from_friday():
    result = classify("[BRAIN: suggest → Learning: he's reading Atomic Habits]",
                      agent="FRIDAY")
    assert result["visibility"] == "collapsed"


def test_classifier_collapses_brain_suggest_from_karen():
    result = classify("[BRAIN: suggest → Personal Model: Energy Patterns — late-night work]",
                      agent="KAREN")
    assert result["visibility"] == "collapsed"


def test_classifier_does_NOT_collapse_brain_suggest_from_jarvis():
    """JARVIS's own response shouldn't collapse even if it contains a suggest tag."""
    result = classify("[BRAIN: suggest → Learning]",
                      agent="JARVIS")
    # JARVIS using suggest is weird but shouldn't collapse — falls through to normal
    assert result["visibility"] != "collapsed"


def test_classifier_collapses_jarvis_territory_deferral():
    result = classify("That's JARVIS territory.", agent="FRIDAY")
    assert result["visibility"] == "collapsed"


def test_classifier_collapses_handing_off_to_jarvis():
    result = classify("Handing this off to JARVIS.", agent="VERONICA")
    assert result["visibility"] == "collapsed"


def test_classifier_collapses_one_word_noted():
    result = classify("Noted.", agent="JARVIS")
    assert result["visibility"] == "collapsed"


def test_classifier_collapses_got_it():
    result = classify("Got it.", agent="FRIDAY")
    assert result["visibility"] == "collapsed"


# ── NORMAL rules ──────────────────────────────────────────────────────────────

def test_classifier_default_is_normal():
    result = classify("Three options here, sir. The first is straightforward.",
                      agent="JARVIS")
    assert result["visibility"] == "normal"
    assert result["tags"] == []


def test_classifier_searched_alone_does_not_surface():
    """SEARCHED is read-only — should surface or normal but not be hidden.
    Per the spec, BRAIN:SEARCHED is a JARVIS brain action so it surfaces."""
    result = classify("Pulled the gym note. [BRAIN: SEARCHED]", agent="JARVIS")
    # Per current rules, any JARVIS brain tag (except suggest) is a write/action
    # SEARCHED is also a JARVIS-driven brain interaction; it surfaces.
    assert result["visibility"] == "surface"


def test_classifier_normal_with_no_tags():
    result = classify("Online, sir. What do you need?", agent="JARVIS")
    assert result["visibility"] == "normal"
    assert result["tags"] == []


def test_classifier_handles_empty_text():
    result = classify("")
    assert result["visibility"] == "normal"
    assert result["tags"] == []


def test_classifier_handles_none_agent():
    result = classify("Some response without agent context.")
    assert result["visibility"] == "normal"


# ── Tag extraction ────────────────────────────────────────────────────────────

def test_tags_extracted_from_brain_tag():
    result = classify("Done. [BRAIN: SAVED → Learning/Open]", agent="JARVIS")
    assert any("SAVED" in t and "Learning/Open" in t for t in result["tags"])


def test_tags_extracted_from_sensitive():
    result = classify("Analysis here. [SENSITIVE]", agent="VERONICA")
    assert "SENSITIVE" in result["tags"]


def test_multiple_tags_extracted():
    result = classify(
        "Proposal staged. [BRAIN: PROPOSED → Business/Solomon] [SENSITIVE]",
        agent="JARVIS",
    )
    assert "SENSITIVE" in result["tags"]
    assert any("PROPOSED" in t for t in result["tags"])
