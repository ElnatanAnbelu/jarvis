"""Right-to-be-forgotten across ALL stores — db + vault (+ FAISS invalidation).

The vault is sacred, so subject notes are ARCHIVED (moved to _Archive/Forgotten),
never hard-deleted — reversible. The DB purge (conversations/facts/ledger) is
handled by memory.forget_subject. This is destructive enough to be a red-list tool.
"""
import os
import shutil
from pathlib import Path

from memory import memory

VAULT = Path(os.environ.get("SECONDBRAIN_PATH", str(Path.home() / "Desktop" / "SecondBrain")))


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

    # 3. Invalidate the vault search index so the archived notes stop serving from
    #    the in-RAM FAISS cache. The LIVE index lives on the VaultManager *singleton*
    #    used by the RAG tools (brain.tools.second_brain._vault), not on the module —
    #    merely touching memory.vault did nothing (a forgotten subject kept resurfacing
    #    from cached chunks until the next lazy rebuild). Reset the singleton's index
    #    state under its own lock so the next search rebuilds from disk (archived
    #    notes excluded).
    try:
        from brain.tools import second_brain as _sb
        vm = _sb._vault()
        with vm._index_lock:
            vm._index = None
            vm._chunks = []
            vm._titles = []
            vm._last_build = 0.0
    except Exception:
        pass

    # 4. The wiki "_Memory" store is a SECOND markdown vault (generated, separate
    #    from SecondBrain) with its own in-RAM FAISS index. Archive matching notes
    #    and invalidate the index, else a forgotten subject keeps resurfacing in
    #    prompts for up to the rebuild interval — and the on-disk note forever.
    wiki_archived = 0
    try:
        from memory import wiki as _w
        needle = ident.lower()
        forgotten = _w.WIKI_PATH / ".forgotten"
        for md in list(_w.WIKI_PATH.glob("*.md")):
            try:
                txt = md.read_text(encoding="utf-8", errors="ignore").lower()
            except Exception:
                continue
            if needle in txt or needle in md.stem.lower():
                forgotten.mkdir(parents=True, exist_ok=True)
                dest = forgotten / md.name
                if dest.exists():
                    dest = forgotten / f"{md.stem}_{wiki_archived}{md.suffix}"
                shutil.move(str(md), str(dest))
                wiki_archived += 1
        _w.invalidate_index()
    except Exception:
        pass

    # 5. observations.db — staged email/sender content + auto-extracted personal
    #    facts. Never purged before, so a "forgotten" contact's address/subject/
    #    body excerpt survived at rest.
    obs_removed = 0
    try:
        from memory import observations as _obs
        like = f"%{ident}%"
        with _obs._lock:
            conn = _obs._get_conn()
            cur = conn.execute(
                "DELETE FROM observations WHERE content LIKE ? OR source_detail LIKE ? "
                "OR relevance_hint LIKE ?",
                (like, like, like),
            )
            obs_removed = cur.rowcount
            conn.commit()
    except Exception:
        pass

    try:
        from obs.log import log_event
        log_event("privacy.forget_subject_full", level="warning", subject=ident,
                  vault_archived=archived, wiki_archived=wiki_archived, observations=obs_removed)
    except Exception:
        pass

    return (f"{db_summary} Archived {archived} vault + {wiki_archived} wiki note(s); "
            f"purged {obs_removed} observation(s), sir.")
