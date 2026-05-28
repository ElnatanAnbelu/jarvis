"""
VaultManager — idempotent scaffold for the JARVIS Second Brain Obsidian vault.

Mirrors the singleton pattern used in memory/wiki.py.
All filesystem operations are idempotent: safe to call multiple times.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────────────────

DEFAULT_VAULT_PATH = Path.home() / "Documents" / "SecondBrain"

# Area folders that form the top-level structure
AREA_FOLDERS = [
    "Personal",
    "Business",
    "Learning",
    "Relationships",
    "Goals",
    "Decisions",
    "Daily",
    "Archive",
]

# Relative paths inside the vault root
JARVIS_DIR        = Path("_JARVIS")
PROPOSALS_DIR     = JARVIS_DIR / "Proposals"
ACTIVITY_MD       = JARVIS_DIR / "_Activity.md"
ACTIVITY_JSONL    = JARVIS_DIR / "_Activity.jsonl"
PERSONAL_MODEL_MD = JARVIS_DIR / "_PersonalModel.md"

# Risk levels used by _log_activity
AREA_RISK = {
    "Personal":      "medium",
    "Business":      "high",
    "Relationships": "high",
    "Goals":         "medium",
    "Decisions":     "high",
    "Learning":      "low",
    "Daily":         "low",
    "Archive":       "low",
    "_JARVIS":       "low",
}

# ── Module-level singleton state ───────────────────────────────────────────────

_vm_instance = None
_vm_lock = threading.Lock()

# ── Scaffold content ───────────────────────────────────────────────────────────

_ACTIVITY_MD_HEADER = (
    "# JARVIS Activity Log\n\n"
    "This file records every write action JARVIS takes on the Second Brain.\n"
    "It is append-only. Do not edit manually.\n\n"
    "---\n\n"
)

_PERSONAL_MODEL_CONTENT = (
    "# Personal Model — Elnatan Anbelu\n"
    "*Last updated: never — awaiting first observations*\n\n"
    "## Interests & Hobbies\n\n"
    "## Energy Patterns\n\n"
    "## Decision-Making Style\n\n"
    "## Communication Preferences\n\n"
    "## Known Challenges\n\n"
    "## Relationship Patterns\n"
)

_ABOUT_ME_CONTENT = "# About Me\n\n*This is your space. Add what matters.*\n"

_LONG_TERM_GOALS_CONTENT = "# Long-Term Goals\n"

_DAILY_README_CONTENT = (
    "# Daily Notes\n\n"
    "Use this folder for day notes and quick captures.\n"
    "Create notes named `YYYY-MM-DD.md` for each day.\n"
)


# ── VaultManager ───────────────────────────────────────────────────────────────

class VaultManager:
    """
    Manages the JARVIS Obsidian vault: scaffold creation, activity logging,
    and (in later tasks) note read/write and personal model updates.

    Usage
    -----
    vm = VaultManager()                          # uses DEFAULT_VAULT_PATH
    vm = VaultManager(vault_path=Path("/tmp/x")) # for tests / custom path
    """

    def __init__(self, vault_path=None):
        self.vault_path = Path(vault_path) if vault_path else DEFAULT_VAULT_PATH
        # FAISS index state — populated in later tasks
        self._index = None
        self._chunks: list = []
        self._titles: list = []
        self._model = None
        self._index_lock = threading.Lock()

        self._ensure_vault()

    # ── Bootstrap ──────────────────────────────────────────────────────────────

    def _ensure_vault(self):
        """
        Idempotently create the full vault scaffold.

        The vault_init activity entry is written only on the first-ever
        creation (when the vault root did not exist before this call).
        """
        vault = self.vault_path
        is_new = not vault.exists()

        # Root
        vault.mkdir(parents=True, exist_ok=True)

        # Area folders
        for area in AREA_FOLDERS:
            (vault / area).mkdir(exist_ok=True)

        # _JARVIS folders
        (vault / JARVIS_DIR).mkdir(exist_ok=True)
        (vault / PROPOSALS_DIR).mkdir(exist_ok=True)

        # Scaffold files
        self._create_stub(ACTIVITY_MD,       _ACTIVITY_MD_HEADER)
        self._create_stub(ACTIVITY_JSONL,    "")
        self._create_stub(PERSONAL_MODEL_MD, _PERSONAL_MODEL_CONTENT)
        self._create_stub(Path("Personal") / "About Me.md",        _ABOUT_ME_CONTENT)
        self._create_stub(Path("Goals")    / "Long-Term Goals.md", _LONG_TERM_GOALS_CONTENT)
        self._create_stub(Path("Daily")    / "README.md",          _DAILY_README_CONTENT)

        # Log vault_init only once — on first creation
        if is_new:
            self._log_activity(
                action="vault_init",
                note="_JARVIS/_Activity.md",
                source="VaultManager._ensure_vault",
                summary="Vault scaffolded for the first time.",
                risk="low",
            )

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _create_stub(self, rel_path: Path, content: str):
        """Create a file at vault_path/rel_path only if it does not exist."""
        target = self.vault_path / rel_path
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def _log_activity(self, action: str, note: str, source: str,
                      summary: str, risk: str = "low"):
        """
        Append one entry to both _Activity.md and _Activity.jsonl.

        Implemented as a real write here (not a stub) so that the
        idempotency test can verify exactly one vault_init entry.
        The full activity-log API (Task 3) will expand this.
        """
        ts = datetime.now(timezone.utc).isoformat()

        # JSON record
        record = {
            "ts": ts,
            "action": action,
            "note": note,
            "source": source,
            "summary": summary,
            "risk": risk,
        }
        jsonl_path = self.vault_path / ACTIVITY_JSONL
        with jsonl_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

        # Human-readable markdown entry
        md_path = self.vault_path / ACTIVITY_MD
        md_line = f"- `{ts}` **{action}** — {summary} *(risk: {risk})*\n"
        with md_path.open("a", encoding="utf-8") as fh:
            fh.write(md_line)
