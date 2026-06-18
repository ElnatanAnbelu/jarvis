"""P7-extra: greeting + goodnight/goodmorning rituals (model-free)."""
import datetime

import pytest

from brain import rituals
from memory import memory, migrations


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "rituals.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    yield p


def test_greeting_all_quiet(db):
    g = rituals.greeting()
    assert "sir" in g.lower()
    assert "quiet" in g.lower()


def test_greeting_surfaces_pending(db):
    memory.enqueue_confirmation("send_email", {"to": "x"}, reason="qa")
    memory.enqueue_confirmation("run_shell", {}, reason="qa")
    g = rituals.greeting()
    assert "2 items need" in g


def test_period_buckets(monkeypatch):
    class _FakeDT:
        @staticmethod
        def now():
            return datetime.datetime(2026, 1, 1, 8, 0)  # 8am → morning
    monkeypatch.setattr(rituals, "datetime", type("m", (), {"datetime": _FakeDT}))
    assert rituals._period() == "morning"


def test_goodnight_includes_digest(db):
    out = rituals.goodnight()
    assert "goodnight" in out.lower()
    assert "sir" in out.lower()
