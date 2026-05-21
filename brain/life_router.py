"""
Natural language interface for JARVIS life management.
Parses user input and calls the correct life.py function.
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.life import (
    add_goal, get_goals, complete_goal,
    add_habit, check_habit, get_habits,
    add_person, get_person, log_contact,
    add_task, get_tasks, complete_task,
    log_expense, get_spending_summary,
    morning_briefing,
)

LIFE_KEYWORDS = [
    # Tasks
    "add task", "new task", "remind me to", "i need to",
    "my tasks", "what are my tasks", "show my tasks", "pending tasks",
    "done with", "finished", "completed task", "mark done",
    # Goals
    "add goal", "new goal", "my goals", "show goals", "what are my goals",
    "goal complete", "achieved my goal",
    # Habits
    "add habit", "track habit", "my habits", "check habit", "did my",
    "habit check", "show habits",
    # People
    "remember that", "who is", "tell me about", "add person", "log contact",
    # Expenses
    "log expense", "spent", "i bought", "show spending", "how much have i spent",
    # Briefing
    "morning briefing", "daily briefing", "what's on my plate",
]


def is_life_command(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in LIFE_KEYWORDS)


def handle_life(text: str) -> str:
    lower = text.lower()

    # ── TASKS ──────────────────────────────────────────────────────────
    if any(kw in lower for kw in ["add task", "new task", "remind me to", "i need to"]):
        title = re.sub(r"(add task|new task|remind me to|i need to)", "", text, flags=re.IGNORECASE).strip(" :.")
        if title:
            # Check for priority hint
            priority = "high" if any(w in lower for w in ["urgent", "asap", "important", "high"]) else "medium"
            due_match = re.search(r"(?:by|due|on)\s+(.+)", text, re.IGNORECASE)
            due = due_match.group(1).strip() if due_match else None
            return add_task(title, priority=priority, due_date=due)
        return "What task should I add?"

    if any(kw in lower for kw in ["my tasks", "what are my tasks", "show my tasks", "pending tasks"]):
        return get_tasks()

    if any(kw in lower for kw in ["done with", "finished", "completed task", "mark done"]):
        title = re.sub(r"(done with|finished|completed task|mark done|task)", "", text, flags=re.IGNORECASE).strip(" :.")
        return complete_task(title) if title else "Which task is done?"

    # ── GOALS ──────────────────────────────────────────────────────────
    if any(kw in lower for kw in ["add goal", "new goal"]):
        title = re.sub(r"(add goal|new goal)", "", text, flags=re.IGNORECASE).strip(" :.")
        cat_match = re.search(r"\b(business|personal|fitness|health|finance|education)\b", lower)
        category = cat_match.group(1) if cat_match else "personal"
        return add_goal(title, category=category) if title else "What's the goal?"

    if any(kw in lower for kw in ["my goals", "show goals", "what are my goals"]):
        return get_goals()

    if any(kw in lower for kw in ["goal complete", "achieved my goal"]):
        title = re.sub(r"(goal complete|achieved my goal|goal)", "", text, flags=re.IGNORECASE).strip()
        return complete_goal(title) if title else "Which goal did you complete?"

    # ── HABITS ─────────────────────────────────────────────────────────
    if any(kw in lower for kw in ["add habit", "track habit"]):
        name = re.sub(r"(add habit|track habit)", "", text, flags=re.IGNORECASE).strip(" :.")
        return add_habit(name) if name else "What habit should I track?"

    if any(kw in lower for kw in ["my habits", "show habits"]):
        return get_habits()

    if any(kw in lower for kw in ["check habit", "did my", "habit check"]):
        name = re.sub(r"(check habit|did my|habit check)", "", text, flags=re.IGNORECASE).strip()
        return check_habit(name) if name else get_habits()

    # ── PEOPLE ─────────────────────────────────────────────────────────
    if "who is" in lower or "tell me about" in lower:
        name = re.sub(r"(who is|tell me about)", "", text, flags=re.IGNORECASE).strip(" ?.")
        return get_person(name) if name else "Who do you mean?"

    if "remember that" in lower:
        # "remember that John is my investor from Kenya"
        name_match = re.search(r"remember that\s+(\w+)\s+is\s+(.+)", text, re.IGNORECASE)
        if name_match:
            name = name_match.group(1)
            notes = name_match.group(2).strip()
            return add_person(name, notes=notes)
        return "Tell me: remember that [name] is [description]"

    if "log contact" in lower:
        name = re.sub(r"log contact", "", text, flags=re.IGNORECASE).strip()
        return log_contact(name) if name else "Who did you contact?"

    # ── EXPENSES ───────────────────────────────────────────────────────
    if any(kw in lower for kw in ["log expense", "spent", "i bought"]):
        amount_match = re.search(r"\$?([\d.]+)", text)
        if amount_match:
            amount = float(amount_match.group(1))
            cat_match = re.search(r"(?:on|for)\s+([a-zA-Z\s]+?)(?:\s*$)", text, re.IGNORECASE)
            category = cat_match.group(1).strip() if cat_match else "misc"
            return log_expense(amount, category)
        return "How much did you spend, and on what?"

    if any(kw in lower for kw in ["show spending", "how much have i spent", "spending summary"]):
        return get_spending_summary()

    # ── BRIEFING ───────────────────────────────────────────────────────
    if any(kw in lower for kw in ["morning briefing", "daily briefing", "what's on my plate"]):
        return morning_briefing()

    return None
