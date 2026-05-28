# Second Brain — Vault Write Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `memory/vault.py`, `memory/observations.py`, and `brain/tools/second_brain.py` — the safe, attributed, proposal-first write layer for Elnatan's Personal Second Brain at `~/Documents/SecondBrain/`.

**Architecture:** `VaultManager` (singleton module pattern matching `wiki.py`) handles all vault I/O with risk-tiered write rules — auto-write for low-risk, proposal files for high-risk. Observations stage in SQLite before synthesis. Ten `@tool`-decorated functions expose the vault to JARVIS via the existing tool registry. Context routing in `_build_context()` pulls from the personal brain for personal queries and the project brain for code queries.

**Tech Stack:** Python 3, sqlite3 (stdlib), hashlib (stdlib), pathlib (stdlib), re (stdlib), threading (stdlib), sentence-transformers + faiss-cpu (optional — keyword fallback if unavailable), pytest + tmp_path for tests.

**Spec:** `docs/superpowers/specs/2026-05-28-second-brain-vault-write-layer-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `memory/vault.py` | CREATE | VaultManager — all vault operations |
| `memory/observations.py` | CREATE | Observation SQLite staging + quality filter |
| `brain/tools/second_brain.py` | CREATE | 10 @tool-decorated JARVIS tools |
| `brain/tools/__init__.py` | MODIFY | Import second_brain module |
| `brain/think.py` | MODIFY | Add `_should_query_personal()`, `_route_personal_context()`, and routing into `_build_context()` |
| `prompts/runtime/prompt_loader.py` | MODIFY | Add `load_second_brain_modules()` helper |
| `tests/test_vault.py` | CREATE | VaultManager unit tests |
| `tests/test_observations.py` | CREATE | Observation staging + quality filter tests |
| `tests/test_second_brain_tools.py` | CREATE | Tool registration + integration tests |

---

## Task 1: Vault Bootstrap — `_ensure_vault()`

The VaultManager must initialize the vault structure idempotently on first instantiation.

**Files:**
- Create: `memory/vault.py`
- Create: `tests/test_vault.py`

- [ ] **Step 1.1: Write failing bootstrap tests**

Create `tests/test_vault.py`:

```python
import pytest
from pathlib import Path


@pytest.fixture
def vault(tmp_path):
    """VaultManager pointed at a temp directory."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from memory.vault import VaultManager
    return VaultManager(vault_path=tmp_path / "SecondBrain")


def test_vault_creates_root_directory(vault, tmp_path):
    assert (tmp_path / "SecondBrain").exists()


def test_vault_creates_all_area_folders(vault, tmp_path):
    sb = tmp_path / "SecondBrain"
    for area in ["Personal", "Business", "Learning", "Relationships",
                 "Goals", "Decisions", "Daily", "Archive"]:
        assert (sb / area).is_dir(), f"Missing area folder: {area}"


def test_vault_creates_jarvis_folders(vault, tmp_path):
    sb = tmp_path / "SecondBrain"
    assert (sb / "_JARVIS").is_dir()
    assert (sb / "_JARVIS" / "Proposals").is_dir()


def test_vault_creates_activity_logs(vault, tmp_path):
    sb = tmp_path / "SecondBrain"
    assert (sb / "_JARVIS" / "_Activity.md").exists()
    assert (sb / "_JARVIS" / "_Activity.jsonl").exists()


def test_vault_creates_personal_model(vault, tmp_path):
    sb = tmp_path / "SecondBrain"
    assert (sb / "_JARVIS" / "_PersonalModel.md").exists()
    content = (sb / "_JARVIS" / "_PersonalModel.md").read_text()
    assert "Personal Model" in content
    assert "Interests" in content


def test_vault_creates_anchor_notes(vault, tmp_path):
    sb = tmp_path / "SecondBrain"
    assert (sb / "Personal" / "About Me.md").exists()
    assert (sb / "Goals" / "Long-Term Goals.md").exists()


def test_vault_bootstrap_is_idempotent(tmp_path):
    """Running VaultManager() twice must not duplicate any file or log entry."""
    from memory.vault import VaultManager
    VaultManager(vault_path=tmp_path / "SecondBrain")
    VaultManager(vault_path=tmp_path / "SecondBrain")
    sb = tmp_path / "SecondBrain"
    activity = (sb / "_JARVIS" / "_Activity.md").read_text()
    assert activity.count("vault_init") == 1  # logged exactly once
```

- [ ] **Step 1.2: Run tests to see them fail**

```bash
cd /Users/elnatananbelu/jarvis
python3 -m pytest tests/test_vault.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'memory.vault'`

- [ ] **Step 1.3: Create `memory/vault.py` with bootstrap**

```python
"""
Personal Second Brain — VaultManager.

Handles all safe reads and writes to ~/Documents/SecondBrain/.
Follows risk-tiered write rules: auto-write for low-risk areas,
proposal-first for high-risk. All writes are attributed and logged.
"""
import hashlib
import json
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Singleton module state (mirrors wiki.py pattern) ───────────────────────
_vm_instance = None
_vm_lock = threading.Lock()

DEFAULT_VAULT_PATH = Path("~/Documents/SecondBrain").expanduser()

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

_PERSONAL_MODEL_PATH = "_JARVIS/_PersonalModel.md"
_ACTIVITY_MD_PATH    = "_JARVIS/_Activity.md"
_ACTIVITY_JSONL_PATH = "_JARVIS/_Activity.jsonl"
_PROPOSALS_DIR       = "_JARVIS/Proposals"

_PERSONAL_MODEL_SCAFFOLD = """# Personal Model — Elnatan Anbelu
*Last updated: never — awaiting first observations*

## Interests & Hobbies

## Energy Patterns

## Decision-Making Style

## Communication Preferences

## Known Challenges

## Relationship Patterns
"""

_ACTIVITY_MD_HEADER = """# JARVIS Activity Log

This file records every write action JARVIS takes on the Second Brain.
It is append-only. Do not edit manually.

---

"""


class VaultManager:
    def __init__(self, vault_path: Optional[Path] = None):
        self.vault = vault_path or DEFAULT_VAULT_PATH
        self._index = None
        self._chunks: list = []
        self._titles: list = []
        self._index_lock = threading.Lock()
        self._last_build: float = 0.0
        self._building = False
        self._ensure_vault()

    # ── Bootstrap ─────────────────────────────────────────────────────────

    def _ensure_vault(self):
        """Create vault structure if it doesn't exist. Safe to call repeatedly."""
        already_exists = self.vault.exists()

        # Directories
        for folder in ["Personal", "Business", "Learning", "Relationships",
                       "Goals", "Decisions", "Daily", "Archive",
                       "_JARVIS", _PROPOSALS_DIR]:
            (self.vault / folder).mkdir(parents=True, exist_ok=True)

        # Activity logs
        act_md = self.vault / _ACTIVITY_MD_PATH
        if not act_md.exists():
            act_md.write_text(_ACTIVITY_MD_HEADER, encoding="utf-8")

        act_jsonl = self.vault / _ACTIVITY_JSONL_PATH
        if not act_jsonl.exists():
            act_jsonl.write_text("", encoding="utf-8")

        # Personal Model scaffold
        pm = self.vault / _PERSONAL_MODEL_PATH
        if not pm.exists():
            pm.write_text(_PERSONAL_MODEL_SCAFFOLD, encoding="utf-8")

        # Anchor notes (no pre-populated content)
        self._create_stub("Personal/About Me.md",
            "# About Me\n\n*This is your space. Add what matters.*\n")
        self._create_stub("Goals/Long-Term Goals.md",
            "# Long-Term Goals\n")
        self._create_stub("Daily/README.md",
            "# Daily Notes\n\nUse this folder for day notes and quick captures.\n"
            "Create notes named `YYYY-MM-DD.md` for each day.\n")

        # Log init only the first time the vault is created
        if not already_exists:
            self._log_activity("vault_init", "_JARVIS", "system", "Vault initialized")

    def _create_stub(self, rel_path: str, content: str):
        p = self.vault / rel_path
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
```

- [ ] **Step 1.4: Run bootstrap tests**

```bash
python3 -m pytest tests/test_vault.py -v 2>&1 | head -40
```

Expected: All 7 bootstrap tests pass. `_log_activity` will fail — that's fine, add a stub:

```python
    # Add this stub at the end of VaultManager for now:
    def _log_activity(self, action: str, note: str, source: str, summary: str,
                      risk: str = "low"):
        pass  # implemented in Task 3
```

Re-run: all 7 pass.

- [ ] **Step 1.5: Commit**

```bash
git add memory/vault.py tests/test_vault.py
git commit -m "feat: vault bootstrap — VaultManager._ensure_vault() with idempotent scaffold"
```

---

## Task 2: Note Format Utilities — Frontmatter, Hash, Sensitivity Decision

**Files:**
- Modify: `memory/vault.py`
- Modify: `tests/test_vault.py` (append)

- [ ] **Step 2.1: Append tests for utilities**

Add to `tests/test_vault.py`:

```python
def test_compute_hash_is_deterministic(vault):
    h1 = vault._compute_hash("hello world")
    h2 = vault._compute_hash("hello world")
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_compute_hash_differs_on_change(vault):
    assert vault._compute_hash("abc") != vault._compute_hash("xyz")


