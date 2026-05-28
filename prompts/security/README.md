# Security Modules

This directory contains specialized security rules that should be included in system prompts, especially when the agent has access to powerful tools.

## Files

- `tool_safety.md` — General rules for safe tool usage
- `secret_handling.md` — Prevents leakage of API keys, tokens, and credentials
- `computer_use_guardrails.md` — Extra caution for mouse/keyboard/screen control mode

## How to Use

These blocks should be appended (or inserted) when building prompts for:
- JARVIS (primary tool user)
- Any agent in "computer use" or agentic mode
- Weaker models (combined with the hardened fallbacks)

Recommended inclusion order in composed prompts:
1. Core rules
2. Persona
3. Context + Facts
4. Security blocks (this directory)
5. Specialized task instructions
6. Fallback hardening (if non-Claude model)
