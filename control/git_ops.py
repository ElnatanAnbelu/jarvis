"""
Git operations for JARVIS — init, status, add, commit, push, branch, log, diff, clone.
"""
import os
import subprocess
import shutil
from pathlib import Path


def _expand(path: str) -> str:
    return str(Path(os.path.expanduser(path)).resolve())


def _run(cmd: str, cwd: str, timeout: int = 60) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=cwd, env=os.environ.copy()
        )
        out = (result.stdout + result.stderr).strip()
        return result.returncode == 0, out
    except subprocess.TimeoutExpired:
        return False, f"Git command timed out: {cmd}"
    except Exception as e:
        return False, str(e)


def _find_repo(path: str = None):
    """Walk up from path to find a git repo root."""
    start = Path(_expand(path)) if path else Path.home()
    check = start if start.is_dir() else start.parent
    for _ in range(10):
        if (check / ".git").exists():
            return str(check)
        parent = check.parent
        if parent == check:
            break
        check = parent
    return None


def git_init(path: str = ".") -> str:
    p = _expand(path)
    if not os.path.isdir(p):
        os.makedirs(p, exist_ok=True)
    ok, out = _run("git init", cwd=p)
    if ok:
        return f"Git repo initialized at {p}"
    return f"git init failed: {out}"


def git_status(path: str = ".") -> str:
    p = _expand(path)
    repo = _find_repo(p) or p
    ok, out = _run("git status", cwd=repo)
    if not out:
        return "Nothing to report — working tree clean."
    return out


def git_add(path: str = ".", files: str = ".") -> str:
    """Add files to staging. files: '.' for all, or space-separated paths."""
    p = _expand(path)
    repo = _find_repo(p) or p
    target = files if files != "." else "-A"
    ok, out = _run(f"git add {target}", cwd=repo)
    if ok:
        staged_ok, staged = _run("git diff --cached --stat", cwd=repo)
        return staged if staged else "Files staged. Nothing changed vs HEAD."
    return f"git add failed: {out}"


def git_commit(path: str = ".", message: str = "update") -> str:
    p = _expand(path)
    repo = _find_repo(p) or p
    safe_msg = message.replace('"', '\\"')
    ok, out = _run(f'git commit -m "{safe_msg}"', cwd=repo)
    if ok:
        return out
    if "nothing to commit" in out:
        return "Nothing to commit — working tree clean."
    return f"git commit failed: {out}"


def git_push(path: str = ".", remote: str = "origin", branch: str = "") -> str:
    p = _expand(path)
    repo = _find_repo(p) or p
    if not branch:
        _, branch = _run("git rev-parse --abbrev-ref HEAD", cwd=repo)
        branch = branch.strip() or "main"
    ok, out = _run(f"git push {remote} {branch}", cwd=repo, timeout=60)
    if ok:
        return out or f"Pushed to {remote}/{branch}."
    return f"git push failed: {out}"


def git_branch(path: str = ".", name: str = "", action: str = "list") -> str:
    """
    action: 'list' — show all branches
            'create' — create new branch (requires name)
            'switch' — switch to branch (requires name)
            'delete' — delete branch (requires name)
    """
    p = _expand(path)
    repo = _find_repo(p) or p
    if action == "list" or (not name and not action):
        ok, out = _run("git branch -a", cwd=repo)
        return out or "No branches found."
    if action == "create" and name:
        ok, out = _run(f"git checkout -b {name}", cwd=repo)
        return out if out else (f"Branch '{name}' created." if ok else f"Failed: {out}")
    if action == "switch" and name:
        ok, out = _run(f"git checkout {name}", cwd=repo)
        return out if out else (f"Switched to '{name}'." if ok else f"Failed: {out}")
    if action == "delete" and name:
        ok, out = _run(f"git branch -d {name}", cwd=repo)
        return out if out else (f"Deleted branch '{name}'." if ok else f"Failed: {out}")
    return "Specify action: list | create | switch | delete"


def git_log(path: str = ".", n: int = 10) -> str:
    p = _expand(path)
    repo = _find_repo(p) or p
    ok, out = _run(f"git log --oneline --graph --decorate -n {n}", cwd=repo)
    return out or "No commits yet."


def git_diff(path: str = ".", staged: bool = False) -> str:
    p = _expand(path)
    repo = _find_repo(p) or p
    flag = "--cached" if staged else ""
    ok, out = _run(f"git diff {flag} --stat", cwd=repo)
    if not out:
        label = "staged changes" if staged else "unstaged changes"
        return f"No {label}."
    return out


def git_clone(url: str, path: str = ".", name: str = "") -> str:
    p = _expand(path)
    cmd = f"git clone {url}"
    if name:
        cmd += f" {name}"
    ok, out = _run(cmd, cwd=p, timeout=120)
    if ok:
        return out or f"Cloned {url} into {p}"
    return f"git clone failed: {out}"


def git_create_github_repo(name: str, private: bool = True, path: str = ".") -> str:
    """Create a GitHub repo and push local code. Requires gh CLI."""
    if not shutil.which("gh"):
        return "gh CLI not installed. Install with: brew install gh"
    p = _expand(path)
    repo = _find_repo(p) or p
    vis = "--private" if private else "--public"
    ok, out = _run(f"gh repo create {name} {vis} --source=. --remote=origin --push", cwd=repo, timeout=60)
    if ok:
        return out or f"GitHub repo '{name}' created and code pushed."
    return f"gh repo create failed: {out}"