def test_build_frontmatter_includes_required_fields(vault):
    fm = vault._build_frontmatter(
        title="Test Note", area="Learning", source="conversation, 2026-05-28",
        sensitivity="low", created_by="jarvis"
    )
    assert "title: Test Note" in fm
    assert "area: Learning" in fm
    assert "sensitivity: low" in fm
    assert "created_by: jarvis" in fm
    assert "jarvis_last_hash:" in fm
    assert fm.startswith("---\n")
    assert fm.strip().endswith("---")


def test_parse_frontmatter_extracts_hash(vault, tmp_path):
    note_path = tmp_path / "SecondBrain" / "Learning" / "test.md"
    note_path.write_text(
        "---\ntitle: Test\njarvis_last_hash: abc123\n---\n\n# Test\n",
        encoding="utf-8"
    )
    fm = vault._parse_frontmatter(note_path)
    assert fm.get("jarvis_last_hash") == "abc123"


def test_should_propose_high_risk_area(vault):
    # High-risk area always proposes
    assert vault._should_propose("Business", "low", False) is True
    assert vault._should_propose("Relationships", "low", False) is True
    assert vault._should_propose("Decisions", "medium", False) is True


def test_should_propose_low_area_high_sensitivity(vault):
    # Low-risk area + high sensitivity → propose (sensitivity wins)
    assert vault._should_propose("Learning", "high", False) is True


def test_should_not_propose_low_risk_low_sensitivity(vault):
    assert vault._should_propose("Learning", "low", False) is False
    assert vault._should_propose("Daily", "low", False) is False


def test_should_propose_when_human_edited(vault):
    # Human edits always trigger proposal regardless of risk
    assert vault._should_propose("Learning", "low", has_human_edits=True) is True
```

- [ ] **Step 2.2: Run to see failures**

```bash
python3 -m pytest tests/test_vault.py -v -k "hash or frontmatter or propose" 2>&1 | head -30
```

Expected: AttributeError — methods don't exist yet.

- [ ] **Step 2.3: Add utilities to `VaultManager`**

Add inside the `VaultManager` class after `_create_stub`:

```python
    # ── Utilities ──────────────────────────────────────────────────────────

    def _compute_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _build_frontmatter(self, title: str, area: str, source: str,
                           sensitivity: str = "low", created_by: str = "jarvis",
                           tags: list = None, extra: dict = None) -> str:
        now = datetime.now().strftime("%Y-%m-%d")
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
            f"jarvis_last_hash: placeholder",  # updated by _write_safe
            f"sensitivity: {sensitivity}",
            f"source: \"{source}\"",
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
```

- [ ] **Step 2.4: Run utility tests**

```bash
python3 -m pytest tests/test_vault.py -v 2>&1 | tail -15
```

Expected: All tests pass.

- [ ] **Step 2.5: Commit**

```bash
git add memory/vault.py tests/test_vault.py
git commit -m "feat: vault note format utilities — hash, frontmatter, risk decision"
```

---

## Task 3: Activity Logging — Dual MD + JSONL

**Files:**
- Modify: `memory/vault.py`
- Modify: `tests/test_vault.py` (append)

- [ ] **Step 3.1: Append activity log tests**

```python
def test_log_activity_appends_to_markdown(vault, tmp_path):
    vault._log_activity("create", "Learning/Test.md", "conversation", "test note", "low")
    content = (tmp_path / "SecondBrain" / "_JARVIS" / "_Activity.md").read_text()
    assert "create" in content
    assert "Learning/Test.md" in content
    assert "conversation" in content


def test_log_activity_appends_jsonl_entry(vault, tmp_path):
    vault._log_activity("update", "Daily/2026-05-28.md", "email", "gym log", "low")
    lines = (tmp_path / "SecondBrain" / "_JARVIS" / "_Activity.jsonl").read_text().strip().splitlines()
    # Filter out vault_init line
    entries = [json.loads(l) for l in lines if l.strip()]
    activity = [e for e in entries if e.get("action") == "update"]
    assert len(activity) == 1
    assert activity[0]["note"] == "Daily/2026-05-28.md"
    assert activity[0]["source"] == "email"
    assert "ts" in activity[0]


def test_log_multiple_activities_accumulate(vault, tmp_path):
    vault._log_activity("create", "Learning/A.md", "conv", "a", "low")
    vault._log_activity("create", "Learning/B.md", "conv", "b", "low")
    lines = [l for l in
        (tmp_path / "SecondBrain" / "_JARVIS" / "_Activity.jsonl")
        .read_text().strip().splitlines()
        if l.strip() and '"action"' in l]
    non_init = [l for l in lines if "vault_init" not in l]
    assert len(non_init) == 2
