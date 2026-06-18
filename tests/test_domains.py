"""P6: people registry, contact-aware gate, and comms triage (model-free)."""
import pytest

from brain import autonomy
from brain.domains import comms
from memory import memory, migrations, people


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "domains.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    people.init_people()
    yield p


# ── people registry ──────────────────────────────────────────────────────────
def test_people_match_flags(db):
    people.add_person("Dad", "dad@family.com", family=True)
    people.add_person("Big Client", "ceo@bigco.com", vip=True)
    people.add_person("Spammer", "evil@spam.com", blocked=True)
    assert people.match("reply to dad@family.com")["family"] is True
    assert people.match("Dad")["family"] is True                  # name match
    assert people.match("ceo@bigco.com")["vip"] is True
    assert people.match("evil@spam.com")["blocked"] is True
    assert people.match("stranger@nowhere.com") == {"vip": False, "family": False, "blocked": False}


# ── contact-aware gate ─────────────────────────────────────────────────────────
def test_gate_blocks_send_to_blocked_contact_even_for_user(db):
    people.add_person("Ex", "ex@no.com", blocked=True)
    d = autonomy.gate("send_email", {"to": "ex@no.com"}, source="user", risk="red")
    assert d["action"] == "confirm"
    assert "blocklist" in d["reason"].lower()


def test_gate_vip_send_confirms_when_autonomous_but_not_when_present(db):
    people.add_person("Investor", "vc@fund.com", vip=True)
    # autonomous send to VIP → confirm
    assert autonomy.gate("send_email", {"to": "vc@fund.com"}, source="autonomous", risk="red")["action"] == "confirm"
    # user present (home) sending to VIP → not nagged (executes/no contact-confirm)
    autonomy.set_away(False)
    autonomy.set_autonomy_mode("auto")
    d = autonomy.gate("send_email", {"to": "vc@fund.com"}, source="user", risk="red")
    assert d["action"] == "execute"


def test_gate_normal_recipient_unaffected(db):
    autonomy.set_away(False)
    autonomy.set_autonomy_mode("auto")
    d = autonomy.gate("send_email", {"to": "colleague@work.com"}, source="user", risk="red")
    assert d["action"] == "execute"


# ── comms triage ──────────────────────────────────────────────────────────────
def test_classify_message(db):
    assert comms.classify_message("Your invoice is overdue, payment required", "billing@x.com") == "important"
    assert comms.classify_message("Unsubscribe from our newsletter, 50% off sale", "promo@x.com") == "spam"
    assert comms.classify_message("hey, are we still on for lunch?", "friend@x.com") == "routine"


def test_classify_vip_sender_is_important(db):
    people.add_person("Boss", "boss@co.com", vip=True)
    assert comms.classify_message("quick question about the doc", "boss@co.com") == "important"


def test_triage_routes_actions(db):
    msgs = [
        {"sender": "promo@x.com", "subject": "SALE", "body": "unsubscribe here, limited time"},
        {"sender": "client@x.com", "subject": "Contract", "body": "please review the contract deadline"},
        {"sender": "bud@x.com", "subject": "yo", "body": "wanna grab coffee"},
    ]
    actions = [d["action"] for d in comms.triage(msgs)]
    assert actions == ["archive", "escalate", "draft_reply"]
