import schedule
import time
import threading
import requests
import random
import os
from pathlib import Path
from datetime import datetime, timedelta


def _load_env():
    env = Path(__file__).parent.parent / ".env"
    for line in env.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            if v.strip() and k.strip() not in os.environ:
                os.environ[k.strip()] = v.strip()

_load_env()

_hud_queue = None  # Injected by server.py on startup


def _send(message: str):
    # Push to HUD queue (picked up by /api/proactive polling)
    if _hud_queue is not None:
        try:
            _hud_queue.put_nowait(message)
        except Exception:
            pass
    # Also send to Telegram if configured
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if token and chat_id:
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": f"*Alfred*\n{message}", "parse_mode": "Markdown"},
                timeout=8,
            )
        except Exception:
            try:
                from obs.log import log_exception
                log_exception("proactive.telegram_send_failed", logger="proactive")
            except Exception:
                pass


def _check_upcoming_events():
    """Check Apple Calendar every 30 min — alert 30 min before any event."""
    try:
        from control.calendar import get_events
        from datetime import date
        events = get_events(date.today())
        now = datetime.now()
        for event in events:
            # Parse time from "HH:MM - Event title"
            if " - " not in event:
                continue
            time_part, title = event.split(" - ", 1)
            try:
                h, m = map(int, time_part.strip().split(":"))
                event_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
                diff = (event_time - now).total_seconds() / 60
                if 25 <= diff <= 35:
                    _send(f"In 30 minutes: *{title}*. Wrap up what you're doing.")
            except Exception:
                continue
    except Exception:
        pass


def _midday_check():
    """12 PM — habits + calendar + accountability."""
    try:
        from memory.goals import get_missed_habits
        missed = get_missed_habits()

        from control.calendar import get_events
        from datetime import date
        afternoon_events = []
        now = datetime.now()
        for e in get_events(date.today()):
            if " - " in e:
                t, title = e.split(" - ", 1)
                try:
                    h, m = map(int, t.strip().split(":"))
                    if h >= 12:
                        afternoon_events.append(title)
                except Exception:
                    pass

        msg = "Midday check.\n"
        if missed:
            msg += f"Habits not done: {', '.join(missed)}.\n"
        if afternoon_events:
            msg += f"This afternoon: {', '.join(afternoon_events[:3])}.\n"
        msg += "What have you shipped today?"
        _send(msg)
    except Exception:
        pass


def _evening_check():
    """7 PM — end of day review."""
    try:
        from memory.goals import get_missed_habits
        missed = get_missed_habits()
        msg = "End of day.\n"
        if missed:
            msg += f"Still missed: {', '.join(missed)}.\n"
        msg += "Did you move the empire forward today? Name one thing you finished."
        _send(msg)
    except Exception:
        pass


def _surface_news():
    """9 AM — push relevant news without being asked."""
    try:
        from brain.news import get_news
        news = get_news(3)
        if news and news != "No relevant news found.":
            _send(f"Morning intel:\n{news}")
    except Exception:
        pass


def _focus_nudge():
    """Every 3 hours during work hours — quick push."""
    now = datetime.now().hour
    if 9 <= now <= 21:
        messages = [
            "Still locked in?",
            "Empire doesn't build itself. What are you working on right now?",
            "Quick check — on task or drifting?",
            "What's the one thing you're finishing in the next hour?",
        ]
        _send(random.choice(messages))


_COMPETITOR_KEYWORDS = [
    "Addis Market competitors", "Ethiopia e-commerce", "Jumia Ethiopia",
    "African marketplace startup", "Nexel competitor", "Ethiopian startup funding",
    "East Africa e-commerce", "Addis Ababa tech startup",
]

_competitor_last_seen = {}  # keyword → last headline seen (to avoid repeats)


