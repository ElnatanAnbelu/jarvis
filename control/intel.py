"""
Phase 7 — Intelligence upgrades.
Long-term memory search, proactive monitoring, pattern recognition.
"""
import sqlite3
import re
from pathlib import Path
from datetime import datetime, date, timedelta


# ── MEMORY SEARCH (7.1) ───────────────────────────────────────────────────────

def search_memory(query: str, limit: int = 10, days_back: int = 0) -> str:
    """
    Search across all conversation history for a query.
    Returns matching messages with timestamps.
    """
    from memory.memory import DB_PATH

    terms = [t.strip().lower() for t in re.split(r'[\s,]+', query) if len(t.strip()) > 2]
    if not terms:
        return "Search query too short."

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        where_clauses = " AND ".join(f"lower(content) LIKE ?" for t in terms)
        params = [f"%{t}%" for t in terms]

        if days_back:
            cutoff = (date.today() - timedelta(days=days_back)).isoformat()
            where_clauses += " AND timestamp >= ?"
            params.append(cutoff)

        rows = conn.execute(
            f"SELECT role, content, timestamp FROM conversations WHERE {where_clauses} ORDER BY id DESC LIMIT ?",
            params + [limit]
        ).fetchall()
        conn.close()
    except Exception as e:
        return f"Memory search error: {e}"

    if not rows:
        return f"No conversations found matching '{query}'."

    lines = [f"Memory search: '{query}' — {len(rows)} results\n"]
    for r in rows:
        ts = r["timestamp"][:16] if r["timestamp"] else "?"
        role = r["role"].upper()
        snippet = r["content"][:200].replace("\n", " ")
        lines.append(f"[{ts}] {role}: {snippet}...")
        lines.append("")

    return "\n".join(lines).strip()


def memory_timeline(topic: str, days: int = 30) -> str:
    """Show how a topic evolved over time in conversation history."""
    from memory.memory import DB_PATH

    terms = topic.lower().split()
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        rows = conn.execute(
            "SELECT role, content, timestamp FROM conversations WHERE lower(content) LIKE ? AND timestamp >= ? ORDER BY id ASC",
            (f"%{terms[0]}%", cutoff)
        ).fetchall()
        conn.close()
    except Exception as e:
        return f"Error: {e}"

    if not rows:
        return f"No mentions of '{topic}' in the last {days} days."

    lines = [f"TIMELINE: '{topic}' (last {days} days)\n"]
    for r in rows:
        ts = r["timestamp"][:10] if r["timestamp"] else "?"
        snippet = r["content"][:150].replace("\n", " ")
        if any(t in snippet.lower() for t in terms):
            lines.append(f"[{ts}] {r['role'].upper()}: {snippet}")

    return "\n".join(lines[:40])


# ── PATTERN RECOGNITION (7.4) ────────────────────────────────────────────────

def analyze_patterns(days: int = 30) -> str:
    """
    Analyze conversation patterns to detect productivity, procrastination, recurring themes.
    """
    from memory.memory import DB_PATH

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        rows = conn.execute(
            "SELECT role, content, timestamp FROM conversations WHERE timestamp >= ? ORDER BY id",
            (cutoff,)
        ).fetchall()
        conn.close()
    except Exception as e:
        return f"Error: {e}"

    if not rows:
        return f"No conversation data in the last {days} days."

    user_msgs = [r["content"] for r in rows if r["role"] == "user"]
    total = len(user_msgs)
    combined = " ".join(user_msgs).lower()

    # Theme detection
    theme_patterns = {
        "Addis Market / business": ["addis market", "marketplace", "vendor", "shop", "delivery", "business"],
        "coding / dev work":       ["code", "build", "app", "function", "bug", "deploy", "python", "react"],
        "procrastination signals": ["bored", "can't focus", "distracted", "later", "skip", "don't feel like"],
        "motivation / goals":      ["goal", "plan", "want to", "going to", "empire", "nexel", "rich", "build"],
        "personal / family":       ["mom", "dad", "family", "yostina", "eyonabel", "abigail"],
        "health / fitness":        ["gym", "workout", "diet", "sleep", "eat", "weight", "bench"],
        "entertainment":           ["anime", "apex", "fortnite", "music", "watch"],
    }

    theme_counts = {}
    for theme, keywords in theme_patterns.items():
        count = sum(combined.count(kw) for kw in keywords)
        if count > 0:
            theme_counts[theme] = count

    lines = [f"── PATTERN ANALYSIS (last {days} days) ──", "",
             f"Total messages: {total}", ""]

    if theme_counts:
        lines.append("TOPIC DISTRIBUTION:")
        total_mentions = sum(theme_counts.values()) or 1
        for theme, count in sorted(theme_counts.items(), key=lambda x: -x[1]):
            pct = count / total_mentions * 100
            bar = "█" * int(pct / 5)
            lines.append(f"  {theme:<30} {bar} {pct:.0f}%")
        lines.append("")

    # Procrastination signals
    proc_words = ["bored", "distracted", "can't focus", "skip", "later", "tired"]
    proc_count = sum(combined.count(w) for w in proc_words)
    if proc_count > 3:
        lines.append(f"PROCRASTINATION SIGNAL: {proc_count} signals detected in the last {days} days.")
        lines.append("  Pattern matches past slowdowns. Watch for this.")
        lines.append("")

    # Activity gap detection — days with no messages
    msg_dates = set()
    for r in rows:
        if r["timestamp"] and r["role"] == "user":
            msg_dates.add(r["timestamp"][:10])

    all_days = [(date.today() - timedelta(days=i)).isoformat() for i in range(days)]
    silent_days = [d for d in all_days if d not in msg_dates]
    if silent_days:
        lines.append(f"SILENT DAYS ({len(silent_days)} in {days}d): {', '.join(sorted(silent_days)[-5:])}")

    return "\n".join(lines)


