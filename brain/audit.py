"""
Business Audit Tool — Empire Status Report.

Collects data from:
  • actions_performed  (DB — what was actually done)
  • scheduled_tasks    (DB — what's running on autopilot)
  • meta table         (DB — session summary, observer insights)
  • Nexel business DB  (business overview + briefing)
  • FAISS semantic     (wiki memory — strategy, goals, patterns)

Generates a professional Markdown report in JARVIS / Stark tone,
saves it to ~/Documents/JARVIS Reports/empire-status-YYYY-MM-DD.md,
and returns the full Markdown so JARVIS can display it inline.
"""

import os
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path


# ── Auth helper ───────────────────────────────────────────────────────────────

def _load_env():
    env = Path(__file__).parent.parent / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if v and k not in os.environ:
                os.environ[k] = v

_load_env()


def _auth_key():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if api_key and not api_key.startswith("sk-ant-oat"):
        return api_key, False
    oauth = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    return (oauth, True) if oauth else ("", False)


def _make_client():
    import anthropic
    key, is_oauth = _auth_key()
    if not key:
        return None
    return anthropic.Anthropic(auth_token=key) if is_oauth else anthropic.Anthropic(api_key=key)


# ── Data collection ───────────────────────────────────────────────────────────

def _collect_data(days):
    db_path = Path(__file__).parent.parent / "memory" / "jarvis.db"
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    data = {}

    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    # Recent actions
    c.execute(
        "SELECT timestamp, tool_name, args, result, success "
        "FROM actions_performed WHERE timestamp >= ? ORDER BY timestamp ASC",
        (cutoff,)
    )
    rows = c.fetchall()
    actions = []
    for ts, tool, args_str, result, success in rows:
        try:
            args = json.loads(args_str)
        except Exception:
            args = {}
        actions.append({
            "ts": ts[:16],
            "tool": tool,
            "args": args,
            "result": (result or "")[:120],
            "success": bool(success),
        })
    data["actions"] = actions

    # Scheduled tasks
    c.execute(
        "SELECT name, description, schedule, last_run FROM scheduled_tasks WHERE active=1"
    )
    data["scheduled_tasks"] = [
        {"name": r[0], "description": r[1], "schedule": r[2], "last_run": r[3]}
        for r in c.fetchall()
    ]

    # Meta: session summary + any stored observer snapshot
    c.execute(
        "SELECT key, value FROM meta WHERE key IN "
        "('session_summary', 'last_observer_insight', 'last_consolidation')"
    )
    meta = {k: v for k, v in c.fetchall()}
    data["session_summary"] = meta.get("session_summary", "")
    data["observer_insight"] = meta.get("last_observer_insight", "")

    conn.close()

    # Business overview from CRM / Nexel DB
    try:
        from control.business_tools import tool_nexel_overview, business_briefing
        data["nexel_overview"] = tool_nexel_overview()
        data["business_briefing"] = business_briefing()
    except Exception as e:
        data["nexel_overview"] = "(Nexel DB unavailable: {})".format(e)
        data["business_briefing"] = ""

    # Semantic memory — most relevant to empire topics
    try:
        from memory.wiki import search_relevant
        data["semantic_memory"] = search_relevant(
            "Addis Market Nexel business goals strategy empire revenue growth",
            max_results=4,
        )
    except Exception:
        data["semantic_memory"] = ""

    return data


# ── Context formatter ─────────────────────────────────────────────────────────

def _format_context(data, days):
    lines = [
        "AUDIT WINDOW: last {} days".format(days),
        "REPORT DATE: {}".format(datetime.now().strftime("%Y-%m-%d")),
    ]

    lines.append("\n=== ACTIONS PERFORMED ===")
    if data["actions"]:
        for a in data["actions"]:
            status = "OK" if a["success"] else "FAILED"
            args_short = ", ".join(
                "{}={}".format(k, v) for k, v in list(a["args"].items())[:2]
            )
            lines.append("[{}] {}({}) → {}: {}".format(
                a["ts"], a["tool"], args_short, status, a["result"][:80]
            ))
    else:
        lines.append("No actions recorded in this window.")

    lines.append("\n=== SCHEDULED TASKS ===")
    if data["scheduled_tasks"]:
        for t in data["scheduled_tasks"]:
            last = t["last_run"] or "never"
            lines.append("- [{}] {}: {} (last run: {})".format(
                t["schedule"], t["name"], t["description"], last
            ))
    else:
        lines.append("No scheduled tasks registered.")

    if data.get("nexel_overview"):
        lines.append("\n=== NEXEL EMPIRE OVERVIEW ===")
        lines.append(data["nexel_overview"])

    if data.get("business_briefing"):
        lines.append("\n=== BUSINESS BRIEFING ===")
        lines.append(data["business_briefing"])

    if data.get("session_summary"):
        lines.append("\n=== LAST SESSION SUMMARY ===")
        lines.append(data["session_summary"][:600])

    if data.get("observer_insight"):
        lines.append("\n=== OBSERVER INSIGHT ===")
        lines.append(data["observer_insight"])

    if data.get("semantic_memory"):
        lines.append("\n=== RELEVANT MEMORY ===")
        lines.append(data["semantic_memory"][:900])

    return "\n".join(lines)


