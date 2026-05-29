#!/usr/bin/env python3
"""
Add Obsidian wikilink syntax ([[Note Name]]) to existing notes so the
graph view actually shows the relationships between concepts.

Strategy:
  - We have a list of known entities (each one has its own note in the
    vault). When their name appears in any note's body, wrap it in
    [[brackets]] so Obsidian renders it as a link.
  - Word-boundary matching so we don't half-wrap something.
  - Already-bracketed occurrences are left alone (idempotent).
  - Skips frontmatter — only modifies note body content.

Run repeatedly without harm.
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


# Entity → wikilink target. Order matters: longest first so
# "Yostina Adugna Anbelu" gets matched before "Yostina".
ENTITY_MAP = [
    # Family — link to their relationship file
    ("Mom — Nitsuh Zenebe Girmay",   "Mom — Nitsuh Zenebe Girmay"),
    ("Dad — Adugna Anbelu Ejigu",    "Dad — Adugna Anbelu Ejigu"),
    ("Nitsuh Zenebe Girmay",         "Mom — Nitsuh Zenebe Girmay"),
    ("Adugna Anbelu Ejigu",          "Dad — Adugna Anbelu Ejigu"),
    ("Yostina Adugna Anbelu",        "Yostina Adugna Anbelu"),
    ("Eyonabel Adugna Anbelu",       "Eyonabel Adugna Anbelu"),
    ("Abigail Eyob",                 "Abigail Eyob"),
    ("Half-Siblings",                "Half-Siblings & Extended"),
    # Bare first-name forms for inside relationship notes
    ("Yostina",                      "Yostina Adugna Anbelu"),
    ("Eyonabel",                     "Eyonabel Adugna Anbelu"),
    # Businesses
    ("Addis Market",                 "Addis Market"),
    ("Nexel",                        "Nexel"),
    ("Dad's School",                 "Dad's School"),
    # Goals
    ("Long-Term Goals",              "Long-Term Goals"),
    ("Core Fears",                   "Core Fears"),
]


def split_frontmatter(text: str):
    """Return (frontmatter, body). If no frontmatter, returns ('', text)."""
    m = re.match(r"^(---\n.*?\n---\n)(.*)$", text, re.DOTALL)
    if m:
        return m.group(1), m.group(2)
    return "", text


def wikilink_body(body: str) -> tuple:
    """Wrap each known entity in [[]] when found as a whole word.
    Already-bracketed occurrences are not re-wrapped.
    Returns (new_body, n_replacements).
    """
    out = body
    total = 0
    for surface, target in ENTITY_MAP:
        # Negative lookbehind to skip already-bracketed: not preceded by '[['
        # Negative lookahead so we don't double-bracket: not followed by ']]'
        if surface == target:
            replacement = f"[[{surface}]]"
        else:
            replacement = f"[[{target}|{surface}]]"
        pattern = (
            r"(?<!\[\[)(?<!\[)"
            + r"\b" + re.escape(surface) + r"\b"
            + r"(?!\]\])(?!\|)"
        )
        new_out, n = re.subn(pattern, replacement, out)
        if n > 0:
            out = new_out
            total += n
    return out, total


def process_file(p: Path) -> int:
    """Return number of wikilinks added to this file."""
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        return 0
    fm, body = split_frontmatter(text)
    new_body, n = wikilink_body(body)
    if n > 0:
        p.write_text(fm + new_body, encoding="utf-8")
    return n


def main():
    from memory.vault import VaultManager
    vm = VaultManager()
    vault = vm.vault_path

    # Walk the whole vault (both real notes and pending proposals)
    targets = []
    for area in ["Personal", "Business", "Relationships", "Goals",
                  "Decisions", "Daily", "Learning", "Archive"]:
        targets.extend((vault / area).rglob("*.md"))
    targets.extend((vault / "_JARVIS" / "Proposals").rglob("*.md"))
    targets.append(vault / "_JARVIS" / "_PersonalModel.md")

    total_files = 0
    total_links = 0
    for p in targets:
        if not p.exists():
            continue
        n = process_file(p)
        if n > 0:
            rel = p.relative_to(vault)
            print(f"  {rel}  ({n} links added)")
            total_files += 1
            total_links += n

    print()
    print(f"Wikilinked {total_links} entity mentions across {total_files} files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
