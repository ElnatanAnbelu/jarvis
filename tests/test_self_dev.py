"""P3 — the gated self-dev SAFETY FRAME.

Alfred may extend its own code ONLY when a present owner asks, and NEVER touch its
own gate / identity / secrets, and NEVER from an autonomous or injected trigger.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain import self_dev
from memory import memory, migrations


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "selfdev.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    yield p


def test_authorize_owner_only():
    self_dev.authorize("user", identity_verified=True)  # ok, no raise
    for bad in ("autonomous", "external", "injected"):
        with pytest.raises(self_dev.SelfDevDenied):
            self_dev.authorize(bad)
    with pytest.raises(self_dev.SelfDevDenied):
        self_dev.authorize("user", identity_verified=False)


def test_protected_paths_off_limits():
    for p in ("brain/autonomy.py", "brain/self_dev.py", "security/identity.py",
              "security/vault.py", ".env", ".session_token", "control/files.py"):
        assert self_dev.is_protected(p), p
    for p in ("brain/tools/web.py", "ui/server.py", "brain/agent.py", "a/new/feature.py"):
        assert not self_dev.is_protected(p), p


def test_request_change_owner_nonprotected_is_queued(db):
    out = self_dev.request_change("brain/tools/new_skill.py", "add a new skill", source="user")
    assert out["action"] == "proposed"
    assert out["confirm_id"]
    assert len(memory.get_pending_confirmations()) == 1


def test_request_change_refuses_protected_even_for_owner(db):
    with pytest.raises(self_dev.SelfDevDenied):
        self_dev.request_change("brain/autonomy.py", "neuter the gate", source="user")
    assert len(memory.get_pending_confirmations()) == 0  # nothing queued


def test_request_change_refuses_non_owner(db):
    for bad in ("autonomous", "external"):
        with pytest.raises(self_dev.SelfDevDenied):
            self_dev.request_change("brain/tools/x.py", "injected change", source=bad)
    assert len(memory.get_pending_confirmations()) == 0


def test_request_change_refuses_outside_repo(db):
    with pytest.raises(self_dev.SelfDevDenied):
        self_dev.request_change("/tmp/evil.py", "escape the repo", source="user")
    with pytest.raises(self_dev.SelfDevDenied):
        self_dev.request_change(str(Path.home() / ".bashrc"), "touch home dotfiles", source="user")
