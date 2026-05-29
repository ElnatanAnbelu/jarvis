#!/usr/bin/env python3
"""
One-shot migration: rename existing date-counter proposal filenames to
the descriptive '{Area} — {Title}.md' format and update their internal
proposal_id frontmatter field to match.

Idempotent — if a file is already in the new format, it's left alone.
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    from memory.vault import VaultManager
    vm = VaultManager()
    proposals_dir = vm.vault_path / "_JARVIS" / "Proposals"
    if not proposals_dir.exists():
        print("No proposals directory found — nothing to migrate.")
        return 0

    print(f"Scanning {proposals_dir}")
    print()

    renamed = 0
    skipped = 0
    legacy_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{3}$")

    for old_path in sorted(proposals_dir.glob("*.md")):
        stem = old_path.stem
        # Only migrate legacy date-counter filenames
        if not legacy_pattern.match(stem):
            skipped += 1
            continue

        fm = vm._parse_frontmatter(old_path)
        target = fm.get("target_note", "")
        if "/" not in target:
            print(f"  SKIP {stem} (no target_note in frontmatter)")
            skipped += 1
            continue

        area, _, title = target.partition("/")
        new_id, new_filename = vm._build_proposal_id(area, title)
        new_path = proposals_dir / new_filename

        # Update internal proposal_id field to the new descriptive form
        text = old_path.read_text(encoding="utf-8")
        text = re.sub(
            r"^(proposal_id:\s*).*$",
            f"\\g<1>{new_id}",
            text,
            count=1,
            flags=re.MULTILINE,
        )
        old_path.write_text(text, encoding="utf-8")

        # Rename
        old_path.rename(new_path)
        print(f"  {stem}.md  →  {new_filename}")
        renamed += 1

    print()
    print(f"Migrated: {renamed}, Skipped: {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
