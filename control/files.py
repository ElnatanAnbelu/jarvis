"""
File system operations for JARVIS.
Read, write, create, delete, move, list — with safety confirmations for destructive ops.
"""
import os
import shutil
from pathlib import Path

# ── Self-write firewall ──────────────────────────────────────────────────────
# JARVIS must NEVER be able to modify its own code, safety gate, or secrets.
# Without this, write_file/create_file/move_file could overwrite
# brain/autonomy.py (neutering the red-list), brain/tools/registry.py (removing
# the gate call), security/identity.py, or .env — a self-edit that defeats the
# entire safety substrate. This guard is independent of and in addition to the
# autonomy gate: it refuses any write/create/move/delete whose resolved path
# lands inside the JARVIS install tree, regardless of the gate's decision or any
# tool argument. Legitimate writes (Obsidian vault at ~/Documents/SecondBrain,
# ~/Desktop reports/charts, user docs, /tmp) are all OUTSIDE the install tree
# and remain allowed.
_INSTALL_ROOT = Path(__file__).resolve().parent.parent


def _expand(path: str) -> str:
    return str(Path(os.path.expanduser(path)).resolve())


def _inside_install(full: str) -> bool:
    """True if `full` (an already-resolved path) is the install root or within
    it. Uses resolved paths on both sides so `..`/symlink tricks can't escape."""
    try:
        root = _INSTALL_ROOT.resolve()
        p = Path(full).resolve()
        return p == root or root in p.parents
    except Exception:
        # If we cannot decide, refuse — fail closed.
        return True


def _guard_write(full: str) -> str:
    """Return a refusal message if writing/altering `full` would touch JARVIS's
    own install tree, else '' (allowed)."""
    if _inside_install(full):
        return ("🚫 Refused: that path is inside JARVIS's own install directory. "
                "JARVIS cannot modify its own code, safety gate, or secrets. "
                "Write to the vault or another location instead.")
    return ""


def read_file(path: str, max_chars: int = 20000) -> str:
    """Read a file and return its contents."""
    try:
        full = _expand(path)
        if not os.path.exists(full):
            return f"File not found: {path}"
        if os.path.isdir(full):
            return list_directory(path)
        size = os.path.getsize(full)
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_chars)
        truncated = len(content) == max_chars and size > max_chars
        result = content
        if truncated:
            result += f"\n\n[... file truncated — {size:,} bytes total, showing first {max_chars:,} chars]"
        return result
    except Exception as e:
        return f"Could not read file: {e}"


def write_file(path: str, content: str) -> str:
    """Write content to an existing file (overwrites)."""
    try:
        full = _expand(path)
        blocked = _guard_write(full)
        if blocked:
            return blocked
        if not os.path.exists(full):
            return f"File not found: {path}. Use create_file to make a new one."
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Written to {full} ({len(content):,} chars)."
    except Exception as e:
        return f"Could not write file: {e}"


def create_file(path: str, content: str = "") -> str:
    """Create a new file (and any missing parent directories)."""
    try:
        full = _expand(path)
        blocked = _guard_write(full)
        if blocked:
            return blocked
        if os.path.exists(full):
            return f"File already exists: {full}. Use write_file to overwrite."
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Created: {full}"
    except Exception as e:
        return f"Could not create file: {e}"


def delete_file(path: str) -> str:
    """Delete a file or empty directory."""
    try:
        full = _expand(path)
        blocked = _guard_write(full)
        if blocked:
            return blocked
        if not os.path.exists(full):
            return f"Not found: {path}"
        if os.path.isdir(full):
            shutil.rmtree(full)
            return f"Deleted directory: {full}"
        os.remove(full)
        return f"Deleted: {full}"
    except Exception as e:
        return f"Could not delete: {e}"


def move_file(src: str, dst: str) -> str:
    """Move or rename a file or directory."""
    try:
        full_src = _expand(src)
        full_dst = _expand(dst)
        # Guard BOTH ends: moving a file out of the install tree deletes it from
        # there; moving one in could plant code. Either is self-modification.
        blocked = _guard_write(full_src) or _guard_write(full_dst)
        if blocked:
            return blocked
        if not os.path.exists(full_src):
            return f"Source not found: {src}"
        os.makedirs(os.path.dirname(full_dst), exist_ok=True)
        shutil.move(full_src, full_dst)
        return f"Moved: {full_src} → {full_dst}"
    except Exception as e:
        return f"Could not move: {e}"


def list_directory(path: str = ".", show_hidden: bool = False) -> str:
    """List files and directories at the given path."""
    try:
        full = _expand(path)
        if not os.path.exists(full):
            return f"Directory not found: {path}"
        if not os.path.isdir(full):
            return f"Not a directory: {path}"
        entries = sorted(os.scandir(full), key=lambda e: (not e.is_dir(), e.name.lower()))
        lines = [f"{full}/"]
        for e in entries:
            if not show_hidden and e.name.startswith("."):
                continue
            if e.is_dir():
                lines.append(f"  📁 {e.name}/")
            else:
                size = e.stat().st_size
                size_str = f"{size:,}b" if size < 1024 else (f"{size//1024:,}KB" if size < 1048576 else f"{size//1048576:,}MB")
                lines.append(f"  📄 {e.name}  ({size_str})")
        if len(lines) == 1:
            lines.append("  (empty)")
        return "\n".join(lines)
    except Exception as e:
        return f"Could not list directory: {e}"


def make_directory(path: str) -> str:
    """Create a directory (and all parents)."""
    try:
        full = _expand(path)
        os.makedirs(full, exist_ok=True)
        return f"Directory created: {full}"
    except Exception as e:
        return f"Could not create directory: {e}"
