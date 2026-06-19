"""Hard-stops (plan §3): Alfred holds a regrettable or self-doxxing send even for a
present owner, releasing it only with a PIN. Normal sends pass untouched."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain import judgment, autonomy
from memory import memory, migrations


# ── the detectors ────────────────────────────────────────────────────────────
def test_heated_message_is_a_hard_stop():
    h, r = judgment.is_hard_stop("send_email", {"body": "you're an idiot and I hate you"})
    assert h and "regret" in r.lower()


def test_normal_message_passes():
    h, _ = judgment.is_hard_stop("send_email", {"body": "Hi — attached is the report. Thanks, sir."})
    assert not h


def test_real_card_number_is_held():
    h, _ = judgment.is_hard_stop("send_imessage", {"message": "my card is 4111 1111 1111 1111"})
    assert h


def test_non_card_long_number_is_fine():
    # an order/reference number that isn't a valid card (fails Luhn) must NOT trip
    h, _ = judgment.is_hard_stop("send_imessage", {"message": "order ref 1234567890123456"})
    assert not h


def test_ssn_is_held():
    h, _ = judgment.is_hard_stop("send_email", {"body": "my ssn is 123-45-6789"})
    assert h


def test_non_outbound_tool_never_hard_stops():
    h, _ = judgment.is_hard_stop("read_file", {"path": "you're an idiot"})
    assert not h


# ── gate integration ─────────────────────────────────────────────────────────
@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "h.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    autonomy.set_paused(False)
    autonomy.set_away(False)
    yield p


def test_gate_holds_heated_send_even_for_present_owner(db):
    d = autonomy.gate("send_imessage", {"to": "friend", "body": "fuck you, never speak to me"}, source="user")
    assert d["action"] == "confirm"


def test_gate_lets_a_normal_send_through_for_owner(db):
    d = autonomy.gate("send_imessage", {"to": "friend", "body": "running late, there by six"}, source="user")
    assert d["action"] == "execute"


def test_approving_a_hard_stop_requires_the_pin(db):
    from security import identity
    identity.set_pin("4321")
    d = autonomy.gate("send_email", {"to": "x", "body": "you're pathetic and worthless"}, source="user")
    assert d["action"] == "confirm"
    cid = d["confirm_id"]
    assert "PIN" in autonomy.approve(cid)              # no PIN → held
    assert "PIN" not in autonomy.approve(cid, pin="4321")   # correct PIN → released
