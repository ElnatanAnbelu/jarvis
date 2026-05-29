"""Tests for brain/observer.py — classified push path (Phase 1 / B6+B7)."""
import queue
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import brain.observer as obs


def _make_queue():
    q = queue.Queue()
    obs._hud_queue = q
    # Reset rate-limit state so _can_push() returns True
    obs._last_push_at = None
    obs._push_count_this_hour = 0
    obs._push_hour = -1
    return q


# ── _push() emits a classified dict ──────────────────────────────────────────

def test_push_emits_dict_not_string():
    q = _make_queue()
    obs._push("[OBS] Test insight.", "surface", ["OBSERVER"])
    item = q.get_nowait()
    assert isinstance(item, dict), "push must emit a dict, not a plain string"


def test_push_dict_has_required_keys():
    q = _make_queue()
    obs._push("[OBS] Something notable.", "surface", ["OBSERVER"])
    item = q.get_nowait()
    assert "text" in item
    assert "visibility" in item
    assert "tags" in item
    assert "agent" in item
    assert "source" in item


def test_push_text_is_preserved():
    q = _make_queue()
    obs._push("[OBS] Vendor pricing keeps coming up.", "surface", ["OBSERVER"])
    item = q.get_nowait()
    assert item["text"] == "[OBS] Vendor pricing keeps coming up."


def test_push_visibility_is_preserved():
    q = _make_queue()
    obs._push("[OBS] Some insight.", "surface", ["OBSERVER"])
    item = q.get_nowait()
    assert item["visibility"] == "surface"


def test_push_tags_are_preserved():
    q = _make_queue()
    obs._push("[OBS] Grounded insight. [BRAIN: GROUNDED]", "surface", ["OBSERVER", "BRAIN:GROUNDED"])
    item = q.get_nowait()
    assert "OBSERVER" in item["tags"]
    assert "BRAIN:GROUNDED" in item["tags"]


def test_push_agent_and_source_are_correct():
    q = _make_queue()
    obs._push("[OBS] Any insight.", "surface", [])
    item = q.get_nowait()
    assert item["agent"] == "JARVIS"
    assert item["source"] == "observer"


def test_push_default_visibility_is_surface():
    """When no visibility arg is given, default is surface (observer insights always surface)."""
    q = _make_queue()
    obs._push("[OBS] Any insight.")
    item = q.get_nowait()
    assert item["visibility"] == "surface"


# ── _push() integrates correctly with visibility classifier ──────────────────

def test_obs_prefix_is_classified_as_surface():
    """[OBS] prefix should trigger surface visibility per brain/visibility.py rules."""
    from brain.visibility import classify
    result = classify("[OBS] You've returned to vendor pricing four times today.",
                      agent="JARVIS", source="observer")
    assert result["visibility"] == "surface"
    assert "OBSERVER" in result["tags"]


def test_grounded_insight_carries_brain_tag():
    """[BRAIN: GROUNDED] in observer text → BRAIN tag extracted by classifier."""
    from brain.visibility import classify
    result = classify(
        "[OBS] Your reading note for Atomic Habits is still on chapter three. [BRAIN: GROUNDED]",
        agent="JARVIS", source="observer"
    )
    assert result["visibility"] == "surface"
    assert any("GROUNDED" in t for t in result["tags"])


# ── Rate-limit guard — _push() respects _can_push() ─────────────────────────

def test_push_does_nothing_when_queue_is_none():
    obs._hud_queue = None
    # Should not raise
    obs._push("[OBS] Test.", "surface", [])
    obs._hud_queue = None  # leave clean


def test_push_increments_count():
    q = _make_queue()
    before = obs._push_count_this_hour
    obs._push("[OBS] Insight one.", "surface", [])
    assert obs._push_count_this_hour == before + 1
    q.get_nowait()  # drain
