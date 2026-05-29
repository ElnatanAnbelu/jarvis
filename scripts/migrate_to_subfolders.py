#!/usr/bin/env python3
"""
One-shot migration: move existing flat-format proposal files into
subfolders by area, and strip the redundant area prefix from filenames.

Before:  _JARVIS/Proposals/Business — Addis Market.md
After:   _JARVIS/Proposals/Business/Addis Market.md

Personal Model proposals go into a dedicated 'Personal Model/' subfolder
regardless of their stored area (they're typed as area=_JARVIS but
their meaning is Personal Model section).

Idempotent.
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

    moved = 0
    skipped = 0

    for old_path in sorted(proposals_dir.glob("*.md")):
        # Only top-level files — anything already in a subfolder is skipped
        fm = vm._parse_frontmatter(old_path)
        target = fm.get("target_note", "")
        area = fm.get("area", "")

        if not area:
            print(f"  SKIP {old_path.name} (no area in frontmatter)")
            skipped += 1
            continue

        # Use the same subfolder logic the production code now uses
        title = fm.get("proposal_id", old_path.stem)
        # Strip the legacy "{Area} — " prefix from the proposal_id if present
        clean_title = title
        prefix = f"{area} — "
        if clean_title.startswith(prefix):
            clean_title = clean_title[len(prefix):]
        # For Personal Model proposals, strip the "Personal Model — " too —
        # the subfolder will be 'Personal Model' and the filename should
        # just be the section name
        if area == "_JARVIS" and clean_title.startswith("Personal Model — "):
            new_subfolder = "Personal Model"
            clean_title = clean_title[len("Personal Model — "):]
        elif area == "_JARVIS":
            new_subfolder = "_JARVIS"
        else:
            new_subfolder = re.sub(r'[<>:"/\\|?*]', '', area).strip() or "Other"

        new_dir = proposals_dir / new_subfolder
        new_dir.mkdir(parents=True, exist_ok=True)
        new_path = new_dir / f"{clean_title}.md"

        # Collision check
        n = 2
        while new_path.exists():
            new_path = new_dir / f"{clean_title} ({n}).md"
            n += 1

        # Also update the proposal_id frontmatter to the clean form
        text = old_path.read_text(encoding="utf-8")
        text = re.sub(
            r"^(proposal_id:\s*).*$",
            f"\\g<1>{clean_title}",
            text,
            count=1,
            flags=re.MULTILINE,
        )
        old_path.write_text(text, encoding="utf-8")

        old_path.rename(new_path)
        print(f"  {old_path.name}  →  {new_subfolder}/{new_path.name}")
        moved += 1

    print()
    print(f"Moved: {moved}, Skipped: {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
