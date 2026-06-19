"""P7 — Encrypted local credential vault.

The OWNER fills this with his service credentials; Alfred can USE them to act on
his behalf, but the self-dev firewall keeps the AI from modifying or exfiltrating
the vault (security/vault.py is in self_dev._PROTECTED). Fully local — secrets
NEVER leave the machine, are NEVER logged, and NEVER go to the cloud.

Backend: the macOS Keychain (OS-encrypted, login-protected) via the `security`
CLI — no third-party crypto dependency. On non-macOS / when the Keychain is
unavailable it falls back to a NON-persistent in-memory store so dev/CI works
without writing real secrets anywhere (that fallback warns and is never the
real backing store).

Note: `security add-generic-password -w <secret>` passes the value as an argv —
acceptable on a single-user personal Mac (local, brief); a stdin-fed variant is a
hardening follow-up. The vault stores only a names INDEX in plaintext (never the
secret values) so list_names()/has() work; the values live in the Keychain.
"""
import json
import subprocess
import sys

_SERVICE = "jarvis-alfred-vault"
_INDEX = "__index__"


class _MemoryBackend:
    """Non-persistent in-memory store (tests / non-mac dev). Never for real use."""

    def __init__(self):
        self._d = {}

    def put(self, name, secret):
        self._d[name] = secret

    def get(self, name):
        return self._d.get(name)

    def delete(self, name):
        self._d.pop(name, None)


class _KeychainBackend:
    """macOS Keychain via the `security` CLI — OS-encrypted, login-protected."""

    def put(self, name, secret):
        subprocess.run(
            ["security", "add-generic-password", "-a", name, "-s", _SERVICE, "-w", secret, "-U"],
            check=True, capture_output=True,
        )

    def get(self, name):
        r = subprocess.run(
            ["security", "find-generic-password", "-a", name, "-s", _SERVICE, "-w"],
            capture_output=True, text=True,
        )
        return r.stdout.strip() if r.returncode == 0 else None

    def delete(self, name):
        subprocess.run(
            ["security", "delete-generic-password", "-a", name, "-s", _SERVICE],
            capture_output=True,
        )


def _default_backend():
    if sys.platform == "darwin":
        try:
            subprocess.run(["security", "help"], capture_output=True)
            return _KeychainBackend()
        except Exception:
            pass
    import warnings
    warnings.warn("credential vault: macOS Keychain unavailable — using a NON-persistent "
                  "in-memory store (dev/CI only; real secrets are NOT saved).")
    return _MemoryBackend()


_backend = None


def _b():
    global _backend
    if _backend is None:
        _backend = _default_backend()
    return _backend


def _names() -> list:
    raw = _b().get(_INDEX)
    try:
        return json.loads(raw) if raw else []
    except Exception:
        return []


def _set_names(names):
    _b().put(_INDEX, json.dumps(sorted(set(names))))


def put(name: str, secret: str) -> str:
    """Store/replace a credential. Returns a confirmation that NEVER contains the secret."""
    if not name or secret is None:
        return "vault: a name and a secret are both required, sir."
    _b().put(name, str(secret))
    _set_names(_names() + [name])
    return f"Stored '{name}' in the local vault — never logged, never leaves the Mac."


def get(name: str):
    """Retrieve a credential value (or None). Callers MUST never log the result."""
    return _b().get(name)


def has(name: str) -> bool:
    return name in _names()


def delete(name: str) -> str:
    _b().delete(name)
    _set_names([n for n in _names() if n != name])
    return f"Removed '{name}' from the vault."


def list_names() -> list:
    """Names only — NEVER the secret values."""
    return _names()
