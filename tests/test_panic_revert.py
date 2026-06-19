"""Regression: panic/revert robustness (second-audit P2).

- A revert's compensating action must not itself be reversible, or a second
  panic re-reverts it and oscillates the system back to the dangerous state.
- revert_recent must report the count that ACTUALLY applied, not len(ids), and
  must leave a row un-reverted (retryable) when its inverse failed.
"""
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain import autonomy
from brain.tools import registry
from memory import memory, migrations

ROOT = Path(__file__).parent.parent


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "panic.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    autonomy.set_autonomy_mode("auto")
    autonomy.set_away(False)
    autonomy.set_paused(False)
    yield p


def test_double_panic_does_not_oscillate(db, tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("BEFORE")
    registry.execute_tool("write_file", {"path": str(f), "content": "AFTER"}, source="user")
    assert f.read_text() == "AFTER"

    assert "reverted 1" in memory.revert_recent(60)
    assert f.read_text() == "BEFORE"
    # second + third panic must find nothing — the revert isn't itself reversible
    assert "no reversible actions" in memory.revert_recent(60)
    assert f.read_text() == "BEFORE"
    assert "no reversible actions" in memory.revert_recent(60)
    assert f.read_text() == "BEFORE"


def test_revert_count_is_honest_on_failure(db):
    # Log an action whose recorded inverse will FAIL: writing into the install
    # tree is refused by the self-write firewall.
    memory.log_action(
        "write_file", {"path": "x"}, "ok", success=True,
        inverse_tool="write_file",
        inverse_args={"path": str(ROOT / "brain" / "autonomy.py"), "content": "x"},
    )
    out = memory.revert_recent(60)
    assert "reverted 0 of 1" in out, out
    # the row stays un-reverted so it can be retried, not falsely marked done
    again = memory.revert_recent(60)
    assert "0 of 1" in again
