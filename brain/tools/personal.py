"""Personal life tools — health, finance, books, relationships, learning."""
from brain.tools.registry import tool


@tool(
    description="Log a health or fitness metric — workout, weight, sleep, steps, meal, heart rate, etc.",
    parameters={"type": {"type": "string", "description": "workout | weight | sleep | steps | meal | water | hr | bench | squat | etc."}, "value": {"type": "number", "description": "Numeric value"}, "unit": {"type": "string", "description": "Unit (lbs, hours, steps, reps, kcal, etc.)"}, "notes": {"type": "string"}, "date_str": {"type": "string", "description": "YYYY-MM-DD"}}
)
def log_health(type: str, value: float, unit: str = "", notes: str = "", date_str: str = "") -> str:
    from control.life_os import tool_log_health
    return tool_log_health(type, value, unit, notes, date_str)


@tool(
    description="Show health data summary for the past N days. Can filter by type.",
    parameters={"type": {"type": "string", "description": "Filter by type (optional)"}, "days": {"type": "integer", "description": "Days to look back (default: 7)"}}
)
def health_summary(type: str = "", days: int = 7) -> str:
    from control.life_os import tool_health_summary
    return tool_health_summary(type, days)


@tool(
    description="Log a personal expense (separate from business expenses).",
    parameters={"amount": {"type": "number"}, "category": {"type": "string", "description": "food | transport | entertainment | shopping | subscriptions | etc."}, "notes": {"type": "string"}, "date_str": {"type": "string"}}
)
def log_personal_expense(amount: float, category: str = "", notes: str = "", date_str: str = "") -> str:
    from control.life_os import tool_log_personal_expense
    return tool_log_personal_expense(amount, category, notes, date_str)


@tool(
    description="Log personal income (job, freelance, family, etc.).",
    parameters={"amount": {"type": "number"}, "category": {"type": "string"}, "notes": {"type": "string"}, "date_str": {"type": "string"}}
)
def log_personal_income(amount: float, category: str = "", notes: str = "", date_str: str = "") -> str:
    from control.life_os import tool_log_personal_income
    return tool_log_personal_income(amount, category, notes, date_str)


@tool(
    description="Show personal income vs expenses breakdown.",
    parameters={"period": {"type": "string", "description": "month | year | all"}}
)
def personal_finance_summary(period: str = "month") -> str:
    from control.life_os import tool_personal_finance_summary
    return tool_personal_finance_summary(period)


@tool(
    description="Add a book to the reading list.",
    parameters={"title": {"type": "string"}, "author": {"type": "string"}, "status": {"type": "string", "description": "want | reading | done"}, "notes": {"type": "string"}}
)
def add_book(title: str, author: str = "", status: str = "want", notes: str = "") -> str:
    from control.life_os import tool_add_book
    return tool_add_book(title, author, status, notes)


@tool(
    description="Update reading status or rating for a book.",
    parameters={"title": {"type": "string", "description": "Book title (partial match)"}, "status": {"type": "string", "description": "want | reading | done | dropped"}, "rating": {"type": "integer", "description": "Rating out of 5"}, "notes": {"type": "string"}}
)
def update_book(title: str, status: str, rating: int = None, notes: str = "") -> str:
    from control.life_os import tool_update_book
    return tool_update_book(title, status, rating, notes)


@tool(
    description="Show the reading list — currently reading, want to read, finished.",
    parameters={"status": {"type": "string", "description": "Filter: want | reading | done (optional)"}}
)
def reading_list(status: str = "") -> str:
    from control.life_os import tool_reading_list
    return tool_reading_list(status)


@tool(
    description="Save an important date — birthday, anniversary, deadline. JARVIS alerts 3 days before.",
    parameters={"person": {"type": "string"}, "event_type": {"type": "string", "description": "birthday | anniversary | deadline | other"}, "date_str": {"type": "string", "description": "YYYY-MM-DD"}, "notes": {"type": "string"}}
)
def add_important_date(person: str, event_type: str, date_str: str, notes: str = "") -> str:
    from control.life_os import tool_add_important_date
    return tool_add_important_date(person, event_type, date_str, notes)


@tool(
    description="Show upcoming important dates — birthdays, anniversaries, deadlines.",
    parameters={"days": {"type": "integer", "description": "Days ahead to check (default: 30)"}}
)
def upcoming_dates(days: int = 30) -> str:
    from control.life_os import tool_upcoming_dates
    return tool_upcoming_dates(days)


@tool(
    description="Log a conversation or interaction with someone important to you.",
    parameters={"person": {"type": "string"}, "notes": {"type": "string", "description": "What was discussed or how they're doing"}, "date_str": {"type": "string"}}
)
def log_relationship(person: str, notes: str, date_str: str = "") -> str:
    from control.life_os import tool_log_relationship
    return tool_log_relationship(person, notes, date_str)


@tool(
    description="Log a learning session — book, course, skill practice, video, etc.",
    parameters={"skill": {"type": "string", "description": "Skill or subject area"}, "type": {"type": "string", "description": "session | book | course | video | practice"}, "title": {"type": "string", "description": "Title of what you studied"}, "notes": {"type": "string", "description": "Key takeaways or progress"}}
)
def log_learning(skill: str, type: str = "session", title: str = "", notes: str = "") -> str:
    from control.life_os import tool_log_learning
    return tool_log_learning(skill, type, title, notes)


@tool(
    description="Show learning activity for the past N days.",
    parameters={"days": {"type": "integer", "description": "Days to look back (default: 7)"}}
)
def learning_summary(days: int = 7) -> str:
    from control.life_os import tool_learning_summary
    return tool_learning_summary(days)
