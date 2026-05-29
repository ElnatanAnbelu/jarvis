"""
VaultManager — idempotent scaffold for the JARVIS Second Brain Obsidian vault.

All filesystem operations are idempotent: safe to call multiple times.
"""

import hashlib
import json
import re
import threading
import time as _time
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

# Central-hub backlink footer. Appended to every new note (create + propose)
# so Obsidian's graph view shows the three identity hubs (Elnatan, JARVIS,
# Claude Code) connected to everything.
_BACKLINK_FOOTER = "\n\n---\n*Linked: [[Elnatan]] · [[JARVIS]] · [[Claude Code]]*\n"


def _with_backlinks(body: str) -> str:
    """Append the central-hub backlink footer if it isn't already present."""
    if body and "[[Claude Code]]" in body:
        return body
    return body.rstrip() + _BACKLINK_FOOTER


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
        # FAISS index state (initialized here, built lazily in background)
        self._index = None
        self._chunks: list = []
        self._titles: list = []
        self._index_lock = threading.Lock()
        self._last_build: float = 0.0
        self._building: bool = False
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

    # Known vault-init stub signatures. A file matching one of these is
    # considered a placeholder created by _ensure_vault and may be safely
    # overwritten when an approval lands content for the same target.
    _INIT_STUB_SIGNATURES = frozenset([
        _ABOUT_ME_CONTENT,
        _LONG_TERM_GOALS_CONTENT,
        _DAILY_README_CONTENT,
    ])

    def _is_init_stub(self, path: Path) -> bool:
        """Return True if the file content matches one of the known init
        stub signatures — meaning it has never had real content written
        to it and is safe to overwrite on approval."""
        try:
            return path.read_text(encoding="utf-8") in self._INIT_STUB_SIGNATURES
        except Exception:
            return False

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
        # Also check _JARVIS folder for special notes like _PersonalModel
        p = self.vault_path / "_JARVIS" / f"{self._safe_title(title_or_path)}.md"
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

    # ── Proposal system ────────────────────────────────────────────────────────

    def _proposal_subfolder(self, area: str, title: str) -> str:
        """Decide which subfolder under Proposals/ a given proposal lives in.

        Personal Model updates (target _PersonalModel in _JARVIS area) get
        their own dedicated 'Personal Model' subfolder so the 6 sections
        live together. Everything else uses its area name.
        """
        safe_title = (title or "").strip()
        if area == "_JARVIS" and "_PersonalModel" in safe_title:
            return "Personal Model"
        if area == "_JARVIS":
            return "_JARVIS"
        # Strip path separators from area just in case
        return re.sub(r'[<>:"/\\|?*]', '', area).strip() or "Other"

    def _build_proposal_id(self, area: str, title: str) -> tuple:
        """Build a descriptive proposal ID + relative path from area + title.

        Returns (proposal_id, relative_path). The proposal lives in a
        subfolder named for its area. The filename and proposal_id are
        the clean title (no area prefix — the subfolder already shows
        that). On collision, ' (N)' is appended.

        Examples:
          ('Business', 'Addis Market') →
              ('Addis Market', Path('Business/Addis Market.md'))
          ('_JARVIS', 'Personal Model — Energy Patterns') →
              ('Personal Model — Energy Patterns',
               Path('Personal Model/Personal Model — Energy Patterns.md'))
        """
        safe_title = self._safe_title(title)
        subfolder = self._proposal_subfolder(area, title)
        proposals_dir = self.vault_path / "_JARVIS" / "Proposals" / subfolder
        proposal_id = safe_title
        base = safe_title
        filename = f"{base}.md"
        n = 2
        while (proposals_dir / filename).exists():
            filename = f"{base} ({n}).md"
            n += 1
        rel_path = Path(subfolder) / filename
        return proposal_id, rel_path

    def _find_proposal_path(self, proposal_id: str) -> Optional[Path]:
        """Look up an *active* proposal file by its ID. The ID is the
        clean title. Searches all subfolders under Proposals/ but
        SKIPS the _Archive folder — archived proposals are finalized
        and shouldn't show up as if they were live.
        """
        proposals_dir = self.vault_path / "_JARVIS" / "Proposals"
        if not proposals_dir.exists():
            return None

        def _is_archived(path: Path) -> bool:
            try:
                rel = path.relative_to(proposals_dir).parts
                return len(rel) > 0 and rel[0] == "_Archive"
            except Exception:
                return False

        # Exact filename match (recursive, excluding archive)
        for p in proposals_dir.rglob(f"{proposal_id}.md"):
            if not _is_archived(p):
                return p
        # Collision suffix match
        for p in proposals_dir.rglob(f"{proposal_id} (*).md"):
            if not _is_archived(p):
                return p
        # Legacy: bare flat-folder filename
        legacy = proposals_dir / f"{proposal_id}.md"
        if legacy.exists():
            return legacy
        # Legacy: search by proposal_id frontmatter field
        for p in proposals_dir.rglob("*.md"):
            if _is_archived(p):
                continue
            fm = self._parse_frontmatter(p)
            if fm.get("proposal_id") == proposal_id:
                return p
        return None

    def propose_change(self, title: str, proposed_content: str, action: str,
                       area: str, source: str, reason: str,
                       sensitivity: str = "low",
                       target_note_override: Optional[str] = None,
                       display_title: Optional[str] = None) -> str:
        """Stage a change as a proposal.

        target_note_override: If set, this string becomes the target_note
            frontmatter field (used at approval time to find the note to
            update). Defaults to "{area}/{title}".
        display_title: If set, this is what shows up in the filename and
            proposal_id. Defaults to title. Use when you want a more
            descriptive filename than the actual target title (e.g.
            Personal Model section updates).
        """
        title_for_display = display_title or title
        proposal_id, rel_path = self._build_proposal_id(area, title_for_display)
        target = target_note_override or f"{area}/{self._safe_title(title)}"
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        # Capture current note hash for stale detection at approval time
        existing_path = self._resolve_note_path(target)
        current_hash = ""
        if existing_path and existing_path.exists():
            current_hash = self._compute_hash(self._body_only(existing_path.read_text(encoding="utf-8")))

        fm_lines = [
            "---",
            f"proposal_id: {proposal_id}",
            f"status: pending",
            f"proposed_at: {now}",
            f"target_note: {target}",
            f"action: {action}",
            f"area: {area}",
            f"risk: {AREA_RISK.get(area, 'medium')}",
            f"sensitivity: {sensitivity}",
            f'source: "{source}"',
            f'reason: "{reason}"',
            f"hash_at_proposal: {current_hash}",
            "---",
        ]
        attribution = f"> *JARVIS: proposed from {source} on {datetime.now(timezone.utc).strftime('%Y-%m-%d')}*"
        body = "\n".join(fm_lines) + _with_backlinks(
            f"\n\n# Proposed Content\n\n{attribution}\n\n{proposed_content}\n"
        )

        # Descriptive filename in a subfolder by area. Collision-handled.
        proposal_path = self.vault_path / "_JARVIS" / "Proposals" / rel_path
        proposal_path.parent.mkdir(parents=True, exist_ok=True)
        proposal_path.write_text(body, encoding="utf-8")
        self._log_activity("propose", target, source,
                           f"Proposed {action}: {title}", risk=AREA_RISK.get(area, "medium"))
        return f"Proposal created: {proposal_id} — review with `review_proposals`"

    # ── Proposal review ────────────────────────────────────────────────────────

    def get_pending_proposals(self) -> str:
        proposals_dir = self.vault_path / "_JARVIS" / "Proposals"
        pending = []
        # rglob to handle subfolder organization (Business/, Personal/, etc.)
        for p in sorted(proposals_dir.rglob("*.md")):
            fm = self._parse_frontmatter(p)
            if fm.get("status") == "pending":
                pid = fm.get("proposal_id", p.stem)
                target = fm.get("target_note", "unknown")
                action = fm.get("action", "?")
                risk = fm.get("risk", "?")
                reason = fm.get("reason", "").strip('"')
                pending.append(
                    f"[{pid}] {target} — {action} ({risk} risk)\n  Reason: {reason}"
                )
        if not pending:
            return "No pending proposals."
        return "Pending proposals:\n\n" + "\n\n".join(pending)

    def approve_proposal(self, proposal_id: str) -> str:
        p = self._find_proposal_path(proposal_id)
        if p is None:
            return f"Proposal not found: {proposal_id}"

        fm = self._parse_frontmatter(p)
        target = fm.get("target_note", "")
        action = fm.get("action", "create")
        hash_at_proposal = fm.get("hash_at_proposal", "")

        # Extract proposed content (everything after "# Proposed Content" heading)
        full_text = p.read_text(encoding="utf-8")
        content_match = re.search(r'---\n\n# Proposed Content\n\n(.*)', full_text, re.DOTALL)
        proposed_content = content_match.group(1).strip() if content_match else ""

        # Split target into area and title
        area_str, _, title_str = target.partition("/")

        # Approval-time stale check for updates
        if action == "update" and target:
            existing_path = self._resolve_note_path(target)
            if existing_path and existing_path.exists():
                current_hash = self._compute_hash(self._body_only(existing_path.read_text(encoding="utf-8")))
                if hash_at_proposal and current_hash != hash_at_proposal:
                    self._update_proposal_status(p, "stale")
                    return (
                        f"Proposal {proposal_id} is stale — `{target}` was edited "
                        f"after this proposal was created. Review `{target}` manually "
                        f"and re-propose if still relevant."
                    )

        # Apply the proposal
        source = fm.get("source", "proposal").strip('"')
        if action == "create":
            note_path = self.vault_path / area_str / f"{self._safe_title(title_str)}.md"
            note_path.parent.mkdir(parents=True, exist_ok=True)
            # Stale check for create: if file exists AND is not a vault-init stub,
            # refuse — we don't silently overwrite real human content. Init stubs
            # (empty placeholder notes created by _ensure_vault) are recognized
            # by content shape and may be safely overwritten by approval.
            if note_path.exists() and not self._is_init_stub(note_path):
                self._update_proposal_status(p, "stale")
                return (
                    f"Proposal {proposal_id} is stale — `{area_str}/{title_str}` already exists. "
                    f"Review the existing file and re-propose if still needed."
                )
            fm_new = self._build_frontmatter(
                title=title_str, area=area_str, source=source,
                created_by="jarvis"
            )
            self._write_note(note_path, fm_new, proposed_content, source)
        elif action == "update":
            existing_path = self._resolve_note_path(target)
            if existing_path:
                updated = existing_path.read_text(encoding="utf-8").rstrip()
                updated += f"\n\n{proposed_content}\n"
                existing_path.write_text(updated, encoding="utf-8")
                new_hash = self._compute_hash(self._body_only(updated))
                self._update_frontmatter_field(existing_path, "jarvis_last_hash", new_hash)

        self._update_proposal_status(p, "approved")
        self._log_activity("approve", target, "human", f"Approved proposal {proposal_id}")
        return f"Approved and applied: {proposal_id} → {target}"

    def reject_proposal(self, proposal_id: str) -> str:
        p = self._find_proposal_path(proposal_id)
        if p is None:
            return f"Proposal not found: {proposal_id}"
        self._update_proposal_status(p, "rejected")
        self._log_activity("reject", proposal_id, "human", f"Rejected proposal {proposal_id}")
        return f"Rejected: {proposal_id} (file preserved in Proposals/)"

    def _update_proposal_status(self, proposal_path: Path, status: str) -> Path:
        """Update the status field; if not pending, move to _Archive/{status}/...

        Keeps the active Proposals/ folder clean — only pending shows up
        when browsing in Obsidian. Returns the (possibly new) path.
        """
        text = proposal_path.read_text(encoding="utf-8")
        updated = re.sub(r'^(status:\s*).*$', rf'\g<1>{status}',
                         text, count=1, flags=re.MULTILINE)
        proposal_path.write_text(updated, encoding="utf-8")
        if status in ("approved", "rejected", "stale"):
            return self._archive_proposal(proposal_path, status)
        return proposal_path

    def _archive_proposal(self, proposal_path: Path, status: str) -> Path:
        """Move a finalized proposal to _Archive/{status}/{Area}/{filename}.

        Preserves the per-area subfolder structure inside the archive so
        an old approved proposal lives at e.g.
            _JARVIS/Proposals/_Archive/approved/Goals/Long-Term Goals.md
        """
        try:
            proposals_root = self.vault_path / "_JARVIS" / "Proposals"
            # The proposal's subfolder relative to Proposals/ (e.g. 'Goals')
            try:
                rel_subfolder = proposal_path.parent.relative_to(proposals_root)
            except ValueError:
                rel_subfolder = Path(".")
            archive_dir = proposals_root / "_Archive" / status / rel_subfolder
            archive_dir.mkdir(parents=True, exist_ok=True)
            new_path = archive_dir / proposal_path.name
            # Collision in the archive — append counter
            n = 2
            while new_path.exists():
                new_path = archive_dir / f"{proposal_path.stem} ({n}){proposal_path.suffix}"
                n += 1
            proposal_path.rename(new_path)
            return new_path
        except Exception:
            # If archive fails for any reason, leave the file where it was
            return proposal_path

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
        body = _with_backlinks(f"# {title}\n\n{attribution}\n\n{content}")
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

    # ── Navigation ─────────────────────────────────────────────────────────────

    def get_note(self, title_or_path: str) -> str:
        """Return the full text of a note by 'Area/Title' or just 'Title'."""
        path = self._resolve_note_path(title_or_path)
        if path is None or not path.exists():
            return f"Note not found: {title_or_path}"
        return path.read_text(encoding="utf-8")

    def list_notes(self, area: Optional[str] = None) -> str:
        """List notes in one area or all areas."""
        areas = [area] if area else list(AREA_RISK.keys())
        lines = []
        for a in areas:
            folder = self.vault_path / a
            if not folder.exists():
                continue
            notes = sorted(folder.glob("*.md"))
            if notes:
                lines.append(f"**{a}/**")
                for n in notes:
                    lines.append(f"  - {n.stem}")
        return "\n".join(lines) if lines else "No notes found."

    # ── Search ─────────────────────────────────────────────────────────────────

    def search_vault(self, query: str, max_results: int = 3) -> str:
        """Search vault using FAISS if available, otherwise keyword fallback."""
        self._ensure_index()
        with self._index_lock:
            index_ready = self._index is not None and len(self._chunks) > 0
        if index_ready:
            try:
                return self._faiss_search(query, max_results)
            except Exception:
                pass
        return self._keyword_search(query, max_results)

    def _keyword_search(self, query: str, max_notes: int = 3) -> str:
        stop = {"the", "a", "an", "is", "it", "to", "of", "and", "or", "in", "on",
                "for", "what", "how", "can", "do", "my", "me", "i"}
        words = set(re.findall(r'\w+', query.lower())) - stop
        if not words:
            return ""
        scored = []
        for area in AREA_RISK:
            folder = self.vault_path / area
            if not folder.exists():
                continue
            for note in folder.glob("*.md"):
                try:
                    orig = note.read_text(encoding="utf-8")
                    text = orig.lower()
                    score = sum(text.count(w) + (3 if w in note.stem.lower() else 0)
                                for w in words)
                    if score > 0:
                        body = re.sub(r'^---.*?---\s*', '', orig,
                                      flags=re.DOTALL).strip()
                        scored.append((score, f"{area}/{note.stem}", body))
                except Exception:
                    continue
        scored.sort(reverse=True)
        if not scored:
            return ""
        parts = [f"### {title}\n{body[:500]}" for _, title, body in scored[:max_notes]]
        return "\n\n".join(parts)

    # ── FAISS infrastructure ───────────────────────────────────────────────────

    def _notes_mtime(self) -> float:
        try:
            mtimes = []
            for area in AREA_RISK:
                folder = self.vault_path / area
                if folder.exists():
                    mtimes.extend(p.stat().st_mtime for p in folder.glob("*.md"))
            return max(mtimes, default=0.0)
        except Exception:
            return 0.0

    def _ensure_index(self):
        with self._index_lock:
            needs_rebuild = (self._index is None or
                (self._notes_mtime() > self._last_build and
                 (_time.time() - self._last_build) > 60))
        should_build = False
        with self._index_lock:
            if needs_rebuild and not self._building:
                self._building = True
                should_build = True
        if should_build:
            t = threading.Thread(target=self._build_index_bg, daemon=True)
            t.start()

    def _build_index_bg(self):
        try:
            self._build_faiss_index()
        except Exception:
            pass
        finally:
            self._building = False

    def _build_faiss_index(self):
        try:
            import numpy as np
            import faiss
            from sentence_transformers import SentenceTransformer
        except ImportError:
            return  # gracefully skip if not installed
        chunks, titles = [], []
        for area in AREA_RISK:
            folder = self.vault_path / area
            if not folder.exists():
                continue
            for note in folder.glob("*.md"):
                try:
                    body = re.sub(r'^---.*?---\s*', '',
                                  note.read_text(encoding="utf-8"),
                                  flags=re.DOTALL).strip()
                    words = body.split()
                    for i in range(0, len(words), 80):
                        chunks.append(" ".join(words[i:i+80]))
                        titles.append(f"{area}/{note.stem}")
                except Exception:
                    continue
        if not chunks:
            return
        model = SentenceTransformer("all-MiniLM-L6-v2")
        emb = model.encode(chunks, normalize_embeddings=True, show_progress_bar=False)
        emb = np.array(emb, dtype="float32")
        index = faiss.IndexFlatIP(emb.shape[1])
        index.add(emb)
        with self._index_lock:
            self._index = index
            self._chunks = chunks
            self._titles = titles
            self._last_build = _time.time()

    # ── Personal Model ─────────────────────────────────────────────────────────

    def update_personal_model(self, section: str, content: str,
                              source: str, supporting_observations: str = "") -> str:
        """Propose an update to the Personal Model — never writes directly."""
        evidence_block = ""
        if supporting_observations:
            evidence_block = f"\n\n*Supporting evidence: {supporting_observations}*"
        full_content = (
            f"### {section}\n\n{content}{evidence_block}\n\n"
            f"*Proposed update — requires review*"
        )
        return self.propose_change(
            title="_PersonalModel",
            display_title=f"Personal Model — {section}",
            proposed_content=full_content,
            action="update",
            area="_JARVIS",
            source=source,
            reason=f"Personal Model update: {section}",
            sensitivity="high",
        )

    def _faiss_search(self, query: str, max_results: int = 3) -> str:
        import numpy as np
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        q = np.array(model.encode([query], normalize_embeddings=True), dtype="float32")
        with self._index_lock:
            scores, indices = self._index.search(q, min(max_results * 3, len(self._chunks)))
        seen, results = set(), []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or score < 0.25:
                continue
            title = self._titles[idx]
            if title in seen:
                continue
            seen.add(title)
            results.append(f"### {title}\n{self._chunks[idx]}")
            if len(results) >= max_results:
                break
        return "\n\n".join(results)
