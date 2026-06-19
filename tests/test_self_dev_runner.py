"""P3 — the self-dev ORCHESTRATOR. Runs against a throwaway git repo (never the real
one). Proves: a green change lands on an isolated branch with main untouched; a
failing change is FULLY reverted (tree restored, no branch); and the safety gates
(owner-only, protected paths, traversal) hold."""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain import self_dev_runner as r
from brain.self_dev import SelfDevDenied


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@t.com")
    _git(tmp_path, "config", "user.name", "T")
    (tmp_path / "mod.py").write_text("VALUE = 1\n")
    # a test that passes iff VALUE == 1
    (tmp_path / "test_mod.py").write_text("from mod import VALUE\n\ndef test_v():\n    assert VALUE == 1\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    return tmp_path


# python -c keeps the temp suite trivial and venv-independent
_PYTEST = [sys.executable, "-m", "pytest", "-q"]


def test_green_change_lands_on_branch_main_untouched(repo):
    res = r.implement_change(
        {"mod.py": "VALUE = 1  # tidied\n"}, "tidy mod",
        repo_root=repo, test_cmd=_PYTEST,
    )
    assert res["ok"] is True
    assert res["branch"] == "self-dev/tidy-mod"
    assert "tidied" in res["diff"]
    # we are back on main, working tree clean, main's content unchanged
    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "main"
    assert (repo / "mod.py").read_text() == "VALUE = 1\n"
    assert _git(repo, "status", "--porcelain").stdout.strip() == ""
    # the change is preserved on the side branch
    assert "self-dev/tidy-mod" in _git(repo, "branch").stdout


def test_failing_change_is_fully_reverted(repo):
    res = r.implement_change(
        {"mod.py": "VALUE = 999\n"}, "break it",
        repo_root=repo, test_cmd=_PYTEST,
    )
    assert res["ok"] is False
    assert "tests failed" in res["reason"]
    # tree restored, on main, NO leftover branch
    assert (repo / "mod.py").read_text() == "VALUE = 1\n"
    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "main"
    assert _git(repo, "status", "--porcelain").stdout.strip() == ""
    assert "self-dev/break-it" not in _git(repo, "branch").stdout


def test_non_owner_is_denied(repo):
    for bad in ("autonomous", "external"):
        with pytest.raises(SelfDevDenied):
            r.implement_change({"mod.py": "VALUE = 1\n"}, "x", source=bad, repo_root=repo, test_cmd=_PYTEST)


def test_unverified_identity_denied(repo):
    with pytest.raises(SelfDevDenied):
        r.implement_change({"mod.py": "x\n"}, "x", identity_verified=False, repo_root=repo, test_cmd=_PYTEST)


def test_protected_path_refused(repo):
    with pytest.raises(SelfDevDenied):
        r.implement_change({"brain/autonomy.py": "# evil\n"}, "rewrite gate", repo_root=repo, test_cmd=_PYTEST)


def test_path_traversal_refused(repo):
    with pytest.raises(SelfDevDenied):
        r.implement_change({"../escape.py": "x\n"}, "escape", repo_root=repo, test_cmd=_PYTEST)


def test_dirty_tree_refused(repo):
    (repo / "mod.py").write_text("VALUE = 2\n")  # uncommitted change
    res = r.implement_change({"test_mod.py": "def test_x():\n    assert True\n"},
                             "x", repo_root=repo, test_cmd=_PYTEST)
    assert res["ok"] is False and "dirty" in res["reason"]
