# JARVIS Upgrade — What We're Doing & Where We Are

## The Short Version

We're making two types of improvements to JARVIS:

1. **Safety fixes** — plugging two security holes that could let JARVIS accidentally do something destructive if it misunderstands a request or if something tricks it
2. **Code cleanup** — breaking one giant messy file (`brain/tools.py`, ~94KB) into smaller focused files so it's easier to work with, test, and grow

Neither of these changes what JARVIS *does*. It will work exactly the same — just safer and easier to maintain.

---

## Why It Matters (Plain English)

### The Two Security Problems

**Problem 1 — Shell injection**
When JARVIS runs a terminal command for you (like `ls`, `git status`, etc.), it passes the command directly to the shell. That means if a command ever included a `;` or `&&`, the shell would treat what comes after as a *second* command and run that too. Example: `ls /tmp; rm -rf ~/Documents` would delete your Documents folder. We're fixing this so those special characters are treated as literal text, not operators.

**Problem 2 — Computer control with no guardrails**
When JARVIS controls your screen (takes a screenshot, figures out what to click), it gets its instructions from Claude. But if something on your screen — like a webpage or email — contains text that *looks like an instruction*, Claude might follow it. There's also no warning before JARVIS presses a keyboard shortcut that could quit an app or delete something. We're adding:
- An approved list of actions (if Claude returns something not on the list, JARVIS refuses)
- A "are you sure?" confirmation before any destructive key combo

### The Code Cleanup

`brain/tools.py` is one file that contains the logic for 100+ tools. It's 2,232 lines long. Every time we want to add or change a tool, we edit the same massive file — hard to read, hard to test, easy to break something unrelated. We're splitting it into 11 smaller files, one per category (messaging, calendar, files, etc.). Same result, much cleaner.

---

## Progress Tracker

### Phase 1 — Security Fixes

| # | Task | Status | What it does |
|---|------|--------|-------------|
| 1 | Fix shell command runner | ✅ Done | Stop `;` and `&&` from chaining unintended commands |
| 2 | Add computer action allowlist | ✅ Done | Only approved mouse/keyboard actions allowed |
| 3 | Add confirmation for dangerous keys | ✅ Done | Ask before pressing cmd+Q, cmd+delete, etc. |

### Phase 2 — Tools Cleanup

| # | Task | Status | What it does |
|---|------|--------|-------------|
| 4 | Build the tool registry | ✅ Done | New system for defining tools — cleaner, testable |
| 5 | Create the package entry point | ✅ Done | Wire everything together so nothing else needs to change |
| 6 | Messaging tools | ✅ Done | Move email, iMessage, WhatsApp to their own file |
| 7 | System tools | ✅ Done | Move app launching, volume, screenshot, focus mode |
| 8 | Web tools | ✅ Done | Move search, news, weather, browser |
| 9 | Calendar tools | ⬜ Not started | Move tasks, events, reminders, briefing |
| 10 | File tools | ⬜ Not started | Move read/write/delete/move file operations |
| 11 | Code & dev tools | ⬜ Not started | Move shell runner, git commands, code execution |
| 12 | Data tools | ⬜ Not started | Move charts, reports, data analysis |
| 13 | Memory tools | ⬜ Not started | Move remember, goals, habits |
| 14 | Business tools | ⬜ Not started | Move Nexel CRM, financials, marketing |
| 15 | Personal tools | ⬜ Not started | Move health, books, relationships, learning |
| 16 | Strategy tools | ⬜ Not started | Move decisions, proactive scan, strategy |
| 17 | Final wiring & cleanup | ⬜ Not started | Verify everything works, delete old file |

---

## Status Key

| Symbol | Meaning |
|--------|---------|
| ⬜ | Not started |
| 🔄 | In progress |
| ✅ | Done |
| ❌ | Blocked / needs attention |

---

## Summary

> *This section will be filled in when all tasks are complete.*

---

*Last updated: 2026-05-23*