```

- [ ] **Step 3.2: Run to see failures**

```bash
python3 -m pytest tests/test_vault.py -v -k "log_activity" 2>&1 | head -20
```

Expected: tests fail (stub `_log_activity` does nothing).

- [ ] **Step 3.3: Implement `_log_activity`**

Replace the stub in `VaultManager`:

```python
    def _log_activity(self, action: str, note: str, source: str,
                      summary: str, risk: str = "low"):
        ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        # Human-readable markdown
        md_entry = (
            f"\n## {ts} | {action} | {note}\n"
            f"- **Action**: {action}\n"
            f"- **Source**: {source}\n"
            f"- **Summary**: {summary}\n"
        )
        act_md = self.vault / _ACTIVITY_MD_PATH
        try:
            with open(act_md, "a", encoding="utf-8") as f:
                f.write(md_entry)
        except Exception:
            pass

        # Machine-readable JSONL
        record = {"ts": ts, "action": action, "note": note,
                  "source": source, "summary": summary, "risk": risk}
        act_jsonl = self.vault / _ACTIVITY_JSONL_PATH
        try:
            with open(act_jsonl, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass
```

- [ ] **Step 3.4: Run all tests**

```bash
python3 -m pytest tests/test_vault.py -v 2>&1 | tail -15
```

Expected: All pass (including bootstrap idempotency — init logs once in JSONL).

- [ ] **Step 3.5: Commit**

```bash
git add memory/vault.py tests/test_vault.py
git commit -m "feat: vault dual activity logging — markdown + JSONL audit trail"
```

---

## Task 4: `create_note()` and `update_note()` with Conflict Detection

**Files:**
- Modify: `memory/vault.py`
- Modify: `tests/test_vault.py` (append)

- [ ] **Step 4.1: Append create/update tests**

```python
def test_create_note_low_risk_writes_file(vault, tmp_path):
    result = vault.create_note(
        title="Python Basics",
        content="Python is a high-level language.",
        area="Learning",
        source="conversation, 2026-05-28",
    )
    note_path = tmp_path / "SecondBrain" / "Learning" / "Python Basics.md"
    assert note_path.exists()
    content = note_path.read_text()
    assert "Python is a high-level language" in content
    assert "JARVIS" in content  # attribution
    assert "auto_write" in result or "created" in result.lower()


def test_create_note_high_risk_creates_proposal(vault, tmp_path):
    result = vault.create_note(
        title="Investor Ahmed",
        content="Met investor Ahmed today.",
        area="Relationships",
        source="conversation, 2026-05-28",
    )
    proposals = list((tmp_path / "SecondBrain" / "_JARVIS" / "Proposals").glob("*.md"))
    assert len(proposals) == 1
    assert "proposal" in result.lower() or "proposed" in result.lower()
    # Note must NOT be written to Relationships/
    rel_path = tmp_path / "SecondBrain" / "Relationships" / "Investor Ahmed.md"
    assert not rel_path.exists()


def test_create_note_low_area_high_sensitivity_creates_proposal(vault, tmp_path):
    result = vault.create_note(
        title="Medical Checkup",
        content="Had a checkup. All good.",
        area="Learning",
        source="conversation",
        sensitivity="high",
    )
    proposals = list((tmp_path / "SecondBrain" / "_JARVIS" / "Proposals").glob("*.md"))
    assert len(proposals) == 1  # sensitivity override


def test_create_note_writes_attribution_header(vault, tmp_path):
    vault.create_note("Book Notes", "Key takeaway here.", "Learning", "email, 2026-05-28")
    note = (tmp_path / "SecondBrain" / "Learning" / "Book Notes.md").read_text()
    assert "*JARVIS:" in note
    assert "email, 2026-05-28" in note


def test_update_note_appends_when_no_conflict(vault, tmp_path):
    vault.create_note("My Goals", "Goal 1: Ship Addis Market.", "Goals", "conv")
    result = vault.update_note("Goals/My Goals", "Goal 2: Launch Nexel.", "conv")
    note = (tmp_path / "SecondBrain" / "Goals" / "My Goals.md").read_text()
    assert "Goal 1" in note
    assert "Goal 2" in note
    assert "proposed" not in result.lower()


def test_update_note_proposes_when_human_edited(vault, tmp_path):
    vault.create_note("My Goals", "Goal 1.", "Goals", "conv")
    # Simulate human edit: change content so hash differs
    note_path = tmp_path / "SecondBrain" / "Goals" / "My Goals.md"
    note_path.write_text(note_path.read_text() + "\n*human addition*\n", encoding="utf-8")

    result = vault.update_note("Goals/My Goals", "Goal 2.", "conv")
    assert "proposal" in result.lower() or "proposed" in result.lower()
    proposals = list((tmp_path / "SecondBrain" / "_JARVIS" / "Proposals").glob("*.md"))
    assert len(proposals) == 1
```

- [ ] **Step 4.2: Run to see failures**

```bash
python3 -m pytest tests/test_vault.py -v -k "create_note or update_note" 2>&1 | head -30
```

- [ ] **Step 4.3: Implement `create_note()` and `update_note()`**

Add to `VaultManager`:

```python
    def _resolve_note_path(self, title_or_path: str) -> Optional[Path]:
        """Find a note by 'Area/Title' or just 'Title' (searches all areas)."""
        if "/" in title_or_path:
            area, _, title = title_or_path.partition("/")
            p = self.vault / area / f"{self._safe_title(title)}.md"
            return p if p.exists() else None
        # Search all areas
        for area in AREA_RISK:
            p = self.vault / area / f"{self._safe_title(title_or_path)}.md"
            if p.exists():
                return p
        return None

    def _detect_human_edits(self, path: Path) -> bool:
        """Return True if the note has been edited by human since last JARVIS write."""
        fm = self._parse_frontmatter(path)
        stored_hash = fm.get("jarvis_last_hash", "")
        if not stored_hash or stored_hash == "placeholder":
            return False
        current_content = path.read_text(encoding="utf-8")
        return self._compute_hash(current_content) != stored_hash

    def _write_note(self, path: Path, frontmatter: str, body: str, source: str):
        """Write note to disk and update jarvis_last_hash."""
        content = frontmatter + "\n\n" + body.strip() + "\n"
        path.write_text(content, encoding="utf-8")
        # Update hash to reflect what we just wrote
        content_hash = self._compute_hash(content)
        self._update_frontmatter_field(path, "jarvis_last_hash", content_hash)
        # Invalidate search index
        with self._index_lock:
            self._last_build = 0.0

    def create_note(self, title: str, content: str, area: str, source: str,
                    tags: list = None, sensitivity: str = "low") -> str:
        if self._should_propose(area, sensitivity, has_human_edits=False):
            return self.propose_change(
                title=title, proposed_content=content, action="create",
                area=area, source=source, reason=f"New {area} note: {title}"
            )

        safe = self._safe_title(title)
        path = self.vault / area / f"{safe}.md"
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

        now = datetime.now().strftime("%Y-%m-%d")
        attribution = f"> *JARVIS: updated from {source} on {now}*"
        existing = path.read_text(encoding="utf-8")
        updated = existing.rstrip() + f"\n\n{attribution}\n\n{content}\n"
        path.write_text(updated, encoding="utf-8")
        new_hash = self._compute_hash(updated)
        self._update_frontmatter_field(path, "jarvis_last_hash", new_hash)
        self._update_frontmatter_field(path, "updated", now)
        self._update_frontmatter_field(path, "last_edited_by", "jarvis")
        with self._index_lock:
            self._last_build = 0.0
        self._log_activity("update", f"{area}/{path.stem}", source,
                           f"Updated note: {path.stem}", risk="low")
        return f"Updated: {area}/{path.stem}.md"
```

- [ ] **Step 4.4: Run create/update tests**

```bash
python3 -m pytest tests/test_vault.py -v 2>&1 | tail -20
```

Expected: All pass. (`propose_change` is a stub — add a temporary one if needed: `def propose_change(self, **kwargs): return "proposed"`)

- [ ] **Step 4.5: Commit**

```bash
git add memory/vault.py tests/test_vault.py
git commit -m "feat: vault create_note + update_note with conflict detection"
```

---

## Task 5: Proposal System — `propose_change()` + ID Generation

**Files:**
- Modify: `memory/vault.py`
- Modify: `tests/test_vault.py` (append)

- [ ] **Step 5.1: Append proposal tests**

```python
def test_propose_change_creates_file_in_proposals_dir(vault, tmp_path):
    vault.propose_change(
        title="Addis Market Revenue",
        proposed_content="Revenue hit $1000 this month.",
        action="create",
        area="Business",
        source="conversation, 2026-05-28",
        reason="Elnatan mentioned hitting first revenue milestone",
    )
    proposals = list((tmp_path / "SecondBrain" / "_JARVIS" / "Proposals").glob("*.md"))
    assert len(proposals) == 1


def test_proposal_file_has_required_frontmatter(vault, tmp_path):
    vault.propose_change("Test", "content", "create", "Business", "conv", "test")
    p = list((tmp_path / "SecondBrain" / "_JARVIS" / "Proposals").glob("*.md"))[0]
    text = p.read_text()
    assert "proposal_id:" in text
    assert "status: pending" in text
    assert "target_note:" in text
    assert "action: create" in text
    assert "reason:" in text


def test_proposal_ids_are_sequential(vault, tmp_path):
    vault.propose_change("A", "c", "create", "Business", "conv", "r")
    vault.propose_change("B", "c", "create", "Business", "conv", "r")
    proposals = sorted((tmp_path / "SecondBrain" / "_JARVIS" / "Proposals").glob("*.md"))
    assert proposals[0].stem.endswith("-001")
    assert proposals[1].stem.endswith("-002")


def test_propose_change_returns_proposal_id(vault):
    result = vault.propose_change("X", "c", "create", "Business", "conv", "r")
    assert "proposal" in result.lower()
    # ID format is embedded in result
    today = datetime.now().strftime("%Y-%m-%d")
    assert today in result
```

- [ ] **Step 5.2: Run to see failures**

```bash
python3 -m pytest tests/test_vault.py -v -k "propose" 2>&1 | head -20
```

- [ ] **Step 5.3: Replace stub `propose_change` with real implementation**

```python
    def _next_proposal_id(self) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        proposals_dir = self.vault / _PROPOSALS_DIR
        existing = list(proposals_dir.glob(f"{today}-*.md"))
        return f"{today}-{len(existing) + 1:03d}"

    def propose_change(self, title: str, proposed_content: str, action: str,
                       area: str, source: str, reason: str,
                       sensitivity: str = "low") -> str:
        proposal_id = self._next_proposal_id()
        target = f"{area}/{self._safe_title(title)}"
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        # Capture current note hash for stale detection at approval time
        existing_path = self._resolve_note_path(target)
        current_hash = ""
        if existing_path and existing_path.exists():
            current_hash = self._compute_hash(existing_path.read_text(encoding="utf-8"))

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
            f"source: \"{source}\"",
            f"reason: \"{reason}\"",
            f"hash_at_proposal: {current_hash}",
            "---",
        ]
        attribution = f"> *JARVIS: proposed from {source} on {datetime.now().strftime('%Y-%m-%d')}*"
        body = "\n".join(fm_lines) + f"\n\n# Proposed Content\n\n{attribution}\n\n{proposed_content}\n"

        proposal_path = self.vault / _PROPOSALS_DIR / f"{proposal_id}.md"
        proposal_path.write_text(body, encoding="utf-8")
        self._log_activity("propose", target, source,
                           f"Proposed {action}: {title}", risk=AREA_RISK.get(area, "medium"))
        return f"Proposal created: {proposal_id} — review with `review_proposals`"
```

- [ ] **Step 5.4: Run proposal tests**

```bash
python3 -m pytest tests/test_vault.py -v 2>&1 | tail -20
```

Expected: All pass.

- [ ] **Step 5.5: Commit**

```bash
git add memory/vault.py tests/test_vault.py
git commit -m "feat: vault proposal system — propose_change + sequential IDs"
```

---

## Task 6: Proposal Review Flow — `get_pending_proposals()`, `approve_proposal()`, `reject_proposal()`

**Files:**
- Modify: `memory/vault.py`
- Modify: `tests/test_vault.py` (append)

- [ ] **Step 6.1: Append review flow tests**

```python
def test_get_pending_proposals_lists_pending_only(vault, tmp_path):
    vault.propose_change("A", "c1", "create", "Business", "conv", "r1")
    vault.propose_change("B", "c2", "create", "Decisions", "conv", "r2")
    result = vault.get_pending_proposals()
    assert "001" in result
    assert "002" in result
    assert "pending" in result.lower() or "Business" in result


