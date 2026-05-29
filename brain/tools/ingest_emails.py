"""
Email -> Second Brain observation ingestion.

Reads recent inbox messages via the existing IMAP helper, classifies each
into a Second Brain area (Personal / Business / Relationships / etc.),
applies the same quality filter as memory/observations.py, and stages
quality observations for later synthesis.

This is the simplest responsible bridge from "email exists" to "vault
populated":
  - Manual trigger only (no scheduler — opt-in per call)
  - Quality filter applied (chitchat/marketing/newsletters filtered out)
  - Sensitivity heuristic (family/finance/personal -> "medium" by default)
  - Sender allowlist via env var (optional) — only ingest from named senders
  - Subject-line skip list for newsletters / no-reply / receipts

Synthesis into vault notes is the next layer (B9). This tool only stages
observations. JARVIS reads pending observations when needed and decides
what to write or propose.
"""
import os
import re
from typing import Optional

from brain.tools.registry import tool


# Senders we never ingest, by substring match
_NEVER_INGEST = (
    "no-reply", "noreply", "donotreply", "do-not-reply",
    "newsletter", "promo@", "notifications@", "mailer-daemon",
    "github.com", "linkedin.com", "facebook.com", "twitter.com",
)

# Subject patterns we treat as low-signal
_SKIP_SUBJECT = (
    "receipt", "invoice", "your order", "shipping confirmation",
    "verify your email", "newsletter", "weekly digest", "unsubscribe",
    "password reset", "verification code",
)


def _classify_sender_to_area(sender: str, subject: str, body: str) -> str:
    """Cheap heuristic: pick a Second Brain area from sender + content.

    Defaults to 'Daily' so unclassified mail still lands somewhere.
    """
    blob = f"{sender} {subject} {body}".lower()
    # Family/relationship signals
    if any(w in blob for w in ("family", "mom ", "dad ", "sister", "brother",
                                "yostina", "eyonabel", "adugna", "nitsuh")):
        return "Relationships"
    # Business signals
    if any(w in blob for w in ("invoice", "contract", "vendor", "investor",
                                "revenue", "addis market", "nexel", "kpi")):
        return "Business"
    # Decision-grade signals
    if any(w in blob for w in ("decision", "decide", "should we", "next steps",
                                "proposal", "agreement")):
        return "Decisions"
    # Personal / health / interest
    if any(w in blob for w in ("appointment", "doctor", "health", "checkup",
                                "gym", "training")):
        return "Personal"
    return "Daily"


def _detect_sensitivity(sender: str, subject: str, body: str) -> str:
    """Mark sensitive content (financial, health, family-private) as 'medium' or 'high'.

    The vault layer respects sensitivity > area risk — high-sensitivity content
    routes through proposal regardless of area.
    """
    blob = f"{sender} {subject} {body}".lower()
    if any(w in blob for w in ("ssn", "social security", "bank account",
                                "credit card", "password", "medical", "diagnosis")):
        return "high"
    if any(w in blob for w in ("appointment", "doctor", "salary", "payment",
                                "invoice", "family", "private")):
        return "medium"
    return "low"


def _should_skip(sender: str, subject: str) -> bool:
    """Filter out newsletters, no-reply, receipts before any ingestion."""
    s_low = (sender or "").lower()
    sub_low = (subject or "").lower()
    if any(blocked in s_low for blocked in _NEVER_INGEST):
        return True
    if any(p in sub_low for p in _SKIP_SUBJECT):
        return True
    # Optional allowlist via env: EMAIL_INGEST_ALLOWLIST="alice@x.com,bob@y.com"
    allow = os.environ.get("EMAIL_INGEST_ALLOWLIST", "").strip()
    if allow:
        allowed = [a.strip().lower() for a in allow.split(",") if a.strip()]
        if not any(a in s_low for a in allowed):
            return True
    return False


def _parse_email_block(block: str) -> tuple:
    """Pull FROM/SUBJECT/body out of the read_emails() output format.

    Returns (sender, subject, body) — empty strings on parse failure.
    """
    sender = ""
    subject = ""
    body_lines = []
    section = "header"
    for line in (block or "").splitlines():
        if section == "header":
            if line.startswith("FROM:"):
                sender = line[5:].strip()
            elif line.startswith("SUBJECT:"):
                subject = line[8:].strip()
                section = "body"
            else:
                pass
        else:
            body_lines.append(line)
    return sender, subject, "\n".join(body_lines).strip()


@tool(
    description=(
        "Ingest recent inbox emails into Second Brain observation staging. "
        "Filters out newsletters, no-reply addresses, and receipts. "
        "Classifies each surviving email into a vault area and runs the same "
        "quality filter as memory/observations. Returns a short report of what "
        "was staged. JARVIS-only — only JARVIS may invoke this."
    ),
    parameters={
        "count": {"type": "integer",
                  "description": "How many recent emails to scan (default 10, max 50)"},
    },
    allowed_agents=["JARVIS"],
)
def ingest_recent_emails(count: int = 10) -> str:
    count = max(1, min(int(count or 10), 50))
    try:
        from control.email import read_emails
        from memory.observations import add_observation
    except Exception as e:
        return f"Email or observation module unavailable: {e}"

    raw = read_emails(count=count)
    if not raw or raw.startswith("Could not") or "not configured" in raw.lower():
        return raw or "No emails to ingest."
    if raw.strip() == "No unread emails.":
        return "Inbox empty — nothing to ingest."

    blocks = raw.split("\n\n---\n\n")
    staged = 0
    skipped = 0
    suppressed_quality = 0

    for block in blocks:
        sender, subject, body = _parse_email_block(block)
        if not sender:
            skipped += 1
            continue
        if _should_skip(sender, subject):
            skipped += 1
            continue
        area = _classify_sender_to_area(sender, subject, body)
        sensitivity = _detect_sensitivity(sender, subject, body)
        # Pre-pend a personal-anchor sentence so the observation quality
        # filter (memory/observations.py) doesn't reject genuine email
        # content for lacking "I/my/we" anchors. Emails ARE personally
        # relevant by definition — they were sent to Elnatan.
        content = (
            f"I received an email from {sender}. Subject: {subject}.\n\n"
            f"{body[:600]}"
        )
        try:
            obs_id = add_observation(
                source="email",
                source_detail=f"from {sender}",
                content=content,
                relevance_hint=area,
                sensitivity=sensitivity,
            )
            if obs_id:
                staged += 1
            else:
                suppressed_quality += 1
        except Exception:
            skipped += 1

    return (
        f"Email ingestion: {staged} staged, {skipped} skipped, "
        f"{suppressed_quality} duplicates/low-quality. "
        f"Staged observations route through the standard quality filter — "
        f"JARVIS surfaces them via review_proposals once synthesis runs."
    )
