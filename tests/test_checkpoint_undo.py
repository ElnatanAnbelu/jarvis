"""P4 — checkpointed autonomous jobs: undo everything done AFTER a checkpoint
(undo-the-whole-job), without touching what came before it."""
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain import autonomy
from brain.tools import registry
from memory import memory, migrations


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "cp.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    autonomy.set_paused(False)
    autonomy.set_away(False)
    yield p


def test_revert_since_only_touches_after_checkpoint(db):
    d = Path(tempfile.mkdtemp())
    f1, f2 = d / "before.txt", d / "after.txt"
    f1.write_text("ORIG_A")
    f2.write_text("ORIG_B")

    registry.execute_tool("write_file", {"path": str(f1), "content": "NEW_A"}, source="user")
    cp = memory.max_action_id()                      # checkpoint AFTER the first write
    registry.execute_tool("write_file", {"path": str(f2), "content": "NEW_B"}, source="user")

    out = memory.revert_since(cp)
    assert "reverted 1" in out
    assert f1.read_text() == "NEW_A"                 # before the checkpoint — untouched
    assert f2.read_text() == "ORIG_B"                # after the checkpoint — undone


def test_undo_last_job_tool(db):
    d = Path(tempfile.mkdtemp())
    f = d / "job.txt"
    f.write_text("ORIG")
    memory.set_flag("last_job_checkpoint", memory.max_action_id())  # job starts here
    registry.execute_tool("write_file", {"path": str(f), "content": "JOB_EDIT"}, source="user")
    assert f.read_text() == "JOB_EDIT"
    out = registry.execute_tool("tool_undo_last_job", {}, source="user")
    assert "reverted" in out.lower()
    assert f.read_text() == "ORIG"                   # the whole job rolled back


def test_undo_last_job_no_checkpoint(db):
    out = registry.execute_tool("tool_undo_last_job", {}, source="user")
    assert "no autonomous job checkpoint" in out.lower()
