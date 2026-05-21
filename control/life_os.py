"""
Phase 6 — Life OS tool functions. Health, personal finance, reading, relationships, learning, decisions.
"""
from memory.life_data import (
    log_health, get_health_summary,
    log_personal_finance, get_personal_finance_summary,
    add_book, update_book, get_reading_list,
    add_relationship_date, get_upcoming_dates, log_relationship, get_relationship_history,
    log_decision, resolve_decision, get_decisions,
    log_learning, get_learning_summary,
)


# ── HEALTH ────────────────────────────────────────────────────────────────────

def tool_log_health(type: str, value: float, unit: str = "", notes: str = "", date_str: str = "") -> str:
    return log_health(type, value, unit, notes, date_str)


def tool_health_summary(type: str = "", days: int = 7) -> str:
    logs = get_health_summary(type, days)
    if not logs:
        return f"No health data{' for ' + type if type else ''} in the last {days} days."

    from collections import defaultdict
    by_type = defaultdict(list)
    for l in logs:
        by_type[l["type"]].append(l)

    lines = [f"── HEALTH SUMMARY (last {days} days) ──", ""]
    for t, entries in by_type.items():
        values = [e["value"] for e in entries if e["value"] is not None]
        unit = entries[0]["unit"] or ""
        if values:
            avg = sum(values) / len(values)
            lines.append(f"{t.upper()}  ({len(entries)} entries)")
            lines.append(f"  Latest: {values[0]} {unit}  |  Avg: {avg:.1f} {unit}  |  Range: {min(values):.1f}–{max(values):.1f}")
            for e in entries[:3]:
                lines.append(f"  [{e['date']}] {e['value']} {unit}{' — ' + e['notes'] if e.get('notes') else ''}")
        lines.append("")
    return "\n".join(lines).strip()


# ── PERSONAL FINANCE ──────────────────────────────────────────────────────────

def tool_log_personal_expense(amount: float, category: str = "", notes: str = "", date_str: str = "") -> str:
    return log_personal_finance("expense", amount, category, notes, date_str)


def tool_log_personal_income(amount: float, category: str = "", notes: str = "", date_str: str = "") -> str:
    return log_personal_finance("income", amount, category, notes, date_str)


def tool_personal_finance_summary(period: str = "month") -> str:
    s = get_personal_finance_summary(period)
    lines = [f"── PERSONAL FINANCES ({period.upper()}) ──", ""]
    lines.append(f"Income:   ${s['income']:>10,.2f}")
    lines.append(f"Expenses: ${s['expenses']:>10,.2f}")
    lines.append(f"Net:      ${s['net']:>10,.2f}")
    lines.append("")
    if s["by_category"]:
        lines.append("Spending by category:")
        for cat, amt in sorted(s["by_category"].items(), key=lambda x: -x[1]):
            pct = (amt / s["expenses"] * 100) if s["expenses"] else 0
            lines.append(f"  {cat:<20} ${amt:>8,.2f}  ({pct:.0f}%)")
    return "\n".join(lines)


# ── READING ───────────────────────────────────────────────────────────────────

def tool_add_book(title: str, author: str = "", status: str = "want", notes: str = "") -> str:
    return add_book(title, author, status, notes)


def tool_update_book(title: str, status: str, rating: int = None, notes: str = "") -> str:
    return update_book(title, status, rating, notes)


def tool_reading_list(status: str = "") -> str:
    books = get_reading_list(status)
    if not books:
        return "Reading list is empty." + (f" No books with status '{status}'." if status else "")

    STATUS_ORDER = {"reading": 0, "want": 1, "done": 2, "dropped": 3}
    books.sort(key=lambda b: STATUS_ORDER.get(b["status"], 9))

    lines = ["── READING LIST ──", ""]
    current_status = None
    for b in books:
        if b["status"] != current_status:
            current_status = b["status"]
            labels = {"reading": "CURRENTLY READING", "want": "WANT TO READ", "done": "FINISHED", "dropped": "DROPPED"}
            lines.append(f"[ {labels.get(current_status, current_status.upper())} ]")
        rating = f"  ★{'★'*b['rating']}{'☆'*(5-b['rating'])}" if b.get("rating") else ""
        lines.append(f"  {b['title']} — {b['author'] or '?'}{rating}")
    return "\n".join(lines)


# ── RELATIONSHIPS ─────────────────────────────────────────────────────────────

def tool_add_important_date(person: str, event_type: str, date_str: str, notes: str = "") -> str:
    return add_relationship_date(person, event_type, date_str, notes)


def tool_upcoming_dates(days: int = 30) -> str:
    dates = get_upcoming_dates(days)
    if not dates:
        return f"No important dates in the next {days} days."
    lines = [f"── UPCOMING DATES (next {days} days) ──", ""]
    for d in dates:
        lines.append(f"  {d['days_away']} days  —  {d['person']}'s {d['event_type']}  ({d['this_year_date']}){' — ' + d['notes'] if d.get('notes') else ''}")
    return "\n".join(lines)


