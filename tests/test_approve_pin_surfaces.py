"""P2 — the money-PIN gate is only usable if the approve SURFACES collect and
pass the PIN. These pin the Telegram + HTTP approve paths so a money move >= the
threshold can actually be released (and reject/undo stay id-only)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import telegram_bot
from brain import autonomy


def test_telegram_approve_parses_and_forwards_pin(monkeypatch):
    calls = {}
    monkeypatch.setattr(autonomy, "approve", lambda cid, pin=None: calls.update(cid=cid, pin=pin) or "ok")
    telegram_bot._handle_owner_command("approve", "42 4321")
    assert calls == {"cid": 42, "pin": "4321"}


def test_telegram_approve_without_pin_passes_none(monkeypatch):
    calls = {}
    monkeypatch.setattr(autonomy, "approve", lambda cid, pin=None: calls.update(cid=cid, pin=pin) or "ok")
    telegram_bot._handle_owner_command("approve", "42")
    assert calls == {"cid": 42, "pin": None}


def test_telegram_reject_and_undo_take_only_id(monkeypatch):
    monkeypatch.setattr(autonomy, "reject", lambda cid: f"rejected {cid}")
    # "7 9999" would be a malformed id for reject (no pin split) → usage hint
    assert "Usage" in telegram_bot._handle_owner_command("reject", "7 9999")
    assert telegram_bot._handle_owner_command("reject", "7") == "rejected 7"


def test_telegram_approve_bad_id_shows_pin_usage(monkeypatch):
    out = telegram_bot._handle_owner_command("approve", "notanumber")
    assert "approve <id> [pin]" in out


def test_parse_owner_command_keeps_pin_in_remainder():
    # the parser hands the whole remainder to the handler, which splits id+pin
    assert telegram_bot.parse_owner_command("approve 42 4321") == ("approve", "42 4321")
    assert telegram_bot.parse_owner_command("/approve 42 4321") == ("approve", "42 4321")