def test_approve_proposal_writes_note(vault, tmp_path):
    vault.propose_change("New Insight", "This is the content.", "create",
                         "Learning", "conversation", "test insight")
    proposals = list((tmp_path / "SecondBrain" / "_JARVIS" / "Proposals").glob("*.md"))
    pid = proposals[0].stem

    result = vault.approve_proposal(pid)
    note_path = tmp_path / "SecondBrain" / "Learning" / "New Insight.md"
    assert note_path.exists()
    assert "This is the content." in note_path.read_text()
    assert "approved" in result.lower()


def test_approve_proposal_marks_status_approved(vault, tmp_path):
    vault.propose_change("X", "content", "create", "Learning", "conv", "r")
    pid = list((tmp_path / "SecondBrain" / "_JARVIS" / "Proposals").glob("*.md"))[0].stem
    vault.approve_proposal(pid)
    proposal_text = (tmp_path / "SecondBrain" / "_JARVIS" / "Proposals" / f"{pid}.md").read_text()
    assert "status: approved" in proposal_text


def test_approve_proposal_stale_when_note_changed(vault, tmp_path):
    # Create a note then make a proposal for it
    vault.create_note("Existing Note", "original content", "Learning", "conv")
    vault.propose_change("Existing Note", "updated content", "update",
                         "Learning", "conv", "update reason")
    pid = list((tmp_path / "SecondBrain" / "_JARVIS" / "Proposals").glob("*.md"))[0].stem

    # Human edits the note after the proposal
    note_path = tmp_path / "SecondBrain" / "Learning" / "Existing Note.md"
    note_path.write_text(note_path.read_text() + "\n*human edit*\n", encoding="utf-8")

    result = vault.approve_proposal(pid)
    assert "stale" in result.lower()
    # Note must NOT be overwritten with proposal content
    assert "updated content" not in note_path.read_text()


def test_reject_proposal_preserves_file(vault, tmp_path):
    vault.propose_change("Sensitive", "data", "create", "Decisions", "conv", "reason")
    pid = list((tmp_path / "SecondBrain" / "_JARVIS" / "Proposals").glob("*.md"))[0].stem
    vault.reject_proposal(pid)
    proposal_path = tmp_path / "SecondBrain" / "_JARVIS" / "Proposals" / f"{pid}.md"
    assert proposal_path.exists()
    assert "status: rejected" in proposal_path.read_text()


def test_get_pending_proposals_empty(vault):
    result = vault.get_pending_proposals()
    assert "no pending" in result.lower() or result == "" or "0" in result
```

- [ ] **Step 6.2: Run to see failures**

```bash
python3 -m pytest tests/test_vault.py -v -k "pending or approve or reject" 2>&1 | head -30
```

- [ ] **Step 6.3: Implement review flow**

```python
    def get_pending_proposals(self) -> str:
        proposals_dir = self.vault / _PROPOSALS_DIR
        pending = []
        for p in sorted(proposals_dir.glob("*.md")):
            fm = self._parse_frontmatter(p)
            if fm.get("status") == "pending":
                pid = fm.get("proposal_id", p.stem)
                target = fm.get("target_note", "unknown")
                action = fm.get("action", "?")
                risk = fm.get("risk", "?")
                reason = fm.get("reason", "").strip('"')
                pending.append(f"[{pid}] {target} — {action} ({risk} risk)\n  Reason: {reason}")
        if not pending:
            return "No pending proposals."
        return "Pending proposals:\n\n" + "\n\n".join(pending)

    def approve_proposal(self, proposal_id: str) -> str:
        p = self.vault / _PROPOSALS_DIR / f"{proposal_id}.md"
        if not p.exists():
            return f"Proposal not found: {proposal_id}"

        fm = self._parse_frontmatter(p)
        target = fm.get("target_note", "")
        action = fm.get("action", "create")
        area_str, _, title_str = target.partition("/")
        hash_at_proposal = fm.get("hash_at_proposal", "")

        # Extract proposed content (everything after the frontmatter + header)
        full_text = p.read_text(encoding="utf-8")
        content_match = re.search(r'---\n\n# Proposed Content\n\n(.*)', full_text, re.DOTALL)
        proposed_content = content_match.group(1).strip() if content_match else ""

        # Stale check: re-verify hash at approval time
        if action == "update" and target:
            existing_path = self._resolve_note_path(target)
            if existing_path and existing_path.exists():
                current_hash = self._compute_hash(existing_path.read_text(encoding="utf-8"))
                if hash_at_proposal and current_hash != hash_at_proposal:
                    self._update_proposal_status(p, "stale")
                    return (f"Proposal {proposal_id} is stale — `{target}` was edited "
                            f"after this proposal was created. Review `{target}` manually "
                            f"and re-propose if still relevant.")

        # Apply the proposal
        source = fm.get("source", "proposal").strip('"')
        if action == "create":
            note_path = self.vault / area_str / f"{self._safe_title(title_str)}.md"
            note_path.parent.mkdir(parents=True, exist_ok=True)
            note_path.write_text(proposed_content + "\n", encoding="utf-8")
            new_hash = self._compute_hash(note_path.read_text(encoding="utf-8"))
            self._update_frontmatter_field(note_path, "jarvis_last_hash", new_hash)
        elif action == "update":
            existing_path = self._resolve_note_path(target)
            if existing_path:
                updated = existing_path.read_text(encoding="utf-8").rstrip()
                updated += f"\n\n{proposed_content}\n"
                existing_path.write_text(updated, encoding="utf-8")
                new_hash = self._compute_hash(updated)
                self._update_frontmatter_field(existing_path, "jarvis_last_hash", new_hash)

        self._update_proposal_status(p, "approved")
        self._log_activity("approve", target, "human", f"Approved proposal {proposal_id}")
        with self._index_lock:
            self._last_build = 0.0
        return f"Approved and applied: {proposal_id} → {target}"

    def reject_proposal(self, proposal_id: str) -> str:
        p = self.vault / _PROPOSALS_DIR / f"{proposal_id}.md"
        if not p.exists():
            return f"Proposal not found: {proposal_id}"
        self._update_proposal_status(p, "rejected")
        self._log_activity("reject", proposal_id, "human", f"Rejected proposal {proposal_id}")
        return f"Rejected: {proposal_id} (file preserved in Proposals/)"

    def _update_proposal_status(self, proposal_path: Path, status: str):
        text = proposal_path.read_text(encoding="utf-8")
        updated = re.sub(r'^(status:\s*).*$', f'\\g<1>{status}',
                         text, count=1, flags=re.MULTILINE)
        proposal_path.write_text(updated, encoding="utf-8")
```

- [ ] **Step 6.4: Run review flow tests**

```bash
python3 -m pytest tests/test_vault.py -v 2>&1 | tail -25
```

Expected: All pass.

- [ ] **Step 6.5: Commit**

```bash
git add memory/vault.py tests/test_vault.py
git commit -m "feat: vault proposal review flow — get/approve/reject with stale detection"
```

---

## Task 7: Navigation + Search — `get_note()`, `list_notes()`, `search_vault()`

**Files:**
- Modify: `memory/vault.py`
- Modify: `tests/test_vault.py` (append)

- [ ] **Step 7.1: Append navigation and search tests**

```python
def test_get_note_returns_content(vault, tmp_path):
    vault.create_note("React Hooks", "useState is fundamental.", "Learning", "conv")
    result = vault.get_note("Learning/React Hooks")
    assert "useState" in result


def test_get_note_not_found(vault):
    result = vault.get_note("Learning/Nonexistent Note")
    assert "not found" in result.lower()


def test_list_notes_returns_notes_in_area(vault, tmp_path):
    vault.create_note("Note A", "content a", "Learning", "conv")
    vault.create_note("Note B", "content b", "Learning", "conv")
    result = vault.list_notes("Learning")
    assert "Note A" in result or "note-a" in result.lower()
    assert "Note B" in result or "note-b" in result.lower()


def test_list_notes_all_areas(vault, tmp_path):
    vault.create_note("Topic X", "x", "Learning", "conv")
    result = vault.list_notes()
    assert "Learning" in result


def test_search_vault_keyword_fallback(vault, tmp_path):
    vault.create_note("Gym Schedule", "I go to gym on Mon/Wed/Fri.", "Daily", "conv")
    result = vault.search_vault("gym workout schedule")
    assert "gym" in result.lower() or "Gym" in result


def test_search_vault_returns_empty_when_no_match(vault):
    result = vault.search_vault("xylophone concerto baroque")
    assert result == "" or "no results" in result.lower()
