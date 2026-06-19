"""P2 — money/approval gate to the owner's exact spec:
a money move at/above ~$100 ALWAYS confirms AND requires a fresh PIN to approve,
even for a present user. Smaller known amounts fall through to normal handling
(present-user executes; autonomous still confirms — no payment-splitting hole).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain import autonomy
from brain.tools import registry
from memory import memory, migrations
from security import identity


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "money.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    autonomy.set_paused(False)
    autonomy.set_away(False)
    yield p


def test_amount_parsing_and_needs_pin():
    assert autonomy._amount_usd({"amount": 120}) == 120
    assert autonomy._amount_usd({"amount": "$1,200.50"}) == 1200.50
    assert abs(autonomy._amount_usd({"amount": 13000, "currency": "ETB"}) - 100.0) < 1.0
    assert autonomy._amount_usd({"note": "no amount"}) is None
    assert autonomy.needs_pin("transfer_money", {"amount": 120}) is True
    assert autonomy.needs_pin("transfer_money", {"amount": 50}) is False
    assert autonomy.needs_pin("transfer_money", {}) is True          # unknown amount → fail safe
    assert autonomy.needs_pin("send_email", {"amount": 9999}) is False  # not a money tool


def test_big_money_confirms_with_pin_even_for_present_user(db):
    d = autonomy.gate("transfer_money", {"amount": 120}, source="user")  # present, home
    assert d["action"] == "confirm"
    assert "PIN" in d["reason"] or "pin" in d["reason"].lower()


def test_small_money_flows_for_present_user(db):
    d = autonomy.gate("transfer_money", {"amount": 50}, source="user")
    assert d["action"] == "execute"


def test_small_money_still_confirms_for_autonomous(db):
    # deliberately NOT loosened — autonomous small spend still confirms (anti payment-splitting)
    autonomy.set_autonomy_mode("auto")
    d = autonomy.gate("transfer_money", {"amount": 50}, source="autonomous")
    assert d["action"] == "confirm"


def test_approve_big_money_requires_correct_pin(db, monkeypatch):
    sink = {}
    monkeypatch.setattr(autonomy, "_MONEY_TOOLS", autonomy._MONEY_TOOLS | {"_pay_probe"})

    @registry.tool(description="pay probe", parameters={}, risk="red")
    def _pay_probe(amount=0):
        sink["paid"] = amount
        return f"paid {amount}"

    try:
        identity.set_pin("4321")
        d = autonomy.gate("_pay_probe", {"amount": 500}, source="user")
        assert d["action"] == "confirm"
        cid = d["confirm_id"]

        # no PIN → refused, not executed, stays pending
        out = autonomy.approve(cid)
        assert "paid" not in sink
        assert "PIN" in out
        assert memory.get_confirmation(cid)["status"] == "pending"

        # wrong PIN → still refused
        assert "paid" not in sink
        autonomy.approve(cid, pin="0000")
        assert "paid" not in sink

        # correct PIN → executes
        out = autonomy.approve(cid, pin="4321")
        assert sink.get("paid") == 500
    finally:
        registry.TOOL_REGISTRY.pop("_pay_probe", None)