def tool_log_relationship(person: str, notes: str, date_str: str = "") -> str:
    return log_relationship(person, notes, date_str)


def tool_relationship_history(person: str) -> str:
    logs = get_relationship_history(person)
    if not logs:
        return f"No conversation history with {person}."
    lines = [f"── HISTORY: {person.upper()} ──", ""]
    for l in logs:
        lines.append(f"[{l['date']}] {l['notes']}")
    return "\n".join(lines)


# ── LEARNING ──────────────────────────────────────────────────────────────────

def tool_log_learning(skill: str, type: str = "session", title: str = "", notes: str = "") -> str:
    return log_learning(skill, type, title, notes)


def tool_learning_summary(days: int = 7) -> str:
    logs = get_learning_summary(days)
    if not logs:
        return f"No learning logged in the last {days} days."

    from collections import defaultdict
    by_skill = defaultdict(list)
    for l in logs:
        by_skill[l["skill"]].append(l)

    lines = [f"── LEARNING SUMMARY (last {days} days) ──", ""]
    for skill, entries in by_skill.items():
        lines.append(f"{skill.upper()} ({len(entries)} sessions)")
        for e in entries[:3]:
            lines.append(f"  [{e['date']}] {e['title'] or e['type']} — {e['notes'] or ''}")
        lines.append("")
    return "\n".join(lines).strip()


# ── DECISIONS ─────────────────────────────────────────────────────────────────

def tool_decision_framework(question: str, context: str = "", options: str = "") -> str:
    """Generate a structured decision framework using Claude."""
    try:
        from brain.think import _get_auth_key, CLAUDE_MODELS
        import anthropic

        key = _get_auth_key()
        if not key:
            return "Claude API key unavailable."

        # Pull past decisions for context
        past = get_decisions("resolved")[:5]
        past_str = "\n".join(
            f"- '{d['question']}' → '{d['chosen']}' | Outcome: {d.get('outcome','unknown')}"
            for d in past
        ) if past else "No past decisions logged."

        prompt = f"""You are JARVIS helping Elnatan make a critical decision.

QUESTION: {question}
CONTEXT: {context or 'None provided'}
OPTIONS CONSIDERED: {options or 'Not specified — suggest options'}

PAST DECISIONS (for pattern awareness):
{past_str}

Build a decision framework:
1. Reframe the question clearly
2. List the realistic options (3 max)
3. For each option: pros, cons, risks, reversibility
4. Key factors that should drive the decision
5. JARVIS recommendation — one clear choice with reasoning
6. What information would change your recommendation?

Be direct. Give Elnatan a real answer, not a list of "it depends." He has to decide."""

        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model=CLAUDE_MODELS["haiku"],
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.content[0].text.strip()
    except Exception as e:
        return f"Decision framework error: {e}"


def tool_log_decision(question: str, chosen: str, reasoning: str = "") -> str:
    return log_decision(question, chosen, reasoning)


def tool_resolve_decision(question: str, outcome: str) -> str:
    return resolve_decision(question, outcome)


def tool_decision_history() -> str:
    decisions = get_decisions()
    if not decisions:
        return "No decisions logged yet."
    lines = ["── DECISION HISTORY ──", ""]
    for d in decisions:
        status = "✓" if d["status"] == "resolved" else "◌"
        lines.append(f"{status} {d['question']}")
        lines.append(f"  Chosen: {d['chosen']}")
        if d.get("outcome"):
            lines.append(f"  Outcome: {d['outcome']}")
        lines.append(f"  [{d['created_at'][:10]}]")
        lines.append("")
    return "\n".join(lines).strip()


# ── LIFE BRIEFING ─────────────────────────────────────────────────────────────

def life_briefing() -> str:
    """Quick life OS snapshot — upcoming dates, health, reading."""
    lines = []

    # Upcoming important dates
    dates = get_upcoming_dates(14)
    if dates:
        lines.append("IMPORTANT DATES (next 14 days):")
        for d in dates[:5]:
            lines.append(f"  {d['days_away']}d — {d['person']}'s {d['event_type']}")
        lines.append("")

    # Recent health
    health = get_health_summary(days=3)
    if health:
        lines.append("RECENT HEALTH:")
        for h in health[:4]:
            lines.append(f"  [{h['date']}] {h['type']}: {h['value']} {h['unit'] or ''}")
        lines.append("")

    # Currently reading
    reading = [b for b in get_reading_list("reading")]
    if reading:
        lines.append("READING:")
        for b in reading[:2]:
            lines.append(f"  {b['title']} — {b['author'] or '?'}")
        lines.append("")

    return "\n".join(lines).strip() if lines else ""