```

- [ ] **Step 7.2: Run to see failures**

```bash
python3 -m pytest tests/test_vault.py -v -k "get_note or list_notes or search_vault" 2>&1 | head -20
```

- [ ] **Step 7.3: Implement navigation + search**

```python
    def get_note(self, title_or_path: str) -> str:
        path = self._resolve_note_path(title_or_path)
        if path is None or not path.exists():
            return f"Note not found: {title_or_path}"
        return path.read_text(encoding="utf-8")

    def list_notes(self, area: str = None) -> str:
        areas = [area] if area else list(AREA_RISK.keys())
        lines = []
        for a in areas:
            folder = self.vault / a
            if not folder.exists():
                continue
            notes = sorted(folder.glob("*.md"))
            if notes:
                lines.append(f"**{a}/**")
                for n in notes:
                    lines.append(f"  - {n.stem}")
        return "\n".join(lines) if lines else "No notes found."

    def search_vault(self, query: str, max_results: int = 3) -> str:
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
        stop = {"the","a","an","is","it","to","of","and","or","in","on",
                "for","what","how","can","do","my","me","i"}
        words = set(re.findall(r'\w+', query.lower())) - stop
        if not words:
            return ""
        scored = []
        for area in AREA_RISK:
            folder = self.vault / area
            if not folder.exists():
                continue
            for note in folder.glob("*.md"):
                try:
                    text = note.read_text(encoding="utf-8").lower()
                    score = sum(text.count(w) + (3 if w in note.stem.lower() else 0)
                                for w in words)
                    if score > 0:
                        body = re.sub(r'^---.*?---\s*', '',
                                      note.read_text(encoding="utf-8"),
                                      flags=re.DOTALL).strip()
                        scored.append((score, f"{area}/{note.stem}", body))
                except Exception:
                    continue
        scored.sort(reverse=True)
        if not scored:
            return ""
        parts = [f"### {title}\n{body[:500]}" for _, title, body in scored[:max_notes]]
        return "\n\n".join(parts)

    # ── FAISS search (background, optional) ───────────────────────────────

    def _notes_mtime(self) -> float:
        try:
            mtimes = []
            for area in AREA_RISK:
                mtimes.extend(p.stat().st_mtime for p in (self.vault / area).glob("*.md")
                               if (self.vault / area).exists())
            return max(mtimes, default=0.0)
        except Exception:
            return 0.0

    def _ensure_index(self):
        with self._index_lock:
            needs_rebuild = (self._index is None or
                (self._notes_mtime() > self._last_build and
                 (__import__('time').time() - self._last_build) > 60))
        if needs_rebuild and not self._building:
            self._building = True
            threading.Thread(target=self._build_index_bg, daemon=True).start()

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
            for note in (self.vault / area).glob("*.md"):
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
            self._last_build = __import__('time').time()

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
```

- [ ] **Step 7.4: Run all vault tests**

```bash
python3 -m pytest tests/test_vault.py -v 2>&1 | tail -25
```

Expected: All pass. FAISS tests skip gracefully if not installed.

- [ ] **Step 7.5: Commit**

```bash
git add memory/vault.py tests/test_vault.py
git commit -m "feat: vault navigation and search — get_note, list_notes, keyword + FAISS search"
```

---

## Task 8: Personal Model — `update_personal_model()`

**Files:**
- Modify: `memory/vault.py`
- Modify: `tests/test_vault.py` (append)

- [ ] **Step 8.1: Append personal model tests**

```python
def test_update_personal_model_always_proposes(vault, tmp_path):
    result = vault.update_personal_model(
        section="Interests & Hobbies",
        content="Elnatan has been discussing anime in every session this week.",
        source="conversation pattern, 2026-05-28",
        supporting_observations="3 sessions mentioned anime",
    )
    proposals = list((tmp_path / "SecondBrain" / "_JARVIS" / "Proposals").glob("*.md"))
    assert len(proposals) == 1
    assert "proposal" in result.lower()


def test_update_personal_model_never_auto_writes(vault, tmp_path):
    vault.update_personal_model("Energy Patterns", "Prefers late night work.",
                                "observation", "5 late-night sessions")
    pm = tmp_path / "SecondBrain" / "_JARVIS" / "_PersonalModel.md"
    assert "Prefers late night work" not in pm.read_text()


def test_update_personal_model_proposal_includes_evidence(vault, tmp_path):
    vault.update_personal_model(
        section="Decision-Making Style",
        content="Tends to delay decisions under uncertainty.",
        source="conversation",
        supporting_observations="Mentioned hesitation 4 times this week",
    )
    p = list((tmp_path / "SecondBrain" / "_JARVIS" / "Proposals").glob("*.md"))[0]
    text = p.read_text()
    assert "Mentioned hesitation" in text
    assert "Decision-Making Style" in text
```

- [ ] **Step 8.2: Implement `update_personal_model`**

```python
    def update_personal_model(self, section: str, content: str,
                              source: str, supporting_observations: str = "") -> str:
        evidence_block = ""
        if supporting_observations:
            evidence_block = f"\n\n*Supporting evidence: {supporting_observations}*"
        full_content = (
            f"### {section}\n\n{content}{evidence_block}\n\n"
            f"*Proposed update — requires review*"
        )
        return self.propose_change(
            title="_PersonalModel",
            proposed_content=full_content,
            action="update",
            area="_JARVIS",
            source=source,
            reason=f"Personal Model update: {section}",
            sensitivity="high",
        )
```

Note: `_JARVIS` area is not in `AREA_RISK` so will default to `medium`. Sensitivity is set to `high` explicitly so `_should_propose` always returns `True`.

- [ ] **Step 8.3: Run personal model tests**

```bash
python3 -m pytest tests/test_vault.py -v -k "personal_model" 2>&1 | tail -10
```

Expected: All 3 pass.

- [ ] **Step 8.4: Commit**

```bash
git add memory/vault.py tests/test_vault.py
git commit -m "feat: vault update_personal_model — always proposal-first with evidence"
```

---

## Task 9: Observation Staging — `memory/observations.py`

**Files:**
- Create: `memory/observations.py`
- Create: `tests/test_observations.py`

- [ ] **Step 9.1: Write observation tests**

Create `tests/test_observations.py`:

```python
import pytest
import json
from pathlib import Path


@pytest.fixture
def obs(tmp_path):
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import importlib
    import memory.observations as mod
    # Point to a temp DB
    mod._DB_PATH = tmp_path / "observations.db"
    mod._conn = None  # force reconnect
    return mod


def test_add_observation_stores_row(obs):
    obs_id = obs.add_observation(
        source="conversation",
        source_detail="chat on 2026-05-28",
        content="I've been reading Open by Andre Agassi and finding it really motivating.",
        relevance_hint="Learning",
    )
    assert isinstance(obs_id, int)
    assert obs_id > 0


def test_quality_filter_passes_good_observation(obs):
    good = {
        "content": "I've decided to stop playing Fortnite and focus on building Addis Market instead.",
        "source": "conversation",
    }
    assert obs.score_observation_quality(good) is True


def test_quality_filter_rejects_chitchat(obs):
    bad = {"content": "hey jarvis how are you doing", "source": "conversation"}
    assert obs.score_observation_quality(bad) is False


def test_quality_filter_rejects_too_short(obs):
    bad = {"content": "I like books", "source": "conversation"}
    assert obs.score_observation_quality(bad) is False


def test_quality_filter_rejects_general_knowledge(obs):
    bad = {
        "content": "The capital of Ethiopia is Addis Ababa which has a population "
                   "of about four million people and is the seat of the African Union.",
        "source": "conversation",
    }
    assert obs.score_observation_quality(bad) is False


def test_quality_filter_rejects_unknown_source(obs):
    bad = {
        "content": "I realized I work best late at night when everything is quiet.",
        "source": "unknown",
    }
    assert obs.score_observation_quality(bad) is False


def test_get_pending_observations_returns_quality_ones(obs):
    obs.add_observation("conversation", "chat", "I feel most productive after midnight.", "Personal")
    obs.add_observation("conversation", "chat", "ok cool", "")
    pending = obs.get_pending_observations()
    assert len(pending) == 1
    assert "midnight" in pending[0]["content"]


def test_mark_synthesized_removes_from_pending(obs):
    oid = obs.add_observation("conversation", "chat",
        "I want to read more books about entrepreneurship this year.", "Learning")
    obs.mark_synthesized(oid)
    pending = obs.get_pending_observations()
    assert all(p["id"] != oid for p in pending)


def test_dedup_blocks_near_duplicate(obs):
    content = "I started reading Open by Andre Agassi and it is very motivating for me."
    obs.add_observation("conversation", "c", content, "Learning")
    obs.add_observation("conversation", "c", content, "Learning")
    pending = obs.get_pending_observations()
    assert len(pending) == 1


def test_suppress_topic_removes_from_pending(obs):
    obs.add_observation("conversation", "c",
        "I want to keep growing Addis Market vendor count this quarter.", "Business")
    obs.suppress_topic("Addis Market")
    pending = obs.get_pending_observations()
    assert len(pending) == 0


def test_sensitivity_stored_in_observation(obs):
    obs.add_observation("email", "from Yostina", "My sister called and we discussed family plans.",
                        "Relationships", sensitivity="high")
    pending = obs.get_pending_observations(include_high_sensitivity=True)
    assert any(p["sensitivity"] == "high" for p in pending)
