"""P3 — Gated self-development (the SAFETY FRAME).

Alfred can extend/fix its OWN code — but ONLY through a safe pipeline:
  owner-authenticated request → isolated git branch → full test + eval gate →
  diff → owner approval → ship → reversible.

This module is the load-bearing safety layer and ships BEFORE any capability that
widens what Alfred can do to itself. The hard invariants it enforces:

  1. OWNER-ONLY trigger. Only a present, identity-verified owner (source="user")
     may start a self-dev run. Autonomous, external, or prompt-injected triggers
     are hard-denied — this is what stops a poisoned email from making Alfred
     rewrite itself.
  2. PROTECTED PATHS are off-limits. Alfred can NEVER self-modify its own safety
     gate, identity/PIN, the credential vault, .env, the install-tree firewall,
     or THIS file. (You change those out-of-band, by hand.)
  3. Scope = its own install tree only; nothing outside the repo.

The implement → branch → test → diff → ship → revert ORCHESTRATION is a separate,
owner-approved step built on top of this frame (it does nothing until this layer
authorizes it). This module writes no code itself; it only decides + queues.

Composes with control/files.py's install-tree write firewall — self-dev is the
only sanctioned route to touch install-tree code, and even it refuses PROTECTED.
"""
import os
from pathlib import Path

_INSTALL_ROOT = Path(__file__).resolve().parent.parent  # the jarvis repo root

# Files Alfred may NEVER self-modify — the safety/secrets core. Off-limits even to
# an owner-initiated self-dev run; these change by hand, out of band.
_PROTECTED = (
    "brain/autonomy.py",       # the safety gate / red-list / money-PIN
    "brain/self_dev.py",       # this firewall — Alfred can't rewrite its own guard
    "security/identity.py",    # auth / PIN / biometrics
    "security/vault.py",       # the credential vault (when it lands)
    ".env",
    ".session_token",
    "control/files.py",        # the install-tree self-write firewall
)


class SelfDevDenied(Exception):
    """Raised when a self-dev request violates a safety invariant."""


def _rel(path) -> str:
    """Path relative to the install root (normalized), for protected-set checks."""
    p = Path(os.path.expanduser(str(path)))
    if not p.is_absolute():
        p = _INSTALL_ROOT / p
    try:
        return str(p.resolve().relative_to(_INSTALL_ROOT))
    except Exception:
        return str(p.resolve())  # outside the repo — caller's in_install_tree() rejects it


def in_install_tree(path) -> bool:
    """True if `path` is inside Alfred's own repo (the only place self-dev may touch)."""
    p = Path(os.path.expanduser(str(path)))
    if not p.is_absolute():
        p = _INSTALL_ROOT / p
    try:
        p.resolve().relative_to(_INSTALL_ROOT)
        return True
    except Exception:
        return False


def is_protected(path) -> bool:
    """True if `path` is a file Alfred must never self-modify (gate/identity/secrets)."""
    rel = _rel(path)
    return any(rel == prot or rel.startswith(prot.rstrip("/") + "/") for prot in _PROTECTED)


def authorize(source: str = "user", identity_verified: bool = True) -> None:
    """Gate the START of a self-dev run. Only a present, identity-verified owner may
    begin; autonomous / external / injected sources are hard-denied. Raises on refusal."""
    if source != "user":
        raise SelfDevDenied(
            f"self-dev refused: source '{source}' is not the owner — only a present owner may start it."
        )
    if not identity_verified:
        raise SelfDevDenied("self-dev refused: owner identity not verified.")


def request_change(files, summary: str, source: str = "user",
                   identity_verified: bool = True) -> dict:
    """Owner-initiated request to change Alfred's own code. Enforces every safety
    invariant FIRST, then queues a proposal for owner approval. Writes no code.

    Returns {"action": "proposed", "confirm_id": int, "files": [...]} on success;
    raises SelfDevDenied on any violation (non-owner, outside repo, protected path).
    """
    authorize(source, identity_verified)
    targets = [files] if isinstance(files, str) else list(files or [])
    if not targets:
        raise SelfDevDenied("self-dev refused: no target files.")
    for f in targets:
        if not in_install_tree(f):
            raise SelfDevDenied(f"self-dev refused: '{f}' is outside Alfred's own code.")
        if is_protected(f):
            raise SelfDevDenied(
                f"self-dev refused: '{f}' is protected (gate/identity/secrets) — off-limits to self-modification."
            )
    from memory import memory
    cid = memory.enqueue_confirmation(
        "self_dev_change", {"files": targets, "summary": summary},
        agent="self_dev", risk="red", reason=f"self-dev: {summary}",
    )
    return {
        "action": "proposed",
        "confirm_id": cid,
        "files": targets,
        "note": ("Queued for your approval. On approval Alfred implements it on an isolated "
                 "branch, runs the full test + eval + latency gate, shows you the diff, and "
                 "ships it reversibly. (Orchestration step builds on this safety frame.)"),
    }
