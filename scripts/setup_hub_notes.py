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

# Only skip binary/append-only logs. Hub notes themselves still get the
# footer — harmless redundancy on hubs keeps the format uniform.
SKIP = {"_Activity.jsonl"}
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

    # Walk EVERYTHING — every .md anywhere in the vault gets the footer
    # (except the binary log and any file that already has [[Claude Code]]).
    # Also auto-populate an empty Obsidian daily note with a minimal header
    # so it has content to link.
    added = 0
    updated = 0
    populated_empty = 0
    for p in vault.rglob("*.md"):
        if p.name in SKIP:
            continue
        t = p.read_text(encoding="utf-8")
        if not t.strip():
            # Empty Obsidian daily note — give it minimal content
            t = f"# {p.stem}\n\n*Daily note. Day belongs to [[Elnatan]].*\n"
            populated_empty += 1
        if "[[Claude Code]]" in t:
            continue
        if OLD_BACKLINK.search(t):
            new_t = OLD_BACKLINK.sub(BACKLINK.strip().lstrip("\n").lstrip("-").lstrip("\n"), t)
            p.write_text(new_t, encoding="utf-8")
            updated += 1
        else:
            p.write_text(t.rstrip() + BACKLINK, encoding="utf-8")
            added += 1

    print(f"Backlinked: {added} new, {updated} upgraded, "
          f"{populated_empty} empty notes populated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