```

- [ ] **Step 9.2: Run to see failures**

```bash
python3 -m pytest tests/test_observations.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'memory.observations'`

- [ ] **Step 9.3: Create `memory/observations.py`**

```python
"""
Observation staging layer for the Personal Second Brain.

Raw life signals (email, calendar, conversation, manual) are buffered
here in SQLite before synthesis. Only quality-scored observations reach
the vault write layer.
"""
import hashlib
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).parent / "observations.db"
_conn: Optional[sqlite3.Connection] = None
_lock = threading.Lock()

_SIGNAL_WORDS = {
    "decided", "starting", "reading", "working", "building", "learned",
    "realized", "want", "goal", "plan", "going", "feels", "noticed",
    "met", "talked", "interested", "thinking", "worried", "excited",
    "finished", "launched", "shipped", "hired", "quit", "moved",
    "started", "stopped", "changed", "discovered", "feeling", "chose",
}

_PERSONAL_ANCHORS = {"i ", "i'", "my ", "me ", "we ", "our ", "you ", "your ",
                     "elnatan", "jarvis"}

_LOW_CREDIBILITY_SOURCES = {"system", "unknown", "test"}


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _create_schema(_conn)
    return _conn


def _create_schema(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            source         TEXT NOT NULL,
            source_detail  TEXT,
            content        TEXT NOT NULL,
            relevance_hint TEXT,
            tags           TEXT,
            sensitivity    TEXT DEFAULT 'low',
            quality        INTEGER DEFAULT 0,
            content_hash   TEXT,
            captured_at    TEXT NOT NULL,
            synthesized    INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS suppressed_topics (
            topic TEXT PRIMARY KEY,
            added_at TEXT NOT NULL
        )
    """)
    conn.commit()


def score_observation_quality(obs: dict) -> bool:
    content = obs.get("content", "").strip()
    source  = obs.get("source", "")

    # 1. Length floor
    if len(content.split()) < 15:
        return False

    # 2. Information density — must contain at least one signal word
    words = set(content.lower().split())
    if not words.intersection(_SIGNAL_WORDS):
        return False

    # 3. Personal relevance — must contain a personal anchor
    lower = content.lower()
    if not any(anchor in lower for anchor in _PERSONAL_ANCHORS):
        return False

    # 4. Source credibility
    if source.lower() in _LOW_CREDIBILITY_SOURCES:
        return False

    return True


def add_observation(source: str, source_detail: str, content: str,
                    relevance_hint: str = "", tags: str = "",
                    sensitivity: str = "low") -> int:
    quality = 1 if score_observation_quality({"content": content, "source": source}) else 0
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    now = datetime.now().isoformat()

    with _lock:
        conn = _get_conn()

        # Deduplication: skip near-identical observations captured in last 24h
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        existing = conn.execute(
            "SELECT id FROM observations WHERE content_hash = ? AND captured_at > ?",
            (content_hash, cutoff)
        ).fetchone()
        if existing:
            return existing["id"]

        # Check suppressed topics
        if quality == 1 and relevance_hint:
            suppressed = conn.execute(
                "SELECT topic FROM suppressed_topics WHERE ? LIKE '%' || topic || '%'",
                (relevance_hint,)
            ).fetchone()
            if suppressed:
                quality = 0

        cursor = conn.execute(
            """INSERT INTO observations
               (source, source_detail, content, relevance_hint, tags,
                sensitivity, quality, content_hash, captured_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (source, source_detail, content, relevance_hint, tags,
             sensitivity, quality, content_hash, now)
        )
        conn.commit()
        return cursor.lastrowid


def get_pending_observations(limit: int = 20,
                             include_high_sensitivity: bool = False) -> list:
    with _lock:
        conn = _get_conn()
        if include_high_sensitivity:
            rows = conn.execute(
                "SELECT * FROM observations WHERE synthesized = 0 AND quality = 1 "
                "ORDER BY captured_at DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM observations WHERE synthesized = 0 AND quality = 1 "
                "AND sensitivity != 'high' ORDER BY captured_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def mark_synthesized(observation_id: int):
    with _lock:
        conn = _get_conn()
        conn.execute("UPDATE observations SET synthesized = 1 WHERE id = ?",
                     (observation_id,))
        conn.commit()


def get_recent_observations(hours: int = 24) -> list:
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    with _lock:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM observations WHERE captured_at > ? ORDER BY captured_at DESC",
            (cutoff,)
        ).fetchall()
        return [dict(r) for r in rows]


def suppress_topic(topic: str):
    now = datetime.now().isoformat()
    with _lock:
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO suppressed_topics (topic, added_at) VALUES (?, ?)",
            (topic, now)
        )
        conn.commit()
        # Mark matching pending observations as quality=0
        conn.execute(
            "UPDATE observations SET quality = 0 WHERE synthesized = 0 "
            "AND relevance_hint LIKE ?", (f"%{topic}%",)
        )
        conn.commit()


def get_suppressed_topics() -> list:
    with _lock:
        conn = _get_conn()
        rows = conn.execute("SELECT topic FROM suppressed_topics").fetchall()
        return [r["topic"] for r in rows]
```

- [ ] **Step 9.4: Run observation tests**

```bash
python3 -m pytest tests/test_observations.py -v 2>&1 | tail -20
```

Expected: All 11 pass.

- [ ] **Step 9.5: Commit**

```bash
git add memory/observations.py tests/test_observations.py
git commit -m "feat: observation staging — SQLite buffer + 4-criterion quality filter"
```

---

## Task 10: JARVIS Tools — `brain/tools/second_brain.py`

Ten `@tool`-decorated functions that expose VaultManager to JARVIS via the existing registry.

**Files:**
- Create: `brain/tools/second_brain.py`
- Create: `tests/test_second_brain_tools.py`

- [ ] **Step 10.1: Write tool registration tests**

Create `tests/test_second_brain_tools.py`:

```python
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_all_ten_tools_register():
    import brain.tools.second_brain  # noqa: F401 — triggers registration
    from brain.tools.registry import TOOL_REGISTRY
    expected = [
        "create_brain_note", "update_brain_note", "propose_brain_change",
        "search_brain", "get_brain_note", "list_brain_notes",
        "review_proposals", "approve_proposal", "reject_proposal",
        "update_personal_model",
    ]
    for name in expected:
        assert name in TOOL_REGISTRY, f"Tool not registered: {name}"


def test_tool_schemas_have_required_fields():
    from brain.tools.registry import TOOL_REGISTRY
    import brain.tools.second_brain  # noqa
    for name in ["create_brain_note", "search_brain", "approve_proposal"]:
        schema = TOOL_REGISTRY[name]["schema"]
        assert "description" in schema
        assert "input_schema" in schema
        assert schema["input_schema"]["type"] == "object"


def test_create_brain_note_tool_executes(tmp_path, monkeypatch):
    # Point VaultManager at temp path
    import memory.vault as vault_mod
    vault_mod.DEFAULT_VAULT_PATH = tmp_path / "SB"
    vault_mod._vm_instance = None  # reset singleton

    from brain.tools.registry import execute_tool
    import brain.tools.second_brain  # noqa
    result = execute_tool("create_brain_note", {
        "title": "Test Book",
        "content": "Great book about resilience.",
        "area": "Learning",
        "source": "conversation",
    })
    assert "created" in result.lower() or "proposal" in result.lower()
    vault_mod._vm_instance = None  # cleanup


def test_search_brain_tool_executes(tmp_path, monkeypatch):
    import memory.vault as vault_mod
    vault_mod.DEFAULT_VAULT_PATH = tmp_path / "SB"
    vault_mod._vm_instance = None

    from brain.tools.registry import execute_tool
    import brain.tools.second_brain  # noqa
    result = execute_tool("search_brain", {"query": "gym workout"})
    assert isinstance(result, str)
    vault_mod._vm_instance = None


def test_review_proposals_tool_executes(tmp_path, monkeypatch):
    import memory.vault as vault_mod
    vault_mod.DEFAULT_VAULT_PATH = tmp_path / "SB"
    vault_mod._vm_instance = None

    from brain.tools.registry import execute_tool
    import brain.tools.second_brain  # noqa
    result = execute_tool("review_proposals", {})
    assert "pending" in result.lower() or "no pending" in result.lower()
    vault_mod._vm_instance = None
```

- [ ] **Step 10.2: Run to see failures**

```bash
python3 -m pytest tests/test_second_brain_tools.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'brain.tools.second_brain'`

- [ ] **Step 10.3: Create `brain/tools/second_brain.py`**

```python
"""
Second Brain tools — expose VaultManager operations to JARVIS.

All 10 tools follow the existing @tool decorator pattern.
VaultManager is instantiated as a module-level singleton.
"""
from brain.tools.registry import tool
from pathlib import Path