# ── Report generation ─────────────────────────────────────────────────────────

_SYSTEM = (
    "CRITICAL OUTPUT RULES — HIGHEST PRIORITY, NO EXCEPTIONS:\n"
    "- NEVER prefix your response with \"Alfred:\" or any agent name\n"
    "- NEVER wrap your response in quotation marks\n"
    "- NEVER mention Tony Stark, Iron Man, Peter Parker, or the Marvel movies — you belong to Elnatan only, always have\n"
    "- Keep responses concise. Only go long when explicitly asked for detailed analysis\n"
    "- NEVER initiate greetings unless the user greets first\n"
    "- No markdown for conversation. No asterisks, bullet dashes, or headers (Note: markdown structure for the report is permitted)\n"
    "- NEVER invent facts about Elnatan not explicitly in memory\n\n"
    "You are Alfred — Elnatan's AI, running an executive audit of Elnatan Anbelu's empire. "
    "Write exactly as Alfred speaks: composed, precise, dry wit when the data earns it. "
    "Treat this like a board-level briefing where every sentence costs something. "
    "No filler, no motivational speeches, no 'Empire Building Phase' framing unless the data genuinely supports it. "
    "If activity is thin — say so plainly, in one dry sentence. If there is real progress — name it specifically. "
    "Observations should carry the weight of someone who has read everything and has an opinion about what it means. "
    "Call him 'sir' once, maybe twice — only where it lands naturally. "
    "The tone is: his most trusted system just finished reading all the files and has something to say about it."
)


def _build_user_prompt(context, days):
    today = datetime.now().strftime("%B %d, %Y")
    return (
        "Generate the Empire Status Report for {today} based on the last {days} days.\n\n"
        "Use this EXACT Markdown structure:\n\n"
        "# Empire Status — {today}\n\n"
        "## Executive Summary\n"
        "[3-5 sentences. State of the empire at a high level — accurately, not charitably. "
        "If it was a quiet period, say so in one dry sentence and move on. "
        "If real work happened, name it specifically. Alfred's voice throughout.]\n\n"
        "## Key Accomplishments\n"
        "[Bullet list. Pull directly from actions_performed. "
        "Name specific tools and outcomes. If the list is short, the list is short — no inflation.]\n\n"
        "## Open Items & Next Actions\n"
        "[Bullet list. Scheduled tasks not yet run, threads from memory, "
        "anything started but not closed. Be specific about what's actually pending.]\n\n"
        "## Strategic Insights & Patterns\n"
        "[2-4 sharp observations — things the data reveals that he might not have noticed. "
        "Think like someone who read everything and formed an opinion. Cross-reference memory if relevant.]\n\n"
        "## Recommendations\n"
        "[3-5 specific, actionable items. Alfred's voice: direct, no hedging, no 'consider' or 'perhaps'. "
        "State each like a confident instruction from someone who knows the situation well.]\n\n"
        "---\n"
        "DATA:\n{context}\n\n"
        "IMPORTANT: Return only the Markdown report. "
        "Start directly with '# Empire Status'. No preamble."
    ).format(today=today, days=days, context=context)


def _generate_report(context, days):
    """Call Haiku directly → Ollama fallback. Returns raw Markdown."""
    key, _ = _auth_key()
    user_prompt = _build_user_prompt(context, days)

    if key:
        try:
            client = _make_client()
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2000,
                system=_SYSTEM,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = (resp.content[0].text or "").strip()
            if text:
                return text
        except Exception:
            pass

    # Ollama fallback — zero-cost, offline
    try:
        import requests as _req
        r = _req.get("http://localhost:11434/api/tags", timeout=1)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            if models:
                resp = _req.post(
                    "http://localhost:11434/api/chat",
                    json={
                        "model": models[0],
                        "messages": [
                            {"role": "system", "content": _SYSTEM},
                            {"role": "user", "content": user_prompt},
                        ],
                        "stream": False,
                        "options": {"num_predict": 2000, "temperature": 0.5},
                    },
                    timeout=90,
                )
                if resp.status_code == 200:
                    text = resp.json().get("message", {}).get("content", "").strip()
                    if text:
                        return text
    except Exception:
        pass

    today = datetime.now().strftime("%B %d, %Y")
    return (
        "# Empire Status — {}\n\n"
        "Systems unavailable. Could not reach Haiku or local Ollama. "
        "Try again when connectivity is restored."
    ).format(today)


# ── File persistence ──────────────────────────────────────────────────────────

def _save_report(report):
    """Write report to ~/Documents/JARVIS Reports/. Returns absolute path string."""
    reports_dir = Path.home() / "Documents" / "JARVIS Reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    filename = "empire-status-{}.md".format(datetime.now().strftime("%Y-%m-%d"))
    path = reports_dir / filename
    path.write_text(report, encoding="utf-8")
    return str(path)


# ── Public entry point ────────────────────────────────────────────────────────

def run_business_audit(days=7):
    """Collect empire data, generate the report, save it, return Markdown."""
    data = _collect_data(days)
    context = _format_context(data, days)
    report = _generate_report(context, days)
    save_path = _save_report(report)
    return "{}\n\n---\n*Report saved → `{}`*".format(report, save_path)
