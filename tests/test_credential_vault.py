"""P7 — the local credential vault core. Uses the in-memory backend (so tests
never touch the real Keychain). Asserts put/get/has/delete/list, that list_names
exposes NAMES not secrets, and that missing lookups return None."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from security import vault


@pytest.fixture(autouse=True)
def mem_backend(monkeypatch):
    # never touch the real macOS Keychain in tests
    monkeypatch.setattr(vault, "_backend", vault._MemoryBackend())


def test_put_get_roundtrip():
    vault.put("gmail_oauth", "super-secret-token-123")
    assert vault.get("gmail_oauth") == "super-secret-token-123"
    assert vault.has("gmail_oauth")


def test_missing_returns_none():
    assert vault.get("does_not_exist") is None
    assert vault.has("does_not_exist") is False


def test_list_names_exposes_names_not_secrets():
    vault.put("gmail_oauth", "tok-A")
    vault.put("whatsapp_token", "tok-B")
    names = vault.list_names()
    assert "gmail_oauth" in names and "whatsapp_token" in names
    # the listing must never contain the secret values
    assert "tok-A" not in names and "tok-B" not in names


def test_put_confirmation_never_leaks_the_secret():
    out = vault.put("notion_token", "ntn_PLAINTEXT_SECRET")
    assert "ntn_PLAINTEXT_SECRET" not in out


def test_delete():
    vault.put("temp", "x")
    assert vault.has("temp")
    vault.delete("temp")
    assert not vault.has("temp")
    assert vault.get("temp") is None


def test_put_requires_name_and_secret():
    assert "required" in vault.put("", "x").lower()
