"""
VaultManager — idempotent scaffold for the JARVIS Second Brain Obsidian vault.

All filesystem operations are idempotent: safe to call multiple times.
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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

# Risk level per area — drives the proposal flow in _should_propose
AREA_RISK = {
    "Business":      "high",
    "Relationships": "high",
    "Decisions":     "high",
    "Personal":      "medium",
    "Goals":         "medium",
    "Learning":      "low",
    "Daily":         "low",
    "Archive":       "low",
}

# Relative paths inside the vault root
JARVIS_DIR        = Path("_JARVIS")
PROPOSALS_DIR     = JARVIS_DIR / "Proposals"
ACTIVITY_MD       = JARVIS_DIR / "_Activity.md"
ACTIVITY_JSONL    = JARVIS_DIR / "_Activity.jsonl"
PERSONAL_MODEL_MD = JARVIS_DIR / "_PersonalModel.md"

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

        _Activity.md  — human-readable markdown with section headers.
        _Activity.jsonl — one JSON record per line (machine-readable).
        """
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        # Human-readable markdown (append-only)
        md_entry = (
            f"\n## {ts} | {action} | {note}\n"
            f"- **Source**: {source}\n"
            f"- **Summary**: {summary}\n"
        )
        act_md = self.vault_path / ACTIVITY_MD
        try:
            with open(act_md, "a", encoding="utf-8") as f:
                f.write(md_entry)
        except Exception:
            pass

        # Machine-readable JSONL (one record per line)
        record = {"ts": ts, "action": action, "note": note,
                  "source": source, "summary": summary, "risk": risk}
        act_jsonl = self.vault_path / ACTIVITY_JSONL
        try:
            with open(act_jsonl, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass

    # ── Note format utilities ──────────────────────────────────────────────────

    def _compute_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _build_frontmatter(self, title: str, area: str, source: str,
                           sensitivity: str = "low", created_by: str = "jarvis",
                           tags: list = None, extra: dict = None) -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        tag_str = "[" + ", ".join(tags) + "]" if tags else "[]"
        lines = [
            "---",
            f"title: {title}",
            f"area: {area}",
            f"tags: {tag_str}",
            f"created: {now}",
            f"updated: {now}",
            f"created_by: {created_by}",
            f"last_edited_by: {created_by}",
            f"jarvis_last_hash: placeholder",
            f"sensitivity: {sensitivity}",
            f'source: "{source}"',
        ]
        if extra:
            for k, v in extra.items():
                lines.append(f"{k}: {v}")
        lines.append("---")
        return "\n".join(lines)

    def _parse_frontmatter(self, path: Path) -> dict:
        """Extract YAML frontmatter as a dict. Returns {} if none."""
        try:
            text = path.read_text(encoding="utf-8")
            m = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
            if not m:
                return {}
            result = {}
            for line in m.group(1).splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    result[k.strip()] = v.strip().strip('"')
            return result
        except Exception:
            return {}

    def _update_frontmatter_field(self, path: Path, field: str, value: str):
        """Update a single frontmatter field in an existing note."""
        try:
            text = path.read_text(encoding="utf-8")
            pattern = rf'(^{re.escape(field)}:\s*)(.*)$'
            new_text = re.sub(pattern, rf'\g<1>{value}', text,
                              count=1, flags=re.MULTILINE)
            path.write_text(new_text, encoding="utf-8")
        except Exception:
            pass

    def _should_propose(self, area: str, sensitivity: str,
                        has_human_edits: bool) -> bool:
        """Return True if this write must go through the proposal flow."""
        if has_human_edits:
            return True
        if sensitivity == "high":
            return True
        risk = AREA_RISK.get(area, "medium")
        return risk in ("high", "medium")

    def _safe_title(self, title: str) -> str:
        return re.sub(r'[<>:"/\\|?*]', '', title).strip()

    # ── Note path resolution ───────────────────────────────────────────────────

    def _resolve_note_path(self, title_or_path: str) -> Optional[Path]:
        """Find a note by 'Area/Title' or just 'Title' (searches all areas)."""
        if "/" in title_or_path:
            area, _, title = title_or_path.partition("/")
            p = self.vault_path / area / f"{self._safe_title(title)}.md"
            return p if p.exists() else None
        for area in AREA_RISK:
            p = self.vault_path / area / f"{self._safe_title(title_or_path)}.md"
            if p.exists():
                return p
        return None

    def _detect_human_edits(self, path: Path) -> bool:
        """Return True if the body has been edited since JARVIS last wrote it."""
        fm = self._parse_frontmatter(path)
        stored_hash = fm.get("jarvis_last_hash", "")
        if not stored_hash or stored_hash == "placeholder":
            return False
        current_content = path.read_text(encoding="utf-8")
        return self._compute_hash(self._body_only(current_content)) != stored_hash

    @staticmethod
    def _body_only(text: str) -> str:
        """Return the portion of a note after the closing frontmatter '---'."""
        # Skip the opening '---', content, closing '---'
        m = re.match(r'^---\n.*?\n---\n(.*)', text, re.DOTALL)
        return m.group(1) if m else text

    def _write_note(self, path: Path, frontmatter: str, body: str, source: str):
        """Write note to disk and store a hash of the body (post-frontmatter)."""
        content = frontmatter + "\n\n" + body.strip() + "\n"
        path.write_text(content, encoding="utf-8")
        # Hash only the body so the stored value is stable regardless of
        # future frontmatter field updates (updated, last_edited_by, etc.).
        body_hash = self._compute_hash(self._body_only(content))
        self._update_frontmatter_field(path, "jarvis_last_hash", body_hash)
        # Invalidate search index (Task 7 will use this)
        # Nothing to invalidate yet — placeholder comment for now

    # ── Proposal stub (Task 5 will replace this) ───────────────────────────────

    def propose_change(self, **kwargs) -> str:
        """Stub: will be replaced in Task 5."""
        title = kwargs.get("title", "?")
        area = kwargs.get("area", "")
        source = kwargs.get("source", "")
        action = kwargs.get("action", "create")
        content = kwargs.get("proposed_content", "")
        reason = kwargs.get("reason", "")

        safe = self._safe_title(title)
        proposals_dir = self.vault_path / PROPOSALS_DIR
        proposals_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        proposal_path = proposals_dir / f"{ts}_{safe}.md"
        body = (
            f"# Proposal: {action} — {title}\n\n"
            f"**Reason**: {reason}\n\n"
            f"**Area**: {area}\n\n"
            f"**Source**: {source}\n\n"
            f"## Proposed Content\n\n{content}\n"
        )
        proposal_path.write_text(body, encoding="utf-8")
        return f"proposed: {title}"

    # ── Note write operations ──────────────────────────────────────────────────

    def create_note(self, title: str, content: str, area: str, source: str,
                    tags: list = None, sensitivity: str = "low") -> str:
        """Create a new note, routing through proposal flow when required."""
        if self._should_propose(area, sensitivity, has_human_edits=False):
            return self.propose_change(
                title=title, proposed_content=content, action="create",
                area=area, source=source, reason=f"New {area} note: {title}"
            )
        safe = self._safe_title(title)
        path = self.vault_path / area / f"{safe}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        attribution = f"> *JARVIS: learned from {source}*"
        fm = self._build_frontmatter(title, area, source, sensitivity,
                                     created_by="jarvis", tags=tags or [])
        body = f"# {title}\n\n{attribution}\n\n{content}"
        self._write_note(path, fm, body, source)
        self._log_activity("create", f"{area}/{safe}", source,
                           f"Created note: {title}", risk="low")
        return f"Created: {area}/{safe}.md"

    def update_note(self, title_or_path: str, content: str, source: str,
                    sensitivity: str = "low") -> str:
        """Append content to an existing note, routing through proposal flow when required."""
        path = self._resolve_note_path(title_or_path)
        if path is None:
            return f"Note not found: {title_or_path}"
        area = path.parent.name
        has_human_edits = self._detect_human_edits(path)
        if self._should_propose(area, sensitivity, has_human_edits):
            return self.propose_change(
                title=path.stem, proposed_content=content, action="update",
                area=area, source=source,
                reason="Human edits detected — proposing update for review"
                       if has_human_edits else f"High-risk area update: {area}"
            )
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        attribution = f"> *JARVIS: updated from {source} on {now}*"
        existing = path.read_text(encoding="utf-8")
        updated = existing.rstrip() + f"\n\n{attribution}\n\n{content}\n"
        path.write_text(updated, encoding="utf-8")
        # Hash only the body so future frontmatter updates don't look like human edits
        new_hash = self._compute_hash(self._body_only(updated))
        self._update_frontmatter_field(path, "jarvis_last_hash", new_hash)
        self._update_frontmatter_field(path, "updated", now)
        self._update_frontmatter_field(path, "last_edited_by", "jarvis")
        self._log_activity("update", f"{area}/{path.stem}", source,
                           f"Updated note: {path.stem}", risk="low")
        return f"Updated: {area}/{path.stem}.md"