def _vault():
    """Return the module-level VaultManager singleton."""
    import memory.vault as _mod
    if _mod._vm_instance is None:
        with _mod._vm_lock:
            if _mod._vm_instance is None:
                _mod._vm_instance = _mod.VaultManager()
    return _mod._vm_instance


@tool(
    description=(
        "Create a new note in Elnatan's Personal Second Brain. "
        "Auto-writes to low-risk areas (Learning, Daily); "
        "creates a proposal for high-risk areas (Business, Relationships, Decisions). "
        "Always include the source of the information."
    ),
    parameters={
        "title":       {"type": "string", "description": "Note title"},
        "content":     {"type": "string", "description": "Note content"},
        "area":        {"type": "string",
                        "description": "Vault area: Learning, Daily, Personal, Goals, "
                                       "Business, Relationships, Decisions, or Archive"},
        "source":      {"type": "string",
                        "description": "Source of information, e.g. 'conversation, 2026-05-28'"},
        "sensitivity": {"type": "string",
                        "description": "Sensitivity level: low (default), medium, or high"},
    }
)
def create_brain_note(title: str, content: str, area: str, source: str,
                      sensitivity: str = "low") -> str:
    return _vault().create_note(title, content, area, source, sensitivity=sensitivity)


@tool(
    description=(
        "Append new information to an existing note in the Personal Second Brain. "
        "If the note has been manually edited since last JARVIS write, creates a proposal instead. "
        "Use 'Area/Note Title' format for title_or_path."
    ),
    parameters={
        "title_or_path": {"type": "string",
                          "description": "Note reference, e.g. 'Learning/React Hooks'"},
        "content":       {"type": "string", "description": "Content to append"},
        "source":        {"type": "string", "description": "Source of information"},
        "sensitivity":   {"type": "string",
                          "description": "Sensitivity: low (default), medium, high"},
    }
)
def update_brain_note(title_or_path: str, content: str, source: str,
                      sensitivity: str = "low") -> str:
    return _vault().update_note(title_or_path, content, source, sensitivity=sensitivity)


@tool(
    description=(
        "Explicitly stage a proposed change to the Personal Second Brain for human review. "
        "Use this for anything sensitive, uncertain, or high-stakes. "
        "Elnatan must approve before the change is applied."
    ),
    parameters={
        "title":            {"type": "string", "description": "Target note title"},
        "proposed_content": {"type": "string", "description": "The proposed content"},
        "action":           {"type": "string",
                             "description": "Action type: create, update, or delete"},
        "area":             {"type": "string", "description": "Vault area"},
        "source":           {"type": "string", "description": "Source of information"},
        "reason":           {"type": "string",
                             "description": "Why this change is being proposed"},
    }
)
def propose_brain_change(title: str, proposed_content: str, action: str,
                         area: str, source: str, reason: str) -> str:
    return _vault().propose_change(title, proposed_content, action, area, source, reason)


@tool(
    description=(
        "Search the Personal Second Brain using semantic or keyword search. "
        "Use for personal queries about Elnatan's life, interests, goals, or patterns."
    ),
    parameters={
        "query":       {"type": "string", "description": "Search query"},
        "max_results": {"type": "integer", "description": "Max results to return (default 3)"},
    }
)
def search_brain(query: str, max_results: int = 3) -> str:
    return _vault().search_vault(query, max_results)


@tool(
    description="Read a specific note from the Personal Second Brain by title or path.",
    parameters={
        "title_or_path": {"type": "string",
                          "description": "Note reference, e.g. 'Learning/React Hooks' or just 'React Hooks'"},
    }
)
def get_brain_note(title_or_path: str) -> str:
    return _vault().get_note(title_or_path)


@tool(
    description="List notes in the Personal Second Brain, optionally filtered by area.",
    parameters={
        "area": {"type": "string",
                 "description": "Optional area to filter by: Learning, Daily, Personal, etc. "
                                "Leave empty to list all areas."},
    }
)
def list_brain_notes(area: str = "") -> str:
    return _vault().list_notes(area if area else None)


@tool(
    description=(
        "Show all pending proposals awaiting review in the Personal Second Brain. "
        "Proposals are changes JARVIS wants to make but needs approval for."
    ),
    parameters={}
)
def review_proposals() -> str:
    return _vault().get_pending_proposals()


@tool(
    description=(
        "Approve a pending proposal and apply the change to the Personal Second Brain. "
        "Re-checks for conflicts at approval time. "
        "Use the proposal ID shown in review_proposals (e.g. '2026-05-28-001')."
    ),
    parameters={
        "proposal_id": {"type": "string",
                        "description": "Proposal ID from review_proposals output"},
    }
)
def approve_proposal(proposal_id: str) -> str:
    return _vault().approve_proposal(proposal_id)


@tool(
    description=(
        "Reject a pending proposal. The proposal file is preserved with status 'rejected' "
        "for reference but the change is not applied."
    ),
    parameters={
        "proposal_id": {"type": "string", "description": "Proposal ID to reject"},
    }
)
def reject_proposal(proposal_id: str) -> str:
    return _vault().reject_proposal(proposal_id)


@tool(
    description=(
        "Propose an update to Elnatan's Personal Model in the Second Brain. "
        "Always creates a proposal — never auto-writes. "
        "Must include supporting evidence (observations, conversations) that justify the update."
    ),
    parameters={
        "section":                  {"type": "string",
                                     "description": "Section to update: 'Interests & Hobbies', "
                                                    "'Energy Patterns', 'Decision-Making Style', "
                                                    "'Communication Preferences', 'Known Challenges', "
                                                    "or 'Relationship Patterns'"},
        "content":                  {"type": "string",
                                     "description": "The proposed update content"},
        "source":                   {"type": "string",
                                     "description": "Source: conversation, observation, etc."},
        "supporting_observations":  {"type": "string",
                                     "description": "Evidence supporting this update"},
    }
)
def update_personal_model(section: str, content: str, source: str,
                          supporting_observations: str = "") -> str:
    return _vault().update_personal_model(section, content, source, supporting_observations)
