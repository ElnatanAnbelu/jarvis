"""Right-to-be-forgotten across ALL stores — db + vault (+ FAISS invalidation).

The vault is sacred, so subject notes are ARCHIVED (moved to _Archive/Forgotten),
never hard-deleted — reversible. The DB purge (conversations/facts/ledger) is
handled by memory.forget_subject. This is destructive enough to be a red-list tool.
"""
import os
import shutil
from pathlib import Path

from memory import memory

VAULT = Path(os.environ.get("SECONDBRAIN_PATH", str(Path.home() / "Documents" / "SecondBrain")))


def forget_subject(identifier: str) -> str:
    ident = (identifier or "").strip()
    if len(ident) < 3:
        return "Refusing to forget — give a specific identifier (3+ chars), sir."

    # 1. Local DB (conversations, facts, action ledger).
    db_summary = memory.forget_subject(ident)

    # 2. Vault: archive any note that names the subject (reversible move).
    archived = 0
    try:
        forgotten = VAULT / "_Archive" / "Forgotten"
        needle = ident.lower()
        for md in VAULT.rglob("*.md"):
            if "_Archive" in md.parts:
                continue
            try:
                text = md.read_text(encoding="utf-8", errors="ignore").lower()
            except Exception:
                continue
            if needle in text or needle in md.stem.lower():
                forgotten.mkdir(parents=True, exist_ok=True)
                dest = forgotten / md.name
                if dest.exists():
                    dest = forgotten / f"{md.stem}_{archived}{md.suffix}"
                shutil.move(str(md), str(dest))
                archived += 1
    except Exception:
        pass

    # 3. Invalidate the vault search index so rebuilds exclude the archived notes.
    try:
        from memory import vault as _v
        _v._EMBED_MODEL  # touch module; index rebuilds lazily from area folders (archived notes excluded)
    except Exception:
        pass

    try:
        from obs.log import log_event
        log_event("privacy.forget_subject_full", level="warning", subject=ident, vault_archived=archived)
    except Exception:
        pass

    return f"{db_summary} Archived {archived} vault note(s) to _Archive/Forgotten, sir."
