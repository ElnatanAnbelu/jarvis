"""
Second Brain tools — expose VaultManager operations to JARVIS.
All 10 tools use the @tool decorator from brain.tools.registry.
"""
import threading

from brain.tools.registry import tool

# ── Singleton ──────────────────────────────────────────────────────────────────
# Module-level singleton so the VaultManager (with its FAISS index state)
# is created once per process, not on every tool call.

_vault_instance = None
_vault_lock = threading.Lock()


def _vault():
    """Return the VaultManager singleton, creating it if needed."""
    global _vault_instance
    if _vault_instance is None:
        with _vault_lock:
            if _vault_instance is None:
                import memory.vault as _mod
                # Respect any DEFAULT_VAULT_PATH override set by tests
                _vault_instance = _mod.VaultManager()
    return _vault_instance


# ── Tool 1: create_brain_note ──────────────────────────────────────────────────

@tool(
    description=(
        "Create a new note in Elnatan's Personal Second Brain. "
        "Auto-writes to low-risk areas (Learning, Daily, Archive); "
        "creates a proposal for high-risk areas (Business, Relationships, Decisions) "
        "or high-sensitivity content. Always include the source of the information."
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


# ── Tool 2: update_brain_note ──────────────────────────────────────────────────

@tool(
    description=(
        "Append new information to an existing note in the Personal Second Brain. "
        "If the note has been manually edited since JARVIS last wrote to it, "
        "creates a proposal instead of writing directly. "
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


# ── Tool 3: propose_brain_change ───────────────────────────────────────────────

@tool(
    description=(
        "Explicitly stage a proposed change to the Personal Second Brain for human review. "
        "Use this for anything sensitive, uncertain, or high-stakes. "
        "Elnatan must approve the proposal before the change is applied."
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


# ── Tool 4: search_brain ───────────────────────────────────────────────────────

@tool(
    description=(
        "Search the Personal Second Brain using semantic or keyword search. "
        "Use for personal queries about Elnatan's life, interests, goals, patterns, "
        "relationships, or anything he has shared over time."
    ),
    parameters={
        "query":       {"type": "string", "description": "Search query"},
        "max_results": {"type": "integer", "description": "Max results to return (default 3)"},
    }
)
def search_brain(query: str, max_results: int = 3) -> str:
    return _vault().search_vault(query, max_results)


# ── Tool 5: get_brain_note ─────────────────────────────────────────────────────

@tool(
    description="Read a specific note from the Personal Second Brain by title or path.",
    parameters={
        "title_or_path": {"type": "string",
                          "description": "Note reference, e.g. 'Learning/React Hooks' "
                                         "or just 'React Hooks'"},
    }
)
def get_brain_note(title_or_path: str) -> str:
    return _vault().get_note(title_or_path)


# ── Tool 6: list_brain_notes ───────────────────────────────────────────────────

@tool(
    description="List notes in the Personal Second Brain, optionally filtered by area.",
    parameters={
        "area": {"type": "string",
                 "description": "Optional area to filter: Learning, Daily, Personal, Goals, "
                                "Business, Relationships, Decisions, Archive. "
                                "Leave empty for all."},
    }
)
def list_brain_notes(area: str = "") -> str:
    return _vault().list_notes(area if area else None)


# ── Tool 7: review_proposals ───────────────────────────────────────────────────

@tool(
    description=(
        "Show all pending proposals awaiting review in the Personal Second Brain. "
        "These are changes JARVIS wants to make but needs Elnatan's approval for."
    ),
    parameters={}
)
def review_proposals() -> str:
    return _vault().get_pending_proposals()


# ── Tool 8: approve_proposal ───────────────────────────────────────────────────

@tool(
    description=(
        "Approve a pending proposal and apply the change to the Personal Second Brain. "
        "Re-checks for conflicts (stale detection) at approval time. "
        "Use the proposal ID shown in review_proposals output, e.g. '2026-05-28-001'."
    ),
    parameters={
        "proposal_id": {"type": "string",
                        "description": "Proposal ID from review_proposals output"},
    }
)
def approve_proposal(proposal_id: str) -> str:
    return _vault().approve_proposal(proposal_id)


# ── Tool 9: reject_proposal ────────────────────────────────────────────────────

@tool(
    description=(
        "Reject a pending proposal. The file is preserved with status 'rejected' "
        "for reference but the change is not applied to the vault."
    ),
    parameters={
        "proposal_id": {"type": "string", "description": "Proposal ID to reject"},
    }
)
def reject_proposal(proposal_id: str) -> str:
    return _vault().reject_proposal(proposal_id)


# ── Tool 10: update_personal_model ────────────────────────────────────────────

@tool(
    description=(
        "Propose an update to Elnatan's Personal Model in the Second Brain. "
        "Always creates a proposal — never auto-writes. "
        "Must include supporting evidence (observations, sessions) that justify the update."
    ),
    parameters={
        "section": {"type": "string",
                    "description": "Section to update: 'Interests & Hobbies', "
                                   "'Energy Patterns', 'Decision-Making Style', "
                                   "'Communication Preferences', 'Known Challenges', "
                                   "or 'Relationship Patterns'"},
        "content": {"type": "string", "description": "The proposed update content"},
        "source":  {"type": "string", "description": "Source: conversation, observation, etc."},
        "supporting_observations": {"type": "string",
                                    "description": "Evidence supporting this update"},
    }
)
def update_personal_model(section: str, content: str, source: str,
                          supporting_observations: str = "") -> str:
    return _vault().update_personal_model(section, content, source, supporting_observations)