# ── PROACTIVE INTELLIGENCE (7.2) ─────────────────────────────────────────────

def proactive_scan(topics: list = None) -> str:
    """
    Scan the web for things relevant to Elnatan's businesses and interests.
    Returns a digest of relevant intel.
    """
    from control.search import web_search

    default_topics = [
        "Ethiopian tech startup news 2025",
        "Ethiopian e-commerce marketplace 2025",
        "Addis Ababa business investment 2025",
        "Ethiopian Birr exchange rate",
        "African fintech venture capital 2025",
    ]

    scan_topics = topics or default_topics
    results = []

    for topic in scan_topics[:4]:
        result = web_search(topic, max_results=2)
        if "No results" not in result and "failed" not in result.lower():
            results.append(f"TOPIC: {topic}\n{result[:400]}")

    if not results:
        return "No relevant intel found in this scan."

    combined = "\n\n---\n\n".join(results)

    try:
        from brain.auth import make_client
        from brain.think import CLAUDE_MODELS

        client = make_client()  # handles api_key vs auth_token; None if unconfigured
        if client is None:
            return combined

        prompt = f"""You are JARVIS filtering intel for Elnatan Anbelu.

Raw scan results:
{combined}

Extract only what actually matters to Elnatan:
- Anything affecting Ethiopian/African e-commerce
- Competitor moves
- Investment opportunities or threats
- Economic signals that affect his business

For each item: one sentence on what it is, one sentence on why it matters to him.
Skip anything irrelevant. If nothing is relevant, say so directly."""

        resp = client.messages.create(
            model=CLAUDE_MODELS["haiku"],
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.content[0].text.strip()
    except Exception:
        return combined


# ── WEEKLY STRATEGY CHECK-IN (4.5) ───────────────────────────────────────────

def weekly_strategy_checkin() -> str:
    """Full weekly strategic review — pulls all data and generates a briefing."""
    sections = []

    # Business data
    try:
        from control.business_tools import tool_nexel_overview, tool_kpi_report, tool_follow_ups_due
        from memory.business import list_businesses
        businesses = list_businesses()
        if businesses:
            sections.append("NEXEL STATUS:\n" + tool_nexel_overview())
            for b in businesses:
                if b["active"]:
                    sections.append(f"\n{b['name'].upper()} KPIs:\n" + tool_kpi_report(b["name"]))
            sections.append("\nFOLLOW-UPS:\n" + tool_follow_ups_due(7))
    except Exception:
        pass

    # Life OS
    try:
        from control.life_os import tool_health_summary, tool_learning_summary, tool_upcoming_dates
        sections.append("\nHEALTH:\n" + tool_health_summary(days=7))
        sections.append("\nLEARNING:\n" + tool_learning_summary(days=7))
        sections.append("\nUPCOMING DATES:\n" + tool_upcoming_dates(14))
    except Exception:
        pass

    # Patterns
    try:
        sections.append("\n" + analyze_patterns(7))
    except Exception:
        pass

    # Intel scan
    try:
        intel = proactive_scan()
        if intel:
            sections.append("\nMARKET INTEL:\n" + intel)
    except Exception:
        pass

    combined = "\n".join(sections)

    try:
        from brain.auth import make_client
        from brain.think import CLAUDE_MODELS

        client = make_client()  # handles api_key vs auth_token; None if unconfigured
        if client is None:
            return combined

        prompt = f"""You are JARVIS giving Elnatan his weekly strategic check-in.

DATA:
{combined[:4000]}

Deliver the weekly check-in:
1. SITUATION: One paragraph on where things stand across all dimensions.
2. WINS: What went well this week (only real data).
3. GAPS: What's off track or needs attention.
4. THREATS: Anything external to watch.
5. THIS WEEK'S FOCUS: Top 3 priorities, ranked. Be specific.
6. JARVIS CALL: One sentence. Your honest assessment of where Elnatan is and what he needs to do.

No fluff. Real data only. Talk directly to him."""

        resp = client.messages.create(
            model=CLAUDE_MODELS["sonnet"],
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.content[0].text.strip()
    except Exception:
        return combined
