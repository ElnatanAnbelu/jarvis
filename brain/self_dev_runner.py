"""P3 — Self-dev ORCHESTRATOR (built on the brain/self_dev.py safety frame).

This is the implement → branch → test → diff step. It does NOTHING the frame doesn't
authorize, and it is deliberately conservative:

  * OWNER-ONLY + identity-verified (delegates to self_dev.authorize) — autonomous /
    external / injected triggers are hard-denied.
  * PROTECTED paths (gate / identity / vault / .env / firewall / the frame itself)
    can never be written, re-checked here as defense in depth.
  * Scope = inside the repo only; path traversal is refused.
  * Works on an ISOLATED git branch. main is never touched. On test failure it FULLY
    reverts (working tree restored, branch deleted). On success it commits to the
    branch and returns the diff — it NEVER auto-merges; the owner merges by hand.
  * Refuses to start on a dirty tree (won't mix your uncommitted work into a self-dev
    branch).

Reversibility is structural: it's all git, and the change lands on a side branch the
owner reviews. Nothing here can silently alter the running Alfred.
"""
import re
import subprocess
from pathlib import Path

from brain.self_dev import _INSTALL_ROOT, _PROTECTED, SelfDevDenied, authorize


def _git(repo: Path, *args, check=True):
    r = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}")
    return r


def _slug(summary: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (summary or "change").lower()).strip("-")
    return (s or "change")[:40]


def _validate(edits: dict, repo: Path):
    """Every target must be a relative path INSIDE repo and NOT protected. Raises."""
    if not isinstance(edits, dict) or not edits:
        raise SelfDevDenied("self-dev: no edits supplied.")
    for relpath in edits:
        if Path(relpath).is_absolute():
            raise SelfDevDenied(f"self-dev: '{relpath}' must be a repo-relative path.")
        resolved = (repo / relpath).resolve()
        try:
            rel = resolved.relative_to(repo.resolve()).as_posix()
        except Exception:
            raise SelfDevDenied(f"self-dev: '{relpath}' escapes the repo — refused.")
        if any(rel == p or rel.startswith(p.rstrip('/') + '/') for p in _PROTECTED):
            raise SelfDevDenied(
                f"self-dev: '{rel}' is protected (gate/identity/secrets) — off-limits to self-modification."
            )


def implement_change(edits: dict, summary: str, source: str = "user",
                     identity_verified: bool = True, repo_root=None,
                     test_cmd=None) -> dict:
    """Apply {relpath: new_content} edits on an isolated branch, run the tests, and
    either keep the branch (green) or fully revert (red). Returns a result dict; never
    merges to main. `repo_root`/`test_cmd` are injectable for tests."""
    authorize(source, identity_verified)                       # owner-only gate (raises)
    repo = Path(repo_root) if repo_root else _INSTALL_ROOT
    _validate(edits, repo)                                     # protected/scope gate (raises)

    if not (repo / ".git").exists():
        return {"ok": False, "reason": "not a git repo — self-dev needs version control."}
    if _git(repo, "status", "--porcelain").stdout.strip():
        return {"ok": False, "reason": "working tree is dirty — commit/stash your changes first, sir."}

    orig = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    branch = f"self-dev/{_slug(summary)}"
    # Recreate a same-named prior self-dev branch cleanly.
    _git(repo, "branch", "-D", branch, check=False)
    _git(repo, "checkout", "-b", branch)

    def _restore():
        _git(repo, "checkout", "--", ".", check=False)        # discard edits
        _git(repo, "checkout", orig, check=False)
        _git(repo, "branch", "-D", branch, check=False)

    try:
        for relpath, content in edits.items():
            target = repo / relpath
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)

        cmd = test_cmd or ["./venv/bin/python", "-m", "pytest", "-q"]
        tests = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True)
        tail = (tests.stdout or tests.stderr or "")[-1500:]

        if tests.returncode != 0:
            _restore()
            return {"ok": False, "branch": None, "reason": "tests failed — change reverted, nothing kept.",
                    "test_output": tail}

        _git(repo, "add", *list(edits.keys()))
        _git(repo, "commit", "-m", f"self-dev: {summary}")
        diff = _git(repo, "diff", f"{orig}..{branch}").stdout
        _git(repo, "checkout", orig)                          # return repo to its original state
        return {"ok": True, "branch": branch, "summary": summary,
                "diff": diff, "test_output": tail,
                "note": f"Implemented on '{branch}' (tests green). main is untouched — "
                        f"review the diff, then merge it yourself when satisfied, sir."}
    except Exception as e:
        _restore()
        return {"ok": False, "branch": None, "reason": f"self-dev errored and was reverted: {e}"}
