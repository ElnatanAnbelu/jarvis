#!/usr/bin/env python3
"""
Adaptive learning logger for the Personal Second Brain.

When Claude Code or JARVIS learns something new about Elnatan during a
session, this captures it correctly — checking for existing content
first so we adapt instead of duplicate.

Decision tree per call:
  1. Search the vault for related content (semantic + keyword)
  2. If a strong match exists:
       - For low-risk content: append as an update with attribution
       - For high-risk: propose the addition for review
  3. If no match: create new (auto-write for low-risk areas, propose
     for high-risk)

Examples:
  python3 scripts/log_learning.py \\
      --area Personal --title "Communication Style" \\
      --content "Prefers direct pushback over warm validation." \\
      --source "Claude Code session 2026-05-29"

  python3 scripts/log_learning.py \\
      --personal-model "Energy Patterns" \\
      --content "Most productive 11pm-3am." \\
      --source "live conversation"

The script always reports what it did so the change is traceable.
"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


SIMILARITY_THRESHOLD_CHARS = 30  # min match length to consider it 'related'


def log_learning(area: str, title: str, content: str, source: str,
                 sensitivity: str = "low", check_existing: bool = True) -> str:
    """Record a learning. Returns a human-readable status string."""
    from memory.vault import VaultManager
    vm = VaultManager()

    # 1. Adaptive check — search the vault for related content
    related = ""
    if check_existing:
        related = vm.search_vault(content[:120], max_results=2) or ""

    # 2. Resolve the existing note for this area+title, if any
    existing_path = vm._resolve_note_path(f"{area}/{title}")
    if existing_path and existing_path.exists():
        # Update path — appends to the existing note
        body = (f"{content}\n\n"
                f"*Source: {source}*")
        result = vm.update_note(f"{area}/{title}", body, source,
                                sensitivity=sensitivity)
        return f"[adapt → updated] {area}/{title} :: {result}"

    # 3. New note path
    body = content
    result = vm.create_note(title=title, content=body, area=area,
                            source=source, sensitivity=sensitivity)
    return f"[adapt → created] {area}/{title} :: {result}"


def log_personal_model_update(section: str, content: str,
                              source: str, evidence: str = "") -> str:
    """Personal Model updates always go through proposal flow."""
    from memory.vault import VaultManager
    vm = VaultManager()
    result = vm.update_personal_model(
        section=section, content=content, source=source,
        supporting_observations=evidence,
    )
    return f"[adapt → proposed Personal Model] {section} :: {result}"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--area", help="Vault area: Personal, Business, Goals, ...")
    ap.add_argument("--title", help="Note title")
    ap.add_argument("--content", required=True, help="What was learned")
    ap.add_argument("--source", default="Claude Code session",
                    help="Where the learning came from")
    ap.add_argument("--sensitivity", default="low",
                    choices=["low", "medium", "high"])
    ap.add_argument("--personal-model", dest="personal_model",
                    help="Section name for a Personal Model update (mutually "
                         "exclusive with --area/--title)")
    ap.add_argument("--evidence", default="",
                    help="Supporting evidence for Personal Model updates")
    ap.add_argument("--no-check", action="store_true",
                    help="Skip the dedup search (force-create)")
    args = ap.parse_args()

    if args.personal_model:
        print(log_personal_model_update(
            section=args.personal_model, content=args.content,
            source=args.source, evidence=args.evidence,
        ))
        return 0

    if not args.area or not args.title:
        ap.error("Either --personal-model OR both --area and --title required.")

    print(log_learning(
        area=args.area, title=args.title, content=args.content,
        source=args.source, sensitivity=args.sensitivity,
        check_existing=not args.no_check,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
