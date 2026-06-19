"""Owner-operator autonomy (the user's explicit choice): local code + computer
control run frictionlessly FOR HIM, even in away-mode — but injected/external
content can never run them, autonomous use respects the domain flag, and money /
outward actions still confirm. This is the safety-critical balance, so it's pinned."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain import autonomy
from memory import memory, migrations


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "oa.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    autonomy.set_paused(False)
    autonomy.set_away(False)
    autonomy.set_autonomy_mode("supervised")
    yield p


def test_owner_runs_code_no_confirm(db):
    d = autonomy.gate("execute_code", {"language": "python", "code": "print(1)"}, source="user")
    assert d["action"] == "execute"


def test_owner_runs_code_even_when_away(db):
    autonomy.set_away(True)
    d = autonomy.gate("execute_code", {"language": "python", "code": "print(1)"}, source="user")
    assert d["action"] == "execute"  # it's still HIM asking


def test_owner_controls_screen_no_confirm(db):
    d = autonomy.gate("control_screen", {"action": "click", "x": 10, "y": 10}, source="user")
    assert d["action"] == "execute"


def test_external_code_always_confirms(db):
    # a poisoned email / web page can NEVER run code, even with the owner present
    d = autonomy.gate("execute_code", {"language": "python", "code": "rm -rf"}, source="external")
    assert d["action"] == "confirm"


def test_autonomous_code_confirms_when_supervised(db):
    d = autonomy.gate("run_shell", {"cmd": "ls"}, source="autonomous")
    assert d["action"] == "confirm"


def test_autonomous_code_executes_when_domain_auto(db):
    autonomy.set_domain_mode("system", "auto")   # owner flips the operator domain on
    d = autonomy.gate("execute_code", {"language": "python", "code": "print(1)"}, source="autonomous")
    assert d["action"] == "execute"


# ── the floor still holds ────────────────────────────────────────────────────
def test_money_still_confirms_for_owner(db):
    d = autonomy.gate("transfer_money", {"amount": 200}, source="user")
    assert d["action"] == "confirm"


def test_outward_send_still_confirms_when_away(db):
    autonomy.set_away(True)
    d = autonomy.gate("send_email", {"to": "a@b.com", "body": "hi"}, source="user")
    assert d["action"] == "confirm"  # send_* is NOT an owner-auto tool


def test_delete_not_frictionless_for_external(db):
    d = autonomy.gate("delete_file", {"path": "/tmp/x"}, source="external")
    assert d["action"] == "confirm"
