"""Persistent session token for the local server.

The auth token used to be regenerated on every process start
(`secrets.token_urlsafe(32)`), which silently 403'd any already-open client
(the orb / HUD / control room) after a restart — JARVIS would appear mute even
though the brain was fine. We persist it to a gitignored 0600 file so a restart
keeps the same token and open clients keep working. It's still required on every
API call and same-origin is still enforced — this only stops self-inflicted
lockouts across restarts.
"""
import os
import secrets
from pathlib import Path

_DEFAULT_PATH = Path(__file__).resolve().parent / ".session_token"


def load_or_create_token(path=None) -> str:
    p = Path(path) if path else _DEFAULT_PATH
    try:
        if p.exists():
            tok = p.read_text().strip()
            if tok:
                return tok
    except Exception:
        pass
    tok = secrets.token_urlsafe(32)
    try:
        p.write_text(tok)
        os.chmod(p, 0o600)
    except Exception:
        pass
    return tok
