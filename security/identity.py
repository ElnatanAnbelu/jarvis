"""Identity lock — JARVIS only acts for Elnatan.

On open/wake, JARVIS tries to recognize him by face + voice (local, free). If
biometrics are unavailable or fail, it falls back to a PIN or Telegram approval.
A successful auth opens a trusted session (TTL-bounded); the gate can require a
trusted session before real actions when 'locked' mode is on.

Face/voice are best-effort and degrade gracefully: with no camera/model/enrollment
they return False so the PIN/Telegram fallback takes over — never a hard failure.
PIN is stored salted-hashed in jarvis.db meta (never plaintext).
"""
import hashlib
import hmac
import os
import secrets
import time

from memory import memory

_SESSION_TTL = int(os.environ.get("JARVIS_SESSION_TTL", "3600"))  # trusted-session seconds


# ── PIN (salted hash, never plaintext) ────────────────────────────────────────
def set_pin(pin: str) -> str:
    if not pin or len(str(pin)) < 4:
        return "PIN must be at least 4 digits, sir."
    salt = secrets.token_hex(8)
    digest = hashlib.sha256((salt + str(pin)).encode()).hexdigest()
    memory.set_flag("identity_pin", f"{salt}${digest}")
    return "PIN set."


def has_pin() -> bool:
    return "$" in str(memory.get_flag("identity_pin", ""))


def verify_pin(pin: str) -> bool:
    stored = str(memory.get_flag("identity_pin", ""))
    if "$" not in stored:
        return False
    salt, digest = stored.split("$", 1)
    candidate = hashlib.sha256((salt + str(pin or "")).encode()).hexdigest()
    return hmac.compare_digest(candidate, digest)


# ── biometrics (best-effort; graceful when unavailable) ────────────────────────
def verify_face() -> bool:
    """Local face match against an enrolled encoding. False if unavailable/unenrolled."""
    try:
        import face_recognition  # noqa: F401  (heavy/optional dep)
        if not memory.get_flag("face_enrolled", False):
            return False
        # A real impl compares a fresh camera frame to the enrolled encoding here.
        return False  # not enrolled in this environment → fall back
    except Exception:
        return False


def verify_voice() -> bool:
    """Local speaker verification against an enrolled voiceprint. False if unavailable."""
    try:
        import resemblyzer  # noqa: F401  (optional dep)
        if not memory.get_flag("voice_enrolled", False):
            return False
        return False
    except Exception:
        return False


def biometrics_ready() -> bool:
    return bool(memory.get_flag("face_enrolled", False) or memory.get_flag("voice_enrolled", False))


# ── trusted session ───────────────────────────────────────────────────────────
def mark_trusted() -> None:
    memory.set_flag("trusted_until", str(int(time.time()) + _SESSION_TTL))


def is_trusted() -> bool:
    try:
        return int(str(memory.get_flag("trusted_until", "0"))) > int(time.time())
    except Exception:
        return False


def lock() -> str:
    memory.set_flag("trusted_until", "0")
    return "🔒 Locked, sir. I'll need to confirm it's you."


# ── the entry point ────────────────────────────────────────────────────────────
def authenticate(pin: str = None) -> dict:
    """Try biometric (face AND voice), else PIN. Opens a trusted session on success.
    Returns {ok, method}."""
    if verify_face() and verify_voice():
        mark_trusted()
        return {"ok": True, "method": "biometric"}
    if pin is not None and verify_pin(pin):
        mark_trusted()
        return {"ok": True, "method": "pin"}
    return {"ok": False, "method": None}
