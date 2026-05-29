"""Tests for the ingestion tools (emails + chat synthesis)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Tool registration ────────────────────────────────────────────────────────

def test_ingest_emails_tool_registered():
    import brain.tools.ingest_emails  # noqa
    from brain.tools.registry import TOOL_REGISTRY
    assert "ingest_recent_emails" in TOOL_REGISTRY
    assert TOOL_REGISTRY["ingest_recent_emails"]["allowed_agents"] == ["JARVIS"]


def test_synthesize_claude_chat_tool_registered():
    import brain.tools.ingest_chat  # noqa
    from brain.tools.registry import TOOL_REGISTRY
    assert "synthesize_claude_chat" in TOOL_REGISTRY
    assert TOOL_REGISTRY["synthesize_claude_chat"]["allowed_agents"] == ["JARVIS"]


# ── Email filtering / classification logic ─────────────────────────────────────

def test_should_skip_no_reply():
    from brain.tools.ingest_emails import _should_skip
    assert _should_skip("noreply@example.com", "Update") is True
    assert _should_skip("notifications@github.com", "PR review") is True


def test_should_skip_marketing_subject():
    from brain.tools.ingest_emails import _should_skip
    assert _should_skip("Marketing Co <ads@example.com>", "Weekly newsletter") is True
    assert _should_skip("Store <store@x.com>", "Your order has shipped") is True


def test_should_not_skip_real_human(monkeypatch):
    monkeypatch.delenv("EMAIL_INGEST_ALLOWLIST", raising=False)
    from brain.tools.ingest_emails import _should_skip
    assert _should_skip("Yostina <yostina@gmail.com>", "Family update") is False


def test_allowlist_filters_out_non_allowed(monkeypatch):
    monkeypatch.setenv("EMAIL_INGEST_ALLOWLIST", "yostina@gmail.com,mom@gmail.com")
    from brain.tools.ingest_emails import _should_skip
    assert _should_skip("Random <random@example.com>", "Hello") is True
    assert _should_skip("Yostina <yostina@gmail.com>", "Hi") is False


def test_classify_to_area_relationships():
    from brain.tools.ingest_emails import _classify_sender_to_area
    area = _classify_sender_to_area("yostina@gmail.com", "Family update",
                                     "Mom said hi.")
    assert area == "Relationships"


def test_classify_to_area_business():
    from brain.tools.ingest_emails import _classify_sender_to_area
    area = _classify_sender_to_area("vendor@example.com",
                                     "Invoice for Addis Market", "Total $5000")
    assert area == "Business"


def test_classify_to_area_defaults_to_daily():
    from brain.tools.ingest_emails import _classify_sender_to_area
    area = _classify_sender_to_area("stranger@example.com", "Hi", "Just saying hi")
    assert area == "Daily"


def test_sensitivity_high_for_medical():
    from brain.tools.ingest_emails import _detect_sensitivity
    s = _detect_sensitivity("clinic@example.com", "Your test results",
                             "Medical diagnosis below.")
    assert s == "high"


def test_sensitivity_medium_for_financial():
    from brain.tools.ingest_emails import _detect_sensitivity
    s = _detect_sensitivity("billing@example.com", "Invoice", "Salary deposit posted.")
    assert s == "medium"


def test_sensitivity_low_for_routine():
    from brain.tools.ingest_emails import _detect_sensitivity
    s = _detect_sensitivity("friend@example.com", "lunch?", "want to grab food")
    assert s == "low"


def test_parse_email_block():
    from brain.tools.ingest_emails import _parse_email_block
    block = "FROM: Alice <alice@x.com>\nSUBJECT: Hi\nthis is the body"
    sender, subject, body = _parse_email_block(block)
    assert "alice" in sender.lower()
    assert subject == "Hi"
    assert "body" in body


# ── Chat ingestion ────────────────────────────────────────────────────────────

def test_read_transcript_markdown(tmp_path):
    f = tmp_path / "chat.md"
    f.write_text("USER: hey\n\nASSISTANT: hi back", encoding="utf-8")
    from brain.tools.ingest_chat import _read_transcript
    text = _read_transcript(str(f))
    assert "hey" in text
    assert "hi back" in text


def test_read_transcript_json(tmp_path):
    import json
    f = tmp_path / "chat.json"
    f.write_text(json.dumps([
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]), encoding="utf-8")
    from brain.tools.ingest_chat import _read_transcript
    text = _read_transcript(str(f))
    assert "USER" in text
    assert "ASSISTANT" in text


def test_read_transcript_missing_file_raises():
    from brain.tools.ingest_chat import _read_transcript
    import pytest
    with pytest.raises(FileNotFoundError):
        _read_transcript("/nonexistent/path/xyz.md")


def test_parse_insights_extracts_well_formed_blocks():
    from brain.tools.ingest_chat import _parse_insights
    sample = (
        "INSIGHT_TYPE: decision\n"
        "AREA: Decisions\n"
        "TITLE: Switched to FAISS\n"
        "CONTENT: Chose FAISS over Chroma for vault search after testing both.\n"
        "EVIDENCE: 'FAISS is faster and easier to ship locally.'\n"
        "---\n"
        "INSIGHT_TYPE: interest\n"
        "AREA: Learning\n"
        "TITLE: Reading Atomic Habits\n"
        "CONTENT: Started Atomic Habits.\n"
        "EVIDENCE: 'Just picked it up.'\n"
    )
    result = _parse_insights(sample)
    assert len(result) == 2
    assert result[0]["area"] == "Decisions"
    assert result[0]["title"] == "Switched to FAISS"
    assert result[1]["area"] == "Learning"


def test_parse_insights_skips_incomplete_blocks():
    from brain.tools.ingest_chat import _parse_insights
    sample = (
        "INSIGHT_TYPE: pattern\n"
        "AREA: Personal\n"
        "TITLE: Only title\n"
        "---\n"  # missing content + area
    )
    result = _parse_insights(sample)
    assert result == []  # incomplete -> skipped


def test_parse_insights_empty_input():
    from brain.tools.ingest_chat import _parse_insights
    assert _parse_insights("") == []
    assert _parse_insights(None) == []
