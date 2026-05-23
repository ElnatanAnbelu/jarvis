"""Calendar tools — tasks, events, reminders, briefing."""
import subprocess
from brain.tools.registry import tool


@tool(
    description="Add a task or reminder to the task list",
    parameters={
        "title":    {"type": "string", "description": "Task title"},
        "priority": {"type": "string", "description": "Task priority: high, medium, or low"},
    }
)
def add_task(title: str, priority: str = "medium") -> str:
    from memory.life import add_task as _add
    return _add(title, priority=priority)


@tool(
    description="Get all pending tasks",
    parameters={}
)
def get_tasks() -> str:
    from memory.life import get_tasks as _get
    return _get()


@tool(
    description="Check calendar events for today or a specific date",
    parameters={
        "date": {"type": "string", "description": "Date to check in YYYY-MM-DD format. Leave empty for today."},
    }
)
def check_calendar(date: str = "") -> str:
    from control.calendar import get_events_str
    from datetime import date as date_type
    d = None
    if date:
        try:
            d = date_type.fromisoformat(date)
        except Exception:
            pass
    return get_events_str(d)


@tool(
    description="Create an event in Apple Calendar",
    parameters={
        "title":            {"type": "string", "description": "Event title"},
        "date":             {"type": "string", "description": "Date in YYYY-MM-DD format"},
        "time":             {"type": "string", "description": "Time in HH:MM 24h format, e.g. 14:30"},
        "duration_minutes": {"type": "integer", "description": "Duration in minutes (default 60)"},
    }
)
def create_calendar_event(title: str, date: str, time: str, duration_minutes: int = 60) -> str:
    from datetime import datetime, timedelta
    title = title.replace('"', "'")
    start_dt = datetime.fromisoformat(f"{date}T{time}:00")
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    start_apple = start_dt.strftime("%B %d, %Y at %I:%M %p")
    end_apple = end_dt.strftime("%B %d, %Y at %I:%M %p")
    script = f'''tell application "Calendar"
    tell calendar "Home"
        make new event with properties {{summary:"{title}", start date:date "{start_apple}", end date:date "{end_apple}"}}
    end tell
end tell'''
    subprocess.run(["osascript", "-e", script], timeout=6)
    return f"Event created: {title} on {date} at {time}"


@tool(
    description="Set a reminder to notify at a specific time with a message",
    parameters={
        "message": {"type": "string", "description": "What to remind about"},
        "minutes": {"type": "integer", "description": "Minutes from now to trigger the reminder"},
    }
)
def set_reminder(message: str, minutes: int = 5) -> str:
    import threading
    mins = max(1, int(minutes))
    def _fire():
        subprocess.run([
            "osascript", "-e",
            f'display notification "{message}" with title "JARVIS REMINDER" sound name "Ping"'
        ])
    threading.Timer(mins * 60, _fire).start()
    return f"Reminder set for {mins} minute{'s' if mins != 1 else ''}: {message}"


@tool(
    description="Generate a morning briefing with real weather, calendar, tasks, and habits data. Use this whenever the user asks for a briefing, morning update, or daily summary.",
    parameters={}
)
def morning_briefing() -> str:
    from brain.briefing import generate_briefing
    return generate_briefing()