def _competitor_scan():
    """Runs 3x per day — scans for competitor and market movements."""
    try:
        from control.search import news_search
        import anthropic, os as _os

        api_key = (
            _os.environ.get("ANTHROPIC_API_KEY", "").strip() or
            _os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
        )
        if not api_key:
            return

        all_results = []
        for kw in _COMPETITOR_KEYWORDS[:4]:  # Limit to 4 per scan
            try:
                result = news_search(kw, max_results=2)
                if "No news found" not in result:
                    all_results.append(result)
            except Exception:
                pass

        if not all_results:
            return

        raw = "\n\n".join(all_results)[:8000]

        # Fully-local default: skip cloud market-intel reasoning unless opted in.
        from brain.agent import cloud_reasoning_allowed
        if not cloud_reasoning_allowed():
            return

        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": f"You are Alfred scanning market intelligence for Elnatan. Review these news items about his market (Ethiopia e-commerce, Addis Market, Nexel). If anything is genuinely worth surfacing — competitor moves, funding news, major market shifts — write a 1-2 sentence alert. If nothing notable, respond with NOTHING.\n\n{raw}"
            }]
        )
        alert = (msg.content[0].text or "").strip()
        if alert and alert.upper() != "NOTHING" and len(alert) > 20:
            _send(f"Market Intel: {alert}")

    except Exception:
        pass


def _run_dynamic_task(task_id: int, description: str):
    """Execute a user-registered scheduled task via JARVIS and push result to HUD."""
    try:
        from brain.runner import run_goal
        from memory.memory import update_task_last_run
        result = run_goal(description, label=f"task:{task_id}")
        if result:
            _send(f"Scheduled task complete:\n{result[:400]}")
        update_task_last_run(task_id)
    except Exception:
        try:
            from obs.log import log_exception
            log_exception("proactive.dynamic_task_failed", logger="proactive", task_id=task_id)
        except Exception:
            pass


def _register_dynamic_tasks():
    """Load user-defined tasks from SQLite and wire them into the schedule library."""
    try:
        from memory.memory import get_scheduled_tasks
        tasks = get_scheduled_tasks(active_only=True)
        for task in tasks:
            tid, name, description, sched = task["id"], task["name"], task["description"], task["schedule"]
            fn = lambda t=tid, d=description: _run_dynamic_task(t, d)
            if sched.startswith("daily@"):
                time_str = sched.split("@", 1)[1]  # "HH:MM"
                schedule.every().day.at(time_str).do(fn).tag(f"dynamic:{name}")
            elif sched.startswith("every_") and sched.endswith("h"):
                hours = int(sched[6:-1])
                schedule.every(hours).hours.do(fn).tag(f"dynamic:{name}")
            elif sched.startswith("weekly@"):
                parts = sched.split("@")  # ["weekly", "friday", "17:00"]
                if len(parts) == 3:
                    day_name, time_str = parts[1].lower(), parts[2]
                    day_scheduler = getattr(schedule.every(), day_name, None)
                    if day_scheduler:
                        day_scheduler.at(time_str).do(fn).tag(f"dynamic:{name}")
    except Exception:
        pass


def start_proactive_scheduler(hud_queue=None):
    """Start all proactive reminders. Call once on bot startup."""
    global _hud_queue
    _hud_queue = hud_queue

    # Hardcoded system tasks
    schedule.every(30).minutes.do(_check_upcoming_events)
    schedule.every().day.at("09:00").do(_surface_news)
    schedule.every().day.at("12:00").do(_midday_check)
    schedule.every().day.at("19:00").do(_evening_check)
    schedule.every(3).hours.do(_focus_nudge)
    schedule.every(8).hours.do(_competitor_scan)

    # User-registered dynamic tasks from SQLite
    _register_dynamic_tasks()
    # Re-sync dynamic tasks every hour in case new ones were added at runtime
    schedule.every().hour.do(_register_dynamic_tasks)

    def run():
        while True:
            try:
                from obs.log import heartbeat
                heartbeat("scheduler")
            except Exception:
                pass
            try:
                from brain.presence import auto_update_away
                auto_update_away()  # presence-based away-mode
            except Exception:
                pass
            schedule.run_pending()
            time.sleep(60)

    threading.Thread(target=run, daemon=True).start()
