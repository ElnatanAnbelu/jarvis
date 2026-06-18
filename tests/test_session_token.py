"""Regression: the session token must PERSIST across restarts so already-open
clients (orb/HUD/control room) don't get silently 403'd → JARVIS appears mute.
(The bug: token was regenerated every process start.)"""
import os
import stat

import session_token


def test_token_persists_across_calls(tmp_path):
    p = tmp_path / ".session_token"
    t1 = session_token.load_or_create_token(p)
    t2 = session_token.load_or_create_token(p)   # simulates a server restart
    assert t1 and t1 == t2                         # same token survives "restart"


def test_token_file_is_locked_down(tmp_path):
    p = tmp_path / ".session_token"
    session_token.load_or_create_token(p)
    assert p.exists()
    assert stat.S_IMODE(os.stat(p).st_mode) == 0o600  # owner-only


def test_token_is_strong(tmp_path):
    t = session_token.load_or_create_token(tmp_path / ".session_token")
    assert len(t) >= 32
