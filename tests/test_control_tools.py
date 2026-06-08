"""
Tests for the safety-control tools in brain/tools/control_tools.py:
  - tool_pause / tool_resume flip the autonomy paused kill-switch
  - tool_set_away parses on/off and flips away-mode
  - tool_safety_status returns a human-readable string
  - tool_undo on a bogus id returns a clean message (no crash)
  - the tools self-register in TOOL_REGISTRY on import

DB isolation mirrors tests/test_safety_ledger.py: memory.memory.DB_PATH (and the
migrations module's stale import-time copy) are pointed at a per-test temp file,
so the real jarvis.db is never touched. Autonomy state lives in that DB via
get_flag/set_flag, so patching DB_PATH fully isolates pause/away state too.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mem(tmp_path, monkeypatch):
    """Fresh, migrated, fully isolated memory module bound to a temp DB."""
    import memory.memory as m
    import memory.migrations as mig

    db = tmp_path / "jarvis_test.db"
    monkeypatch.setattr(m, "DB_PATH", db)
    monkeypatch.setattr(mig, "DB_PATH", db)
    m.init_db()
    return m


# ── pause / resume ─────────────────────────────────────────────────────────--

def test_pause_sets_paused_true(mem):
    from brain import autonomy
    from brain.tools.control_tools import tool_pause

    assert autonomy.is_paused() is False  # clean temp DB starts unpaused
    msg = tool_pause()
    assert isinstance(msg, str) and msg
    assert autonomy.is_paused() is True


def test_resume_sets_paused_false(mem):
    from brain import autonomy
    from brain.tools.control_tools import tool_pause, tool_resume

    tool_pause()
    assert autonomy.is_paused() is True
    msg = tool_resume()
    assert isinstance(msg, str) and msg
    assert autonomy.is_paused() is False


# ── away-mode ────────────────────────────────────────────────────────────────

def test_set_away_on(mem):
    from brain import autonomy
    from brain.tools.control_tools import tool_set_away

    assert autonomy.is_away() is False
    msg = tool_set_away("on")
    assert isinstance(msg, str) and msg
    assert autonomy.is_away() is True


def test_set_away_off(mem):
    from brain import autonomy
    from brain.tools.control_tools import tool_set_away

    tool_set_away("on")
    assert autonomy.is_away() is True
    tool_set_away("off")
    assert autonomy.is_away() is False


@pytest.mark.parametrize("on_value", [True, 1, "yes", "true", "1", "Away"])
def test_set_away_truthy_variants(mem, on_value):
    from brain import autonomy
    from brain.tools.control_tools import tool_set_away

    tool_set_away(on_value)
    assert autonomy.is_away() is True


@pytest.mark.parametrize("off_value", [False, 0, "no", "false", "0", "off", ""])
def test_set_away_falsy_variants(mem, off_value):
    from brain import autonomy
    from brain.tools.control_tools import tool_set_away

    tool_set_away("on")  # ensure it actually has to turn off
    tool_set_away(off_value)
    assert autonomy.is_away() is False


# ── safety status ────────────────────────────────────────────────────────────

def test_safety_status_returns_string(mem):
    from brain.tools.control_tools import tool_safety_status

    out = tool_safety_status()
    assert isinstance(out, str)
    assert out  # non-empty


def test_safety_status_reflects_state(mem):
    from brain.tools.control_tools import tool_pause, tool_set_away, tool_safety_status

    tool_pause()
    tool_set_away("on")
    out = tool_safety_status()
    assert "paused: yes" in out
    assert "away-mode: yes" in out


# ── undo ─────────────────────────────────────────────────────────────────────

def test_undo_bogus_id_clean_message(mem):
    from brain.tools.control_tools import tool_undo

    out = tool_undo(999999)
    assert isinstance(out, str)
    assert "no action found" in out.lower()


def test_undo_non_numeric_id_clean_message(mem):
    from brain.tools.control_tools import tool_undo

    out = tool_undo("not-a-number")
    assert isinstance(out, str) and out  # no crash, clean message


# ── registration ─────────────────────────────────────────────────────────────

def test_tools_register():
    import brain.tools  # noqa: F401 — triggers package import / self-registration
    from brain.tools.registry import TOOL_REGISTRY

    for name in ("tool_undo", "tool_pause", "tool_resume",
                 "tool_set_away", "tool_safety_status"):
        assert name in TOOL_REGISTRY
        entry = TOOL_REGISTRY[name]
        assert entry["risk"] == "low"
        assert entry["allowed_agents"] == ["JARVIS"]
