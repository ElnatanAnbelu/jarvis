"""Memory tools — remember facts, search history, goals, habits."""
from brain.tools.registry import tool


@tool(
    description="Save an important fact about Elnatan — phone numbers, preferences, schedules, anything he tells you to remember.",
    parameters={
        "category": {"type": "string", "description": "Category like 'contact', 'preference', 'schedule', 'goal'"},
        "key":      {"type": "string", "description": "Short label, e.g. 'Mom phone', 'wake up time'"},
        "value":    {"type": "string", "description": "The value to remember"},
    }
)
def remember(category: str, key: str, value: str) -> str:
    from memory.memory import save_fact
    save_fact(category, key, value)
    return f"Remembered: [{category}] {key} = {value}"


@tool(
    description="Search all past conversations for any topic, person, or event. Use when asked 'what did we discuss about X?', 'when did I mention Y?', 'what was that thing about Z?'",
    parameters={
        "query":     {"type": "string", "description": "What to search for"},
        "limit":     {"type": "integer", "description": "Max results (default: 10)"},
        "days_back": {"type": "integer", "description": "Limit to past N days (0 = all time)"},
    }
)
def search_memory(query: str, limit: int = 10, days_back: int = 0) -> str:
    from control.intel import search_memory as _run
    return _run(query, limit, days_back)


@tool(
    description="Show how a topic evolved over time in conversation history.",
    parameters={
        "topic": {"type": "string", "description": "Topic to trace over time"},
        "days":  {"type": "integer", "description": "How many days back to look (default: 30)"},
    }
)
def memory_timeline(topic: str, days: int = 30) -> str:
    from control.intel import memory_timeline as _run
    return _run(topic, days)


@tool(
    description="Analyze conversation patterns to detect focus areas, procrastination signals, silent days, and topic distribution.",
    parameters={
        "days": {"type": "integer", "description": "Days to analyze (default: 30)"},
    }
)
def analyze_patterns(days: int = 30) -> str:
    from control.intel import analyze_patterns as _run
    return _run(days)


@tool(
    description="Add a new long-term goal",
    parameters={
        "title":    {"type": "string", "description": "The goal"},
        "category": {"type": "string", "description": "Category e.g. business, health, personal"},
    }
)
def add_goal(title: str, category: str = "general") -> str:
    from memory.goals import add_goal as _run
    return _run(title, category)


@tool(
    description="Get all active goals",
    parameters={}
)
def get_goals() -> str:
    from memory.goals import get_goals as _run
    return _run()


@tool(
    description="Add a new daily habit to track",
    parameters={
        "title": {"type": "string", "description": "The habit to track daily"},
    }
)
def add_habit(title: str) -> str:
    from memory.goals import add_habit as _run
    return _run(title)


@tool(
    description="Mark a habit as done for today",
    parameters={
        "title": {"type": "string", "description": "The habit to mark complete"},
    }
)
def check_habit(title: str) -> str:
    from memory.goals import check_habit as _run
    return _run(title)


@tool(
    description="Get today's habit completion status",
    parameters={}
)
def get_habits() -> str:
    from memory.goals import get_habits_status
    return get_habits_status()
