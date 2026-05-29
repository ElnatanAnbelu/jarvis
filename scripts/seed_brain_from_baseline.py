#!/usr/bin/env python3
"""
Seed the Personal Second Brain with the baseline profile content
that has been accumulated across JARVIS's prompt context files
(elnatan_profile.md, business_context.md, life_context.md, and the
original JARVIS_SYSTEM inline profile).

This is one-time bootstrap. Most items route through the proposal flow
(per area risk rules); only low-risk areas (Learning, Daily, Archive)
auto-write. After running, ask JARVIS:

    show my pending brain proposals
    approve all low risk

Then go through the high-risk ones (Relationships, Business, Decisions,
Personal Model) one by one.

Source attribution: "JARVIS context profile (vetted)" — this content
was already vetted in the prompt system; we're moving it to the
proper structured home.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

SOURCE = "JARVIS context profile (vetted)"


# ── Personal Model sections (always propose, high-stakes) ────────────────────
PERSONAL_MODEL = [
    ("Interests & Hobbies",
     "Loves anime deeply. Plays Apex Legends and Fortnite (these are major "
     "distraction vectors when focus slips). Music is a big part of daily life "
     "— style varies. Reading is part of the rhythm; currently working through "
     "non-fiction.",
     "Recurring themes across prompt context and observed behavior"),

    ("Energy Patterns",
     "Sleeps early. Often wakes at midnight to work more — the late-night/early-"
     "morning window is when execution tends to happen. When locked in, nearly "
     "unstoppable on things with genuine passion. When distracted, procrastinates "
     "hard and the spiral continues until something breaks it.",
     "Documented in baseline profile, confirmed by repeated patterns"),

    ("Decision-Making Style",
     "Decisive when locked in. Hesitates and delays decisions when emotionally "
     "weighted or uncertain. Has a strong sense of his own direction (stay in "
     "Africa long-term, build generational wealth, family-first). Doesn't "
     "outsource the big choices.",
     "Baseline profile + observed pattern across sessions"),

    ("Communication Preferences",
     "Witty, sarcastic, playful, confident. Tolerates and prefers direct "
     "pushback over warm validation. Doesn't want overly emotional or "
     "philosophical replies. Responds well to dry, precise observation. Hates "
     "filler — open with the answer or the action.",
     "Baseline profile + consistent tone preferences in the JARVIS persona"),

    ("Known Challenges",
     "Apex Legends and Fortnite are the documented major distraction vectors. "
     "Procrastinates hard once it starts — typically self-reinforcing until "
     "interrupted. Not deeply invested in his formal degree at DSU. Currently "
     "balancing university obligations with building real businesses.",
     "Baseline profile"),

    ("Relationship Patterns",
     "Trusts family. Long-term family business plan via Nexel. Especially close "
     "to mom (tells her everything). Close to dad (main income source / mentor "
     "figure). Inner circle is tight; trusts very few people outside that "
     "circle. Sees the world through family-first lens.",
     "Baseline profile"),
]

# ── Core notes, organized by area ────────────────────────────────────────────
NOTES = [
    # Personal area (medium risk → propose)
    ("Personal", "About Me",
     "20 years old. Ethiopian man. Cyber Operations major at Dakota State "
     "University (DSU) in Madison, SD. Currently in Addis Ababa on vacation as "
     "of recent records. Sees himself as a lucky man. Upper middle class family "
     "background. Single. Natural people person. Wants to stay in Africa / "
     "Ethiopia long-term."),

    ("Personal", "Self View",
     "Driven by goals and the desire to retire his family and build generational "
     "wealth. Sees himself as lucky. Believes when locked in, he is unstoppable "
     "at anything he has genuine passion for."),

    ("Personal", "Income & Finances",
     "Only current income: on-campus kitchen job at DSU. Funded by family — "
     "dad (Adugna) is the main income source. Dad owns a school with multiple "
     "campuses in Ethiopia."),

    # Goals area (medium risk → propose)
    ("Goals", "Long-Term Goals",
     "1. Retire his family — make sure they don't have to worry about money\n"
     "2. Build generational wealth\n"
     "3. Stay in Africa / Ethiopia long-term\n"
     "4. Get Addis Market big enough to be a real foundation\n"
     "5. Eventually formally launch Nexel as the family empire holding company\n"
     "6. Not become \"just another startup founder\" — build something durable"),

    ("Goals", "Core Fears",
     "1. Losing people he loves\n"
     "2. Not becoming rich\n"
     "3. Not achieving his goals\n"
     "4. Not making Nexel big\n\n"
     "These fears function as drivers — name them honestly when relevant rather "
     "than working around them."),

    # Business area (HIGH risk → propose)
    ("Business", "Addis Market",
     "Ethiopian-first marketplace app. Main active venture. Vision: physical "
     "shops get online storefronts; future delivery network creates jobs for "
     "delivery people (similar to Amazon / Shop model). Direct competition with "
     "informal Ethiopian commerce channels — Telegram shops, Facebook "
     "Marketplace. Code is on another laptop, in active development. Cash flow "
     "and vendor acquisition are the current main concerns."),

    ("Business", "Nexel",
     "The family empire holding company. Parent vehicle for every business "
     "Elnatan and his family build long-term. Family-only by design: him, "
     "Yostina, Eyonabel, Abigail, mom, dad. Generational wealth vehicle. "
     "Strategic order: get Addis Market big first, then formally launch Nexel."),

    ("Business", "Dad's School",
     "Father Adugna owns a school with multiple campuses in Ethiopia. Primary "
     "family income source. Important context — not a venture Elnatan runs, "
     "but the financial foundation he's currently operating from."),

    # Relationships area (HIGH risk → propose)
    ("Relationships", "Mom — Nitsuh Zenebe Girmay",
     "Extremely close. Tells her everything. Remarried to Eyon (stepdad). "
     "Birthday: October 14. The primary emotional center of his inner circle."),

    ("Relationships", "Dad — Adugna Anbelu Ejigu",
     "Close. Main income source. Parents separated; dad remarried to Ruth. "
     "Owns a school with multiple campuses in Ethiopia. Mentor figure and the "
     "financial foundation for the current building season."),

    ("Relationships", "Yostina Adugna Anbelu",
     "Older sister. Part of the Nexel family-only inner circle."),

    ("Relationships", "Eyonabel Adugna Anbelu",
     "Little brother. Part of the Nexel family-only inner circle."),

    ("Relationships", "Abigail Eyob",
     "Little sister. Part of the Nexel family-only inner circle."),

    ("Relationships", "Half-Siblings & Extended",
     "Half-siblings: Tobi, Dudu, Abigail (second), Meadot, Emma.\n"
     "Close cousins (not blood): Kiki, Kidus, Dawit.\n\n"
     "Inner trust circle is tight by design — family by default, very few "
     "outsiders."),

    # Daily area (low risk → AUTO-WRITES)
    ("Daily", "Sleep Pattern",
     "Generally sleeps early. Often wakes around midnight to work more. The "
     "late-night / pre-dawn window is the most consistent execution window."),

    ("Daily", "Training",
     "Actively working out. Was on a diet at recorded time. Wants better "
     "physique. Bench press tracked previously."),

    # Learning area (low risk → AUTO-WRITES)
    ("Learning", "Reading Style",
     "Has an active reading list. Reads non-fiction. Previously mentioned "
     "\"Open\" by Andre Agassi (or \"Zero to Zero\" — recorded variation). "
     "Reading is part of the steady-state rhythm, not bursty."),

    ("Learning", "DSU Cyber Operations",
     "Major: Cyber Operations. At Dakota State University, Madison, SD. Not "
     "deeply invested in the formal degree — sees more value in what he's "
     "building. Considers internships but finds the job market hard. Treats "
     "the degree as something to complete rather than a primary path."),
]


def main():
    print()
    print("═" * 72)
    print("  Seeding Personal Second Brain from baseline profile")
    print("═" * 72)
    print()

    try:
        from memory.vault import VaultManager
    except Exception as e:
        print(f"  ERROR: Vault module unavailable — {e}")
        return 1

    vm = VaultManager()
    print(f"  Vault: {vm.vault_path}")
    print()

    pm_count = 0
    note_count = 0
    auto_writes = 0

    # ── Personal Model — always proposes ─────────────────────────────────
    print("PART 1 — Personal Model sections")
    for section, content, evidence in PERSONAL_MODEL:
        try:
            r = vm.update_personal_model(
                section=section, content=content,
                source=SOURCE, supporting_observations=evidence,
            )
            print(f"  [{section}] → staged")
            pm_count += 1
        except Exception as e:
            print(f"  [{section}] ERROR: {e}")
    print(f"  Subtotal: {pm_count} Personal Model proposals staged")

    # ── Core notes ──────────────────────────────────────────────────────
    print()
    print("PART 2 — Core area notes")
    for area, title, content in NOTES:
        try:
            r = vm.create_note(
                title=title, content=content, area=area, source=SOURCE,
            )
            r_lower = r.lower()
            if "created" in r_lower:
                print(f"  [{area}/{title}] → auto-written")
                auto_writes += 1
            elif "proposal" in r_lower or "proposed" in r_lower:
                print(f"  [{area}/{title}] → proposal staged")
                note_count += 1
            else:
                print(f"  [{area}/{title}] → {r}")
        except Exception as e:
            print(f"  [{area}/{title}] ERROR: {e}")

    # ── Summary ─────────────────────────────────────────────────────────
    print()
    print("═" * 72)
    print(f"  Seed complete.")
    print(f"  Personal Model proposals:  {pm_count}")
    print(f"  Note proposals (high/med): {note_count}")
    print(f"  Auto-written (low-risk):   {auto_writes}")
    print()
    print(f"  Review proposals:")
    print(f"    Ask JARVIS: 'show my pending brain proposals'")
    print(f"    Or open: ~/Documents/SecondBrain/_JARVIS/Proposals/")
    print(f"  After review, ask: 'approve all low risk' for bulk approval.")
    print("═" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
