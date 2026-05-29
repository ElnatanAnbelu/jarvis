#!/usr/bin/env python3
"""Idempotent setup: create the Elnatan + JARVIS central hub notes in
the vault and add a 'Linked: [[Elnatan]] · [[JARVIS]]' footer to every
existing note so Obsidian's graph view shows them as central."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

ELNATAN_MD = """---
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
"""

JARVIS_MD = """---
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
"""

SKIP = {"Elnatan.md", "JARVIS.md", "_Activity.md", "_Activity.jsonl", "_PersonalModel.md"}
BACKLINK = "\n\n---\n*Linked: [[Elnatan]] · [[JARVIS]]*\n"


def main():
    from memory.vault import VaultManager
    vm = VaultManager()
    vault = vm.vault_path
    e = vault / "Personal" / "Elnatan.md"
    j = vault / "_JARVIS" / "JARVIS.md"
    e.parent.mkdir(parents=True, exist_ok=True)
    j.parent.mkdir(parents=True, exist_ok=True)
    if not e.exists():
        e.write_text(ELNATAN_MD, encoding="utf-8")
        print(f"Created {e.relative_to(vault)}")
    if not j.exists():
        j.write_text(JARVIS_MD, encoding="utf-8")
        print(f"Created {j.relative_to(vault)}")

    added = 0
    for area in ["Personal", "Business", "Relationships", "Goals",
                  "Decisions", "Daily", "Learning", "Archive"]:
        for p in (vault / area).rglob("*.md"):
            if p.name in SKIP:
                continue
            t = p.read_text(encoding="utf-8")
            if "Linked: [[Elnatan]]" in t:
                continue
            p.write_text(t.rstrip() + BACKLINK, encoding="utf-8")
            added += 1
    for p in (vault / "_JARVIS" / "Proposals").rglob("*.md"):
        if p.name in SKIP:
            continue
        t = p.read_text(encoding="utf-8")
        if "Linked: [[Elnatan]]" in t:
            continue
        p.write_text(t.rstrip() + BACKLINK, encoding="utf-8")
        added += 1
    print(f"Backlinked {added} notes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
