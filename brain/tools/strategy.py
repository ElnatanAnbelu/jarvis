"""Strategy tools — proactive scans, weekly check-ins, decision tracking."""
from brain.tools.registry import tool


@tool(
    description="Scan the web for news and intel relevant to Elnatan's businesses and interests — Ethiopian e-commerce, competitors, market moves.",
    parameters={"topics": {"type": "array", "items": {"type": "string"}, "description": "Custom topics to scan (optional — uses defaults if omitted)"}}
)
def proactive_scan(topics: list = None) -> str:
    from control.intel import proactive_scan as _run
    return _run(topics)


@tool(
    description="Full weekly strategic review — pulls all business data, life OS, patterns, and market intel. Use every Monday or when asked for a weekly check-in.",
    parameters={}
)
def weekly_strategy_checkin() -> str:
    from control.intel import weekly_strategy_checkin as _run
    return _run()


@tool(
    description="Build a structured decision framework for a hard choice. Options, pros/cons, risks, JARVIS recommendation.",
    parameters={"question": {"type": "string", "description": "The decision to make"}, "context": {"type": "string", "description": "Relevant context"}, "options": {"type": "string", "description": "Options being considered (optional)"}}
)
def decision_framework(question: str, context: str = "", options: str = "") -> str:
    from control.life_os import tool_decision_framework
    return tool_decision_framework(question, context, options)


@tool(
    description="Record a decision that was made — for tracking and learning over time.",
    parameters={"question": {"type": "string"}, "chosen": {"type": "string", "description": "What was decided"}, "reasoning": {"type": "string", "description": "Why this was chosen"}}
)
def log_decision(question: str, chosen: str, reasoning: str = "") -> str:
    from control.life_os import tool_log_decision
    return tool_log_decision(question, chosen, reasoning)


@tool(
    description="Record the outcome of a past decision — what happened after you made that call.",
    parameters={"question": {"type": "string", "description": "The original question (partial match)"}, "outcome": {"type": "string", "description": "What actually happened"}}
)
def resolve_decision(question: str, outcome: str) -> str:
    from control.life_os import tool_resolve_decision
    return tool_resolve_decision(question, outcome)


@tool(
    description="Show all logged decisions and their outcomes.",
    parameters={}
)
def decision_history() -> str:
    from control.life_os import tool_decision_history
    return tool_decision_history()