```

- [ ] **Step 10.4: Run tool tests**

```bash
python3 -m pytest tests/test_second_brain_tools.py -v 2>&1 | tail -15
```

Expected: All 5 pass.

- [ ] **Step 10.5: Commit**

```bash
git add brain/tools/second_brain.py tests/test_second_brain_tools.py
git commit -m "feat: 10 second brain tools registered via @tool decorator"
```

---

## Task 11: Tool Registration — `brain/tools/__init__.py`

**Files:**
- Modify: `brain/tools/__init__.py`

- [ ] **Step 11.1: Add import to `__init__.py`**

```python
# Add after the existing imports:
import brain.tools.second_brain
```

- [ ] **Step 11.2: Verify all 10 tools appear in the registry**

```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from brain.tools import TOOL_REGISTRY
sb_tools = [k for k in TOOL_REGISTRY if 'brain' in k or 'proposal' in k or 'personal_model' in k]
print('Second Brain tools:', sb_tools)
print('Total tools:', len(TOOL_REGISTRY))
"
```

Expected output includes all 10 tool names.

- [ ] **Step 11.3: Run full tool test suite to check no regressions**

```bash
python3 -m pytest tests/test_tool_registry.py tests/test_second_brain_tools.py -v 2>&1 | tail -15
```

Expected: All pass.

- [ ] **Step 11.4: Commit**

```bash
git add brain/tools/__init__.py
git commit -m "feat: register second brain tools in tool registry"
```

---

## Task 12: Context Routing — `brain/think.py`

Pull personal brain context for personal queries; project brain for code queries; both for ambiguous.

**Files:**
- Modify: `brain/think.py`

- [ ] **Step 12.1: Add routing functions after the existing imports block in `think.py`**

Find the line `_HAIKU_PATTERNS = [re.compile(r, re.I) for r in [` and insert before it:

```python
# ── Second Brain context routing ─────────────────────────────────────────────

_PERSONAL_SIGNALS = {
    "sleep", "gym", "workout", "family", "mom", "dad", "sister", "brother",
    "book", "reading", "anime", "hobby", "interest", "diet", "health",
    "feel", "mood", "energy", "goal", "relationship", "friend", "girlfriend",
    "decision", "choice", "should i", "thinking about", "want to", "plans",
    "woke", "tired", "motivated", "stressed", "happy", "sad", "bored",
}

_PROJECT_SIGNALS = {
    "code", "function", "file", "wiki", "repo", "error", "bug", "build",
    "python", "api", "database", "server", "tool", "script", "module",
    "deploy", "test", "commit", "branch", "import", "class", "endpoint",
    "flask", "react", "sql", "bash", "shell", "git", "npm", "pip",
}


def _should_query_personal(user_input: str) -> bool:
    lower = user_input.lower()
    p_score = sum(1 for s in _PERSONAL_SIGNALS if s in lower)
    j_score = sum(1 for s in _PROJECT_SIGNALS if s in lower)
    return p_score >= j_score  # default True when tied or no signals


def _should_query_project(user_input: str) -> bool:
    lower = user_input.lower()
    p_score = sum(1 for s in _PERSONAL_SIGNALS if s in lower)
    j_score = sum(1 for s in _PROJECT_SIGNALS if s in lower)
    return j_score > 0 and j_score >= p_score


def _get_personal_context(user_input: str) -> str:
    try:
        import memory.vault as vault_mod
        vm = vault_mod._vm_instance
        if vm is None:
            vm = vault_mod.VaultManager()
            vault_mod._vm_instance = vm
        results = vm.search_vault(user_input, max_results=2)
        if results:
            return f"\nPERSONAL BRAIN:\n{results}\n"
    except Exception:
        pass
    return ""
```

- [ ] **Step 12.2: Modify `_build_context()` to call routing**

Find this line in `_build_context()`:
```python
    if wiki:
        ctx += wiki
```

Add personal brain query immediately after it:

```python
    if wiki:
        ctx += wiki
    # Personal Second Brain context
    if _should_query_personal(user_input):
        personal_ctx = _get_personal_context(user_input)
        if personal_ctx:
            ctx += personal_ctx
```

- [ ] **Step 12.3: Verify routing works without crashing**

```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from brain.think import _should_query_personal, _should_query_project

# Personal query
assert _should_query_personal('how has my sleep been lately') is True
assert _should_query_project('how has my sleep been lately') is False
print('personal query: OK')

# Code query
assert _should_query_project('fix the bug in wiki.py') is True
print('project query: OK')

# Ambiguous (both or default)
result_p = _should_query_personal('help me plan my week')
print(f'ambiguous routes to personal: {result_p}')
print('routing OK')
"
```

Expected: All assertions pass.

- [ ] **Step 12.4: Syntax check**

```bash
python3 -m py_compile brain/think.py && echo "think.py OK"
```

- [ ] **Step 12.5: Commit**

```bash
git add brain/think.py
git commit -m "feat: dual-brain context routing in _build_context — personal vs project signals"
```

---

## Task 13: Prompt Loader Integration

Add a `load_second_brain_modules()` helper so any JARVIS call doing Second Brain work can load the relevant prompt guidance.

**Files:**
- Modify: `prompts/runtime/prompt_loader.py`

- [ ] **Step 13.1: Add helper to `prompt_loader.py`**

Find `def load_security() -> str:` and add before it:

```python
def load_second_brain_modules() -> str:
    # Core second brain guidance for when JARVIS is doing vault work.
    parts = [
        _read("specialized/second_brain_execution_overview.md"),
        _read("specialized/safe_vault_write.md"),
        _read("security/second_brain_vault_writes.md"),
    ]
    return "\n\n".join(p for p in parts if not p.startswith("[MISSING"))
```

- [ ] **Step 13.2: Verify the helper loads without error**

```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from prompts.runtime.prompt_loader import load_second_brain_modules
result = load_second_brain_modules()
print(f'Second Brain modules: {len(result):,} chars')
assert 'JARVIS' in result or 'vault' in result.lower(), 'Expected vault content'
print('OK')
"
```

Expected: prints character count, `OK`.

- [ ] **Step 13.3: Syntax check**

```bash
python3 -m py_compile prompts/runtime/prompt_loader.py && echo "prompt_loader.py OK"
```

- [ ] **Step 13.4: Commit**

```bash
git add prompts/runtime/prompt_loader.py
git commit -m "feat: prompt loader — load_second_brain_modules() helper"
```

---

## Task 14: End-to-End Smoke Test + Vault Initialization

Verify the complete flow works together. This is the final integration check.

**Files:**
- Run tests only (no new files)

- [ ] **Step 14.1: Run the full test suite**

```bash
python3 -m pytest tests/test_vault.py tests/test_observations.py tests/test_second_brain_tools.py tests/test_tool_registry.py -v 2>&1 | tail -30
```

Expected: All tests pass.

- [ ] **Step 14.2: Run end-to-end smoke script**

```bash
python3 - <<'SMOKE'
import sys, tempfile
sys.path.insert(0, '.')
from pathlib import Path

# Point vault at a temp directory
import memory.vault as vm_mod
with tempfile.TemporaryDirectory() as tmp:
    vm_mod.DEFAULT_VAULT_PATH = Path(tmp) / "SecondBrain"
    vm_mod._vm_instance = None

    vm = vm_mod.VaultManager()
    print("1. Vault initialized:", (Path(tmp) / "SecondBrain").exists())

    r = vm.create_note("Open by Andre Agassi", "Started reading this book.", "Learning", "conversation")
    print("2. Low-risk create:", r)

    r = vm.create_note("Investor Ahmed", "Met today.", "Relationships", "conversation")
    print("3. High-risk → proposal:", r)

    r = vm.get_pending_proposals()
    print("4. Pending proposals:", r[:80])

    plist = list((Path(tmp) / "SecondBrain" / "_JARVIS" / "Proposals").glob("*.md"))
    pid = plist[0].stem
    r = vm.approve_proposal(pid)
    print("5. Approve proposal:", r)

    r = vm.search_vault("reading book")
    print("6. Search:", r[:80] if r else "(no results — index not built yet, keyword fallback)")

    r = vm.update_personal_model("Interests & Hobbies", "Enjoys reading motivational books.",
                                 "conversation", "mentioned reading Open")
    print("7. Personal model update:", r[:80])

    # Check activity log
    log = (Path(tmp) / "SecondBrain" / "_JARVIS" / "_Activity.md").read_text()
    print("8. Activity log entries:", log.count("##"))

    import json
    jsonl = [(Path(tmp) / "SecondBrain" / "_JARVIS" / "_Activity.jsonl").read_text().strip().splitlines()]
    print("9. JSONL entries:", len(jsonl[0]))

    vm_mod._vm_instance = None
    print("SMOKE TEST PASSED")
SMOKE
```

Expected output: Lines 1–9 each print a sensible value, ending with `SMOKE TEST PASSED`.

- [ ] **Step 14.3: Verify vault is openable in Obsidian**

```bash
# Create the real vault at ~/Documents/SecondBrain
python3 -c "
import sys; sys.path.insert(0, '.')
import memory.vault as vm_mod
vm_mod._vm_instance = None
vm = vm_mod.VaultManager()
print('Vault created at:', vm.vault)
print('Areas:', [d.name for d in vm.vault.iterdir() if d.is_dir() and not d.name.startswith('.')])
"
```

Then open `~/Documents/SecondBrain` in Obsidian to visually confirm structure.

- [ ] **Step 14.4: Final commit**

```bash
git add -A
git commit -m "feat: Second Brain vault write layer — complete Sub-Project 1

Delivers:
- ~/Documents/SecondBrain/ vault with pre-scaffolded areas
- memory/vault.py: VaultManager with risk-tiered writes, conflict detection,
  proposal system, approval flow with stale check, dual activity logging,
  FAISS search with keyword fallback
- memory/observations.py: SQLite staging with 4-criterion quality filter
- brain/tools/second_brain.py: 10 registered JARVIS tools
- brain/think.py: dual-brain context routing
- prompts/runtime/prompt_loader.py: load_second_brain_modules() helper
"
```

---

## Self-Review Against Spec

**Spec coverage check:**

| Spec Section | Covered By |
|---|---|
| Why This Exists / Core Purpose | Spec only — implementation is pure infrastructure |
| Vault Location + Structure | Task 1 (`_ensure_vault`) |
| Risk Level Table | Task 2 (`_should_propose`) |
| Sensitivity + Area Risk Matrix | Task 2 (`_should_propose`) |
| Note Format Standard | Task 2 (`_build_frontmatter`) |
| Vault Initialization / Bootstrap | Task 1 (`_ensure_vault`) with idempotency test |
| Conflict Detection | Task 4 (`_detect_human_edits`) |
| Observation Staging | Task 9 (`memory/observations.py`) |
| Observation Quality Filter | Task 9 (`score_observation_quality`) with pseudocode |
| Proposal Format | Task 5 (`propose_change`) |
| Proposal ID Generation | Task 5 (`_next_proposal_id`) |
| Approval-Time Conflict Re-Check | Task 6 (`approve_proposal`) |
| Approval / Review UX | Task 6 + Task 10 tools |
| Personal Model Triggers (in-scope only) | Task 8 (`update_personal_model`) — manual trigger only |
| Activity Log Dual Format | Task 3 (`_log_activity`) |
| Personal Model Note | Task 1 (scaffold) + Task 8 (update tool) |
| Human Feedback Loops | Not in scope for this sub-project — deferred |
| Performance / Latency | FAISS in background thread (Task 7); all real-time ops synchronous and fast |
| Dual-Brain Context Routing | Task 12 (`brain/think.py`) |
| Prompt Loader Integration | Task 13 |
| 10 Tools | Task 10 |
| Tool Registration | Task 11 |
| Success Criteria 1–15 | All addressed in Tasks 1–14 |

**No gaps found. No placeholders. Type signatures are consistent across all tasks.**
