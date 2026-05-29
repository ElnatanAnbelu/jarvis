#!/usr/bin/env python3
"""
Personal Second Brain — Initial Intake

Interactive seeding flow for the Personal Model + core vault notes.
Run this once when starting the brain to get high-signal foundation
content in fast. After this, the brain grows through normal use.

Usage:
    python3 scripts/personal_intake.py

You can skip any question with empty input. Anything you answer gets
staged as a Second Brain proposal (high-stakes areas) or written
directly (low-stakes areas) following the same risk rules JARVIS uses.

Designed to be re-runnable safely — duplicate proposals are caught by
the proposal system on review.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


PERSONAL_MODEL_SECTIONS = [
    ("Interests & Hobbies",
     "What do you currently spend time on outside work? Hobbies, interests, things you enjoy.",
     "Reads non-fiction books, plays Apex Legends and Fortnite, watches anime, listens to music daily."),

    ("Energy Patterns",
     "When are you most productive? Any clear rhythms — morning person, late-night focus, etc.",
     "Most productive late at night, often picks up again after waking around midnight."),

    ("Decision-Making Style",
     "How do you approach decisions? Quick gut calls? Research-heavy? Avoidance under uncertainty?",
     "Decisive when locked in. Procrastinates when overwhelmed. Tends to delay decisions when emotional."),

    ("Communication Preferences",
     "How do you like people to talk to you? Direct vs gentle? Brief vs thorough? Pushback vs validation?",
     "Direct, dry, witty. Tolerates sarcasm. Wants pushback when wrong, not validation."),

    ("Known Challenges",
     "What gets in your way? Distractions, patterns you fall into, things you've identified as obstacles.",
     "Apex Legends and Fortnite are major distraction vectors. Procrastinates hard once it starts."),

    ("Relationship Patterns",
     "How do you relate to family / friends / collaborators? Anything important about your dynamics?",
     "Trusts family. Long-term family business plan (Nexel). Especially close to mom."),
]

CORE_QUESTIONS = [
    # (area, title, prompt, instruction)
    ("Goals", "Active Long-Term Goals",
     "What are your top 3-5 long-term goals right now? One per line.",
     "Write them down whether or not you've told anyone. No filtering."),

    ("Personal", "Daily Rhythm",
     "Describe a typical day. Sleep, work, training, food, downtime — broad strokes.",
     "No need for precision. The model just needs to know the shape."),

    ("Personal", "Current Reading",
     "What books are you reading or want to read soon?",
     "Title + author per line is enough."),

    ("Relationships", "Inner Circle",
     "Who matters most in your life right now? Names + one-line context for each.",
     "Family by default — anyone else who's in the small inner circle."),

    ("Business", "Active Ventures",
     "What businesses or projects are you actively working on?",
     "Name + one-line description of current state."),

    ("Decisions", "Open Decisions",
     "What decisions are you currently working through? Things you haven't resolved yet.",
     "Even half-formed ones count. The vault is the place for these."),
]


def ask(prompt, instruction=None, multiline=True):
    """Get input from the user. Empty input = skip."""
    print()
    print("─" * 72)
    print(prompt)
    if instruction:
        print(f"  ({instruction})")
    print("─" * 72)
    if multiline:
        print("(Type your answer. Empty line on its own to finish, or just Enter to skip.)")
        lines = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if not line.strip() and not lines:
                return ""  # skip
            if not line.strip():
                break
            lines.append(line)
        return "\n".join(lines).strip()
    else:
        try:
            return input("> ").strip()
        except EOFError:
            return ""


def main():
    print()
    print("═" * 72)
    print("  Personal Second Brain — Initial Intake")
    print("═" * 72)
    print()
    print("  This walks through a one-time seeding of your Personal Model")
    print("  and core vault notes. Everything you answer here gets staged")
    print("  as proposals you can review and approve. Skip anything you")
    print("  don't want to answer right now — you can re-run this later.")
    print()
    print("  Vault: ~/Documents/SecondBrain/")
    print()

    try:
        from memory.vault import VaultManager
    except Exception as e:
        print(f"  ERROR: Vault module unavailable — {e}")
        return 1

    vm = VaultManager()
    print(f"  Vault confirmed at: {vm.vault_path}")
    print()
    print("  Ready? Press Enter to start.")
    try:
        input()
    except EOFError:
        pass

    # ── Personal Model section ────────────────────────────────────────────
    print()
    print("PART 1 — Personal Model")
    print("These go directly to _JARVIS/_PersonalModel.md as proposals.")

    pm_proposals = 0
    for section, prompt, example in PERSONAL_MODEL_SECTIONS:
        answer = ask(
            f"[{section}]\n  {prompt}",
            instruction=f"Example shape: {example}",
        )
        if not answer:
            print("  (skipped)")
            continue
        try:
            result = vm.update_personal_model(
                section=section,
                content=answer,
                source="personal intake script",
                supporting_observations="provided directly by Elnatan during intake",
            )
            print(f"  → {result}")
            pm_proposals += 1
        except Exception as e:
            print(f"  ERROR staging proposal: {e}")

    # ── Core vault notes ──────────────────────────────────────────────────
    print()
    print("PART 2 — Core Vault Notes")
    print("These get staged as proposals in the matching vault area.")

    core_proposals = 0
    for area, title, prompt, instruction in CORE_QUESTIONS:
        answer = ask(f"[{area}/{title}]\n  {prompt}", instruction=instruction)
        if not answer:
            print("  (skipped)")
            continue
        try:
            result = vm.propose_change(
                title=title,
                proposed_content=answer,
                action="create",
                area=area,
                source="personal intake script",
                reason="seeded during initial intake",
            )
            print(f"  → {result}")
            core_proposals += 1
        except Exception as e:
            print(f"  ERROR staging proposal: {e}")

    # ── Summary ───────────────────────────────────────────────────────────
    print()
    print("═" * 72)
    print(f"  Intake complete.")
    print(f"  Personal Model proposals staged:  {pm_proposals}")
    print(f"  Core vault note proposals staged: {core_proposals}")
    print()
    print(f"  Review and approve via JARVIS:")
    print(f"    > 'show my pending brain proposals'")
    print(f"    > 'approve all low risk'  (then handle high-risk ones one by one)")
    print()
    print(f"  Or open ~/Documents/SecondBrain/_JARVIS/Proposals/ in Obsidian.")
    print("═" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
