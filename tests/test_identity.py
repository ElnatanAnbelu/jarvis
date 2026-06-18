"""P3: identity lock — PIN, trusted session, graceful biometrics (model-free)."""
import pytest

from security import identity
from memory import memory, migrations


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "identity.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    yield p


def test_pin_set_and_verify(db):
    assert "set" in identity.set_pin("1234").lower()
    assert identity.has_pin() is True
    assert identity.verify_pin("1234") is True
    assert identity.verify_pin("0000") is False


def test_pin_rejects_too_short(db):
    out = identity.set_pin("12")
    assert "4" in out
    assert identity.has_pin() is False


def test_pin_stored_hashed_not_plaintext(db):
    identity.set_pin("7777")
    stored = str(memory.get_flag("identity_pin", ""))
    assert "7777" not in stored and "$" in stored  # salted hash, not the PIN


def test_authenticate_pin_opens_session(db):
    identity.set_pin("4321")
    res = identity.authenticate(pin="4321")
    assert res["ok"] is True and res["method"] == "pin"
    assert identity.is_trusted() is True
    assert identity.authenticate(pin="9999")["ok"] is False


def test_lock_clears_trust(db):
    identity.set_pin("4321")
    identity.authenticate(pin="4321")
    assert identity.is_trusted() is True
    identity.lock()
    assert identity.is_trusted() is False


def test_biometrics_degrade_gracefully(db):
    # No camera / model / enrollment in this environment → False, never crashes.
    assert identity.verify_face() is False
    assert identity.verify_voice() is False
    # with neither biometric nor pin, auth fails cleanly
    assert identity.authenticate()["ok"] is False
