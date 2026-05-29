#!/usr/bin/env python3
"""Idempotent setup: create the three central hub notes (Elnatan,
JARVIS, Claude Code) in the vault and add a backlink footer to every
existing note so Obsidian's graph view shows them as central spokes.
Re-runnable safely after vault changes."""
import sys
import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

HUBS = {
    "Personal/Elnatan.md": """---
title: Elnatan
area: Personal
tags: [identity, hub]
created_by: jarvis
sensitivity: low
---

# Elnatan

The center of this Second Brain. Everything in this vault is about,
for, or in service of him.

Co-curated with: [[JARVIS]]
System built by: [[Claude Code]]
""",
    "_JARVIS/JARVIS.md": """---
title: JARVIS
area: _JARVIS
tags: [system, hub]
created_by: jarvis
sensitivity: low
---

# JARVIS

I am Elnatan's personal AI operating system. I observe, synthesize, and
co-curate this Second Brain — but [[Elnatan]] owns it.

Co-curating with: [[Elnatan]]
System built by: [[Claude Code]]
""",
    "_JARVIS/Claude Code.md": """---
title: Claude Code
area: _JARVIS
tags: [system, hub, builder]
created_by: jarvis
sensitivity: low
---

# Claude Code

I am the AI development environment that built this Second Brain with
[[Elnatan]]. I am the architect's tool; [[JARVIS]] is the operating
persona that runs inside Elnatan's daily system.

Co-architects: [[Elnatan]] · [[JARVIS]]
""",
}

SKIP = {"Elnatan.md", "JARVIS.md", "Claude Code.md",
        "_Activity.md", "_Activity.jsonl", "_PersonalModel.md"}
BACKLINK = "\n\n---\n*Linked: [[Elnatan]] · [[JARVIS]] · [[Claude Code]]*\n"
OLD_BACKLINK = re.compile(r'\*Linked: \[\[Elnatan\]\] · \[\[JARVIS\]\]\*')


def main():
    from memory.vault import VaultManager
    vm = VaultManager()
    vault = vm.vault_path

    # Create / refresh hubs (idempotent — won't overwrite existing edits)
    for rel, content in HUBS.items():
        p = vault / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.write_text(content, encoding="utf-8")
            print(f"Created {rel}")

    # Walk all areas + proposals and add the backlink footer
    added = 0
    updated = 0
    for area in ["Personal", "Business", "Relationships", "Goals",
                  "Decisions", "Daily", "Learning", "Archive"]:
        targets = list((vault / area).rglob("*.md"))
        for p in targets:
            if p.name in SKIP:
                continue
            t = p.read_text(encoding="utf-8")
            if "[[Claude Code]]" in t:
                continue
            if OLD_BACKLINK.search(t):
                # upgrade old footer to include Claude Code
                new_t = OLD_BACKLINK.sub(BACKLINK.strip().lstrip("\n").lstrip("-").lstrip("\n"), t)
                p.write_text(new_t, encoding="utf-8")
                updated += 1
            else:
                p.write_text(t.rstrip() + BACKLINK, encoding="utf-8")
                added += 1

    for p in (vault / "_JARVIS" / "Proposals").rglob("*.md"):
        if p.name in SKIP:
            continue
        t = p.read_text(encoding="utf-8")
        if "[[Claude Code]]" in t:
            continue
        if OLD_BACKLINK.search(t):
            new_t = OLD_BACKLINK.sub(BACKLINK.strip().lstrip("\n").lstrip("-").lstrip("\n"), t)
            p.write_text(new_t, encoding="utf-8")
            updated += 1
        else:
            p.write_text(t.rstrip() + BACKLINK, encoding="utf-8")
            added += 1

    print(f"Backlinked: {added} new, {updated} upgraded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
