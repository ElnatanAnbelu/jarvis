import os
import requests
from pathlib import Path
from datetime import date, datetime

BRIEFING_DATE_FILE = Path(__file__).parent.parent / ".briefing_date"


def already_sent_today() -> bool:
    if not BRIEFING_DATE_FILE.exists():
        return False
    return BRIEFING_DATE_FILE.read_text().strip() == str(date.today())


def mark_sent():
    BRIEFING_DATE_FILE.write_text(str(date.today()))


def _get_weather() -> str:
    try:
        from brain.tools import execute_tool
        return execute_tool("get_weather", {"city": "Madison, SD"})
    except Exception:
        return "Weather unavailable."


def _get_tasks() -> str:
    try:
        from memory.memory import get_facts
        facts = get_facts()
        if facts:
            return facts[:300]
    except Exception:
        pass
    return ""


def _get_calendar() -> str:
    try:
        from control.calendar import get_events_str
        return get_events_str()
    except Exception:
        return ""


def _get_news() -> str:
    try:
        from brain.news import get_news_briefing
        return get_news_briefing()
    except Exception:
        return ""


def _get_habits() -> str:
    try:
        from memory.goals import get_missed_habits
        missed = get_missed_habits()
        if missed:
            return f"Habits not done yet: {', '.join(missed)}"
    except Exception:
        pass
    return ""


def _get_recent_history() -> str:
    """Get yesterday's and recent conversation snippets."""
    try:
        from memory.memory import get_recent_history
        rows = get_recent_history(limit=8)
        if not rows:
            return ""
        lines = []
        for role, content in rows:
            label = "ELNATAN" if role == "user" else role.upper()
            lines.append(f"{label}: {content[:120]}")
        return "\n".join(lines)
    except Exception:
        return ""


def _get_business_briefing() -> str:
    try:
        from control.business_tools import business_briefing
        return business_briefing()
    except Exception:
        return ""


def _get_life_briefing() -> str:
    try:
        from control.life_os import life_briefing
        return life_briefing()
    except Exception:
        return ""


def generate_briefing() -> str:
    now = datetime.now()
    day = now.strftime("%A, %B %d")
    weather = _get_weather()
    tasks = _get_tasks()
    calendar = _get_calendar()
    news = _get_news()
    habits = _get_habits()
    history = _get_recent_history()
    business = _get_business_briefing()
    life = _get_life_briefing()

    prompt = f"""Generate a sharp morning briefing for Elnatan. Today is {day}.

REAL DATA ONLY — only use what is provided below. Do not invent anything.

Weather: {weather if weather else 'unavailable'}
Calendar today: {calendar if calendar and calendar != 'No events scheduled.' else 'No events scheduled'}
Habits not done: {habits if habits else 'None missed'}
Active tasks: {tasks if tasks else 'No tasks found'}
News: {news if news else 'No news available'}
Recent conversation context: {history if history else 'No recent conversations'}
Business status: {business if business else 'No business data yet'}
Life OS: {life if life else 'No life data'}

RULES:
- Only report what is in the data above. If a section is empty, skip it entirely.
- Do NOT invent tasks, events, business updates, timelines, or anything not listed above.
- Reference recent conversation only if there is a clear unfinished task or follow-up.
- If there are KPIs off target, follow-ups overdue, or important dates in 3 days, flag them.
- Keep it under 6 sentences. Talk directly to Elnatan. Sharp and factual."""

    try:
        from brain.think import _get_auth_key, CLAUDE_MODELS
        import anthropic
        auth_key = _get_auth_key()
        if auth_key:
            client = anthropic.Anthropic(api_key=auth_key)
            resp = client.messages.create(
                model=CLAUDE_MODELS["haiku"],
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text.strip()
    except Exception:
        pass

    # Fallback
    return f"Good morning. {day}. {weather}. Addis Market doesn't build itself — what's the one thing you're finishing today?"


def send_telegram_briefing(text: str):
    """Send briefing to Telegram."""
    try:
        from pathlib import Path as _Path
        env = _Path(__file__).parent.parent / ".env"
        token = ""
        chat_id = ""
        for line in env.read_text().splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                token = line.split("=", 1)[1].strip()
            if line.startswith("TELEGRAM_CHAT_ID="):
                chat_id = line.split("=", 1)[1].strip()
        if not token or not chat_id:
            return
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": f"*JARVIS — Morning Briefing*\n{text}", "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception:
        pass


def get_briefing_text() -> str:
    return generate_briefing()


def run_briefing(speak_fn=None):
    """Run the morning briefing if not already sent today."""
    if already_sent_today():
        return

    text = generate_briefing()
    mark_sent()

    print("\n" + "=" * 50)
    print("  MORNING BRIEFING")
    print("=" * 50)
    print(text)
    print("=" * 50 + "\n")

    if speak_fn:
        speak_fn(text, "JARVIS")

    send_telegram_briefing(text)
