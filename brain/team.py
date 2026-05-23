"""
Work Together mode — all four agents tackle a task with a shared blackboard.
FRIDAY → VERONICA → KAREN each write to the blackboard.
JARVIS reads all three before synthesizing the final strategy.
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
        import anthropic
        api_key = (
            os.environ.get("ANTHROPIC_API_KEY", "").strip() or
            os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
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
    Generator. Yields ('agent', name), ('chunk', text), ('done_agent', name) events.

    Blackboard protocol:
      FRIDAY, VERONICA, KAREN each run first and write to shared_context.
      JARVIS receives the full blackboard and synthesizes a final strategy.
      No agent is blind to what the others said.
    """
    from brain.gemini import think_friday_stream
    from brain.free_agents import think_veronica_stream, think_karen_stream
    from brain.think import think as think_jarvis
    from memory.memory import save_message

    actual_task = _strip_trigger(task)
    save_message("user", task)

    assignments = _jarvis_assign(actual_task)

    # ── Phase 1: FRIDAY, VERONICA, KAREN stream to blackboard ─────────────────
    blackboard = {}

    supporting_agents = [
        ("FRIDAY",   assignments.get("FRIDAY",   "Give quick data, timing, and efficiency facts about: " + actual_task), think_friday_stream),
        ("VERONICA", assignments.get("VERONICA", "Assess the risks and structural weaknesses of: " + actual_task), think_veronica_stream),
        ("KAREN",    assignments.get("KAREN",    "Cover the human angle, readiness, and personal considerations for: " + actual_task), think_karen_stream),
    ]

    for agent_name, sub_task, stream_fn in supporting_agents:
        yield ("agent", agent_name)
        chunks = []
        try:
            for chunk in stream_fn(sub_task):
                chunks.append(chunk)
                yield ("chunk", chunk)
        except Exception:
            pass
        response = "".join(chunks).strip() or ("No response from " + agent_name + ".")
        blackboard[agent_name] = response
        save_message(agent_name.lower(), response)
        yield ("done_agent", agent_name)

    # ── Phase 2: JARVIS reads full blackboard then synthesizes ─────────────────
    yield ("agent", "JARVIS")

    blackboard_text = "\n\n".join(
        f"[{name}]\n{content}" for name, content in blackboard.items()
    )

    jarvis_prompt = (
        f"{assignments.get('JARVIS', f'Final strategy and execution plan for: {actual_task}')}\n\n"
        f"Your team has weighed in. Read their analysis. Do not repeat what they said — "
        f"build on it and deliver the final call in your voice: composed, direct, dry British wit if it fits. "
        f"One clear recommendation. No hedging. No committee language. "
        f"You are the system that synthesizes and decides — act like it.\n\n"
        f"TEAM BLACKBOARD:\n{blackboard_text}"
    )

    jarvis_response = think_jarvis(jarvis_prompt, model="claude-sonnet-4-6") or "No response."
    save_message("jarvis", jarvis_response)
    yield ("chunk", jarvis_response)
    yield ("done_agent", "JARVIS")
    yield ("all_done", "")
