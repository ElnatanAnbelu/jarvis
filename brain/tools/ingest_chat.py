"""
Claude chat transcript -> Second Brain proposals.

Reads a transcript file (markdown, JSON export, or plain text) and uses
Claude Haiku to extract structured insights:

  - Decisions Elnatan made
  - Patterns about how he thinks or works
  - Topics he was reading/researching
  - People he mentioned
  - Goals or commitments he stated

Each insight is staged as a Second Brain *proposal* so Elnatan reviews
before any vault content lands. The raw transcript is NOT copied into
the vault — only the distilled insights. This avoids the noise/dilution
problem of dumping raw transcripts.

JARVIS-only tool.
"""
import json
import os
import re
from pathlib import Path

from brain.tools.registry import tool


_EXTRACTION_PROMPT = """You are a memory extractor for Elnatan Anbelu's Personal Second Brain.

Read this Claude conversation transcript. Extract ONLY lasting, high-signal insights — things worth retaining months from now. Ignore code snippets, debugging back-and-forth, and one-off questions.

For each insight, output exactly:
INSIGHT_TYPE: decision | pattern | interest | goal | person | preference
AREA: Personal | Business | Learning | Relationships | Goals | Decisions | Daily
TITLE: <3-7 word title>
CONTENT: <one to three sentences capturing what matters>
EVIDENCE: <one short quote or paraphrase from the transcript supporting this>
---

Be strict. Most chats yield 0-3 real insights. If nothing is worth saving, output nothing.

Forbidden:
- Inventing details not in the transcript
- Extracting routine code/tool questions
- Vague generalities ("he likes learning")
- Anything you'd be unable to source from a specific moment in the transcript

TRANSCRIPT:
{transcript}
"""


def _read_transcript(path: str) -> str:
    """Read a transcript from .md, .txt, or .json (Claude export format).

    Returns plain text suitable for the extraction prompt. Truncates to
    fit within Haiku's window.
    """
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Transcript not found: {path}")
    raw = p.read_text(encoding="utf-8", errors="ignore")

    # Claude.ai JSON export — array of {role, content} objects
    if p.suffix.lower() == ".json":
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                lines = []
                for msg in data:
                    role = msg.get("role", "?").upper()
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        content = " ".join(
                            c.get("text", "") for c in content
                            if isinstance(c, dict)
                        )
                    lines.append(f"{role}: {content}")
                raw = "\n\n".join(lines)
        except Exception:
            pass  # fall through, treat as text

    # Hard cap at ~80k chars to stay safely inside Haiku's context window
    return raw[:80000]


def _parse_insights(extraction_text: str) -> list:
    """Parse the Haiku output back into structured insight dicts.

    Format per insight block (separated by '---'):
      INSIGHT_TYPE: ...
      AREA: ...
      TITLE: ...
      CONTENT: ...
      EVIDENCE: ...
    """
    out = []
    blocks = [b.strip() for b in (extraction_text or "").split("---") if b.strip()]
    for block in blocks:
        rec = {}
        for line in block.splitlines():
            m = re.match(r"^\s*(INSIGHT_TYPE|AREA|TITLE|CONTENT|EVIDENCE)\s*:\s*(.*)",
                         line, re.IGNORECASE)
            if m:
                rec[m.group(1).lower()] = m.group(2).strip()
        # Require minimum viable shape
        if rec.get("title") and rec.get("content") and rec.get("area"):
            out.append(rec)
    return out


def _call_haiku_for_extraction(transcript: str) -> str:
    """Run the extraction prompt through Claude Haiku."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    is_oauth = False
    if not api_key or api_key.startswith("sk-ant-oat"):
        api_key = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
        is_oauth = True
    if not api_key:
        return ""
    try:
        import anthropic
        client = (anthropic.Anthropic(auth_token=api_key) if is_oauth
                  else anthropic.Anthropic(api_key=api_key))
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": _EXTRACTION_PROMPT.format(transcript=transcript),
            }],
        )
        return (resp.content[0].text or "").strip()
    except Exception as e:
        return f"[extraction failed: {e}]"


@tool(
    description=(
        "Synthesize a Claude conversation transcript into Second Brain proposals. "
        "Reads the file at the given path (.md, .txt, or .json), extracts "
        "lasting insights (decisions, patterns, interests, goals, people), "
        "and stages each as a vault proposal for review. Does NOT copy the raw "
        "transcript into the vault. JARVIS-only."
    ),
    parameters={
        "transcript_path": {"type": "string",
                            "description": "Absolute path to the transcript file"},
        "session_label":   {"type": "string",
                            "description": "Short label for this chat (e.g. 'May 28 vault design')"},
    },
    allowed_agents=["JARVIS"],
)
def synthesize_claude_chat(transcript_path: str, session_label: str = "claude chat") -> str:
    try:
        transcript = _read_transcript(transcript_path)
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"Could not read transcript: {e}"

    if not transcript.strip():
        return "Transcript is empty."

    extraction = _call_haiku_for_extraction(transcript)
    if not extraction or extraction.startswith("[extraction failed"):
        return f"Extraction failed: {extraction or 'no response'}"

    insights = _parse_insights(extraction)
    if not insights:
        return "No high-signal insights found in this transcript. Nothing staged."

    # Stage each insight as a proposal
    try:
        from brain.tools.second_brain import _vault
        vm = _vault()
    except Exception as e:
        return f"Vault unavailable: {e}"

    staged = []
    for ins in insights:
        title = ins.get("title", "").strip()[:80]
        area = ins.get("area", "Daily").strip()
        content_body = ins.get("content", "").strip()
        evidence = ins.get("evidence", "").strip()
        full_content = content_body
        if evidence:
            full_content += f"\n\n> {evidence}"

        try:
            result = vm.propose_change(
                title=title,
                proposed_content=full_content,
                action="create",
                area=area,
                source=f"Claude chat — {session_label}",
                reason=f"Synthesized from chat transcript at {transcript_path}",
            )
            staged.append(f"  - [{area}/{title}] {ins.get('insight_type', '')}")
        except Exception as e:
            staged.append(f"  - FAILED: {title} — {e}")

    body = "\n".join(staged)
    return (
        f"Chat synthesis complete. {len(insights)} insight(s) staged as proposals "
        f"from {session_label}:\n\n{body}\n\n"
        f"Review with `review_proposals` and approve the ones worth keeping."
    )
