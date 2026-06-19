"""The setup wizard's only non-interactive logic: idempotent .env writes. The
prompt-driven sections aren't unit-tested (pure I/O), but _set_env_var is the part
that can silently corrupt config, so it's pinned."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent))

import setup


def test_set_env_var_adds_new_key(tmp_path):
    env = tmp_path / ".env"
    env.write_text("EXISTING=1\n")
    added = setup._set_env_var(env, "ALFRED_IMESSAGE_OWNER", "+14155551212")
    assert added is False  # newly added
    text = env.read_text()
    assert "EXISTING=1" in text
    assert "ALFRED_IMESSAGE_OWNER=+14155551212" in text


def test_set_env_var_updates_existing_key_in_place(tmp_path):
    env = tmp_path / ".env"
    env.write_text("A=1\nALFRED_IMESSAGE_OWNER=old\nB=2\n")
    updated = setup._set_env_var(env, "ALFRED_IMESSAGE_OWNER", "new@icloud.com")
    assert updated is True
    lines = env.read_text().splitlines()
    assert "ALFRED_IMESSAGE_OWNER=new@icloud.com" in lines
    assert "ALFRED_IMESSAGE_OWNER=old" not in lines
    # other keys preserved, no duplication
    assert lines.count("A=1") == 1 and lines.count("B=2") == 1
    assert sum(1 for l in lines if l.startswith("ALFRED_IMESSAGE_OWNER=")) == 1


def test_set_env_var_creates_file_if_missing(tmp_path):
    env = tmp_path / "nope.env"
    setup._set_env_var(env, "K", "v")
    assert env.exists() and "K=v" in env.read_text()
