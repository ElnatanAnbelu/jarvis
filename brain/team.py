"""
Work Together mode — all four agents tackle a task independently.
FRIDAY → VERONICA → KAREN → JARVIS in sequence.
Each reports in their own voice. JARVIS closes with final strategy.
"""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def _load_env():
    env = Path(__file__).parent.parent / ".env"
    for line in env.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            if v.strip() and k.strip() not in os.environ:
                os.environ[k.strip()] = v.strip()

_load_env()


_WORK_TOGETHER_TRIGGERS = [
    "work together", "all agents", "everyone on this", "all hands",
    "get the team", "full team", "team mode", "bring everyone in",
    "all four", "team up",
    "all of you", "each of you", "you guys", "you all",
    "everyone weigh in", "all respond", "team respond",
    "individually", "each agent", "every agent",
    "what do you all", "what do you guys", "tell me what you all",
]


def is_work_together(text: str) -> bool:
    lower = text.lower()
    return any(t in lower for t in _WORK_TOGETHER_TRIGGERS)


def _strip_trigger(text: str) -> str:
    """Remove the 'work together on' prefix to get the actual task."""
    lower = text.lower()
    for t in sorted(_WORK_TOGETHER_TRIGGERS, key=len, reverse=True):
        if t in lower:
            idx = lower.index(t)
            after = text[idx + len(t):].strip(" :,on").strip()
            return after if len(after) > 4 else text
    return text


def _jarvis_assign(task: str) -> dict:
    """Ask JARVIS Haiku to split the task into agent-specific sub-tasks."""
    try:
        import os as _os, anthropic
        api_key = (
            _os.environ.get("ANTHROPIC_API_KEY", "").strip() or
            _os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
        )
        if not api_key:
            return {}
        client = anthropic.Anthropic(api_key=api_key)
        prompt = f"""Task: {task}

Break this into 4 focused sub-tasks, one per agent. Be specific about what each agent should contribute.
FRIDAY: (data, timing, quick facts, efficiency angles)
VERONICA: (risks, structure, weaknesses, what could go wrong)
KAREN: (human angle, readiness, confidence, personal considerations)
JARVIS: (final strategy, decision, recommendation, execution plan)

Output ONLY 4 lines in this exact format:
FRIDAY: [their specific task]
VERONICA: [their specific task]
KAREN: [their specific task]
JARVIS: [their specific task]"""

        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        lines = msg.content[0].text.strip().splitlines()
        assignments = {}
        for line in lines:
            for agent in ("FRIDAY", "VERONICA", "KAREN", "JARVIS"):
                if line.strip().upper().startswith(agent + ":"):
                    assignments[agent] = line.split(":", 1)[1].strip()
                    break
        return assignments
    except Exception:
        return {}


def work_together(task: str):
    """
    Generator. Yields ('agent', name), ('chunk', text), ('done', full) events
    for each agent in sequence: FRIDAY → VERONICA → KAREN → JARVIS.
    """
    from brain.free_agents import think_veronica_agent, think_karen_agent
    from brain.gemini import think_friday
    from brain.think import think as think_jarvis
    from memory.memory import save_message

    actual_task = _strip_trigger(task)
    save_message("user", task)

    assignments = _jarvis_assign(actual_task)

    agents = [
        ("FRIDAY",   assignments.get("FRIDAY",   f"Give quick data, timing, and efficiency facts about: {actual_task}")),
        ("VERONICA", assignments.get("VERONICA", f"Assess the risks and structural weaknesses of: {actual_task}")),
        ("KAREN",    assignments.get("KAREN",    f"Cover the human angle, readiness, and personal considerations for: {actual_task}")),
        ("JARVIS",   assignments.get("JARVIS",   f"Give the final strategy, decision, and execution plan for: {actual_task}")),
    ]

    for agent_name, sub_task in agents:
        yield ("agent", agent_name)

        if agent_name == "FRIDAY":
            response = think_friday(sub_task) or ""
        elif agent_name == "VERONICA":
            response = think_veronica_agent(sub_task) or ""
        elif agent_name == "KAREN":
            response = think_karen_agent(sub_task) or ""
        else:  # JARVIS
            response = think_jarvis(sub_task, model="claude-sonnet-4-6") or ""

        if not response:
            response = f"No response from {agent_name}."

        save_message(agent_name.lower(), response)
        yield ("chunk", response)
        yield ("done_agent", agent_name)

    yield ("all_done", "")
