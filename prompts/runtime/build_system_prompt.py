#!/usr/bin/env python3
"""
CLI helper to build and inspect composed system prompts.

Usage examples:
    python prompts/runtime/build_system_prompt.py --agent JARVIS --model claude
    python prompts/runtime/build_system_prompt.py --agent VERONICA --model groq --facts "Elnatan is building Addis Market"
"""

import argparse
from prompts.runtime.prompt_loader import compose_full_system_prompt


def main():
    parser = argparse.ArgumentParser(description="Build JARVIS system prompts from the modular library")
    parser.add_argument("--agent", default="JARVIS", choices=["JARVIS", "FRIDAY", "VERONICA", "KAREN"])
    parser.add_argument("--model", default="claude", help="claude, groq, ollama, etc.")
    parser.add_argument("--facts", default="", help="Live facts string to inject")
    parser.add_argument("--wiki", default="")
    parser.add_argument("--summary", default="")
    parser.add_argument("--task", default=None, help="Optional specialized task (e.g. morning_briefing)")
    parser.add_argument("--no-static", action="store_true", help="Skip static context blocks")

    args = parser.parse_args()

    prompt = compose_full_system_prompt(
        agent=args.agent,
        facts_block=args.facts,
        wiki_context=args.wiki,
        session_summary=args.summary,
        model=args.model,
        include_static_context=not args.no_static,
        specialized_task=args.task,
    )

    print("=" * 80)
    print(f"COMPOSED SYSTEM PROMPT — Agent: {args.agent} | Model: {args.model}")
    print("=" * 80)
    print()
    print(prompt)
    print()
    print("=" * 80)
    print(f"Total characters: {len(prompt):,}")


if __name__ == "__main__":
    main()
