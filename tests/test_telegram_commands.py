"""Unit tests for Telegram owner-command parsing and dispatch.

`parse_owner_command` is a pure function (no I/O), so the bulk of these tests
need no Telegram connection and no DB. The dispatch/owner-allowlist tests
monkeypatch the autonomy/memory boundary so they never touch the real DB.
"""
import pytest

import telegram_bot as tb


# ── parse_owner_command: command recognition ─────────────────────────────────
@pytest.mark.parametrize(
    "text,expected",
    [
        # no-arg commands
        ("pause", ("pause", None)),
        ("resume", ("resume", None)),
        ("away", ("away", None)),
        ("home", ("home", None)),
        ("back", ("home", None)),          # back normalizes to home
        ("status", ("status", None)),
        ("pending", ("pending", None)),
        # id commands carry their raw arg through
        ("approve 5", ("approve", "5")),
        ("reject 12", ("reject", "12")),
        ("undo 7", ("undo", "7")),
    ],
)
def test_parse_known_commands(text, expected):
    assert tb.parse_owner_command(text) == expected


def test_parse_is_case_insensitive():
    assert tb.parse_owner_command("PAUSE") == ("pause", None)
    assert tb.parse_owner_command("Approve 3") == ("approve", "3")
    assert tb.parse_owner_command("ReSuMe") == ("resume", None)


def test_parse_tolerates_leading_slash():
    assert tb.parse_owner_command("/pause") == ("pause", None)
    assert tb.parse_owner_command("/approve 9") == ("approve", "9")
    assert tb.parse_owner_command("/status") == ("status", None)


def test_parse_strips_surrounding_whitespace():
    assert tb.parse_owner_command("   pause  ") == ("pause", None)
    assert tb.parse_owner_command("  approve  4 ") == ("approve", "4")


def test_parse_id_command_with_missing_arg_returns_empty_arg():
    # The parser does NOT validate the int — it hands a (possibly empty) arg to
    # the dispatcher, which produces the usage hint.
    assert tb.parse_owner_command("approve") == ("approve", "")
    assert tb.parse_owner_command("undo") == ("undo", "")


def test_parse_id_command_with_nonnumeric_arg_passes_through():
    assert tb.parse_owner_command("approve abc") == ("approve", "abc")


# ── parse_owner_command: non-commands fall through to the router ──────────────
@pytest.mark.parametrize(
    "text",
    [
        "hello there",
        "what's the weather today",
        "send an email to bob",
        "pause the music please",     # 'pause' + trailing text is NOT a command
        "status of the project",      # 'status' + trailing text is NOT a command
        "homework is due",            # not 'home'
        "",
        "   ",
        "/",
        "/   ",
        "approval workflow",          # 'approve' substring must not match 'approval'
    ],
)
def test_parse_non_commands_return_none(text):
    assert tb.parse_owner_command(text) is None


# ── _handle_owner_command: dispatch (DB-isolated via monkeypatch) ─────────────
class _FakeAutonomy:
    def __init__(self):
        self.paused = False
        self.away = False
        self.mode = "supervised"

    def set_paused(self, v):
        self.paused = bool(v)

    def set_away(self, v):
        self.away = bool(v)

    def get_autonomy_mode(self):
        return self.mode

    def set_autonomy_mode(self, m):
        self.mode = "auto" if m == "auto" else "supervised"

    def panic(self, minutes=1440):
        self.paused = True
        return "🛑 PANIC — paused all autonomy."

    def is_paused(self):
        return self.paused

    def is_away(self):
        return self.away

    def approve(self, cid):
        return f"approved-{cid}"

    def reject(self, cid):
        return f"rejected-{cid}"

    def pending_summary(self):
        return "Nothing is waiting for approval."


class _FakeMemory:
    def revert_action(self, aid):
        return f"reverted-{aid}"


@pytest.fixture
def fake_modules(monkeypatch):
    """Patch the brain.autonomy / memory.memory modules that _handle_owner_command
    imports at call time, so no real DB is opened."""
    import sys
    auto = _FakeAutonomy()
    mem = _FakeMemory()
    # _handle_owner_command does `from brain import autonomy` / `from memory import
    # memory`, so patch the submodule attributes on the parent packages.
    import brain
    import memory as memory_pkg
    monkeypatch.setattr(brain, "autonomy", auto, raising=False)
    monkeypatch.setattr(memory_pkg, "memory", mem, raising=False)
    monkeypatch.setitem(sys.modules, "brain.autonomy", auto)
    monkeypatch.setitem(sys.modules, "memory.memory", mem)
    return auto, mem


def test_dispatch_pause_resume(fake_modules):
    auto, _ = fake_modules
    assert "Paused" in tb._handle_owner_command("pause", None)
    assert auto.paused is True
    assert "Resumed" in tb._handle_owner_command("resume", None)
    assert auto.paused is False


def test_dispatch_away_home(fake_modules):
    auto, _ = fake_modules
    assert "Away-mode ON" in tb._handle_owner_command("away", None)
    assert auto.away is True
    assert "Away-mode OFF" in tb._handle_owner_command("home", None)
    assert auto.away is False


def test_dispatch_status_reports_state(fake_modules):
    auto, _ = fake_modules
    auto.paused = True
    auto.away = False
    out = tb._handle_owner_command("status", None)
    assert "Paused: yes" in out
    assert "Away: no" in out
    assert "Nothing is waiting" in out


def test_dispatch_approve_reject_undo(fake_modules):
    assert tb._handle_owner_command("approve", "5") == "approved-5"
    assert tb._handle_owner_command("reject", "8") == "rejected-8"
    assert tb._handle_owner_command("undo", "2") == "reverted-2"


def test_dispatch_bad_id_returns_usage_hint(fake_modules):
    for cmd in ("approve", "reject", "undo"):
        out = tb._handle_owner_command(cmd, "notanumber")
        assert out.startswith(f"Usage: {cmd} <id>")
        out_empty = tb._handle_owner_command(cmd, "")
        assert out_empty.startswith(f"Usage: {cmd} <id>")


# ── _is_owner: allowlist behavior (finding C4) ────────────────────────────────
def test_is_owner_allows_when_no_owner_configured(monkeypatch, tmp_path):
    monkeypatch.delenv("OWNER_CHAT_ID", raising=False)
    monkeypatch.setattr(tb, "_chat_id", None, raising=False)
    # Point .env lookup at an env file with no TELEGRAM_CHAT_ID.
    env = tmp_path / ".env"
    env.write_text("TELEGRAM_BOT_TOKEN=x\n")
    monkeypatch.setattr(tb, "__file__", str(tmp_path / "telegram_bot.py"))
    assert tb._is_owner(123) is True


def test_is_owner_honors_explicit_env_owner(monkeypatch):
    monkeypatch.setenv("OWNER_CHAT_ID", "999")
    assert tb._is_owner(999) is True
    assert tb._is_owner("999") is True
    assert tb._is_owner(123) is False


def test_is_owner_locks_to_persisted_chat_id(monkeypatch, tmp_path):
    monkeypatch.delenv("OWNER_CHAT_ID", raising=False)
    monkeypatch.setattr(tb, "_chat_id", None, raising=False)
    env = tmp_path / ".env"
    env.write_text("TELEGRAM_CHAT_ID=555\n")
    monkeypatch.setattr(tb, "__file__", str(tmp_path / "telegram_bot.py"))
    assert tb._is_owner(555) is True
    assert tb._is_owner(777) is False
