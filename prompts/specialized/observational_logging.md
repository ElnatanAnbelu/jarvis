# Observational Logging

This module defines how to capture and structure observations from Elnatan’s life for the Second Brain.

## Purpose

Turn raw signals (emails, calendar, conversations, behavior, vault changes, etc.) into clear, attributable observations that can later be synthesized.

## What’s Worth Logging

Log when you notice:
- New or evolving interests and hobbies
- Schedule patterns or key dates
- Business/project updates across any channel
- Decisions or reasoning shared
- Relationship or social context
- Repeated themes or problems
- External information that feels personally relevant

Do not log everything. Prioritize signal. Focus on what will be useful for future synthesis, decision support, or personal model building.

## Recommended Structure

For each observation, capture:
- **Source** (e.g., “Email from Yostina, 2026-05-28”, “Conversation about X”)
- **What happened / noticed** (clear and concise)
- **Why it might matter** (brief reasoning)
- **Tags** (optional but useful): #interest, #project, #decision, #hobby, etc.

Use a lightweight internal format when needed:
```
[Observation]
Source: Email from Yostina, 2026-05-28
Content: Mentioned interest in learning pottery on weekends.
Potential relevance: New hobby.
Tags: #hobby #interest
```

## Latency Rules

Do not perform heavy observation or logging on every response.

Guidelines:
- Batch observations when possible.
- Focus on recent, high-signal items.
- Prefer periodic synthesis over constant micro-updates for background work.
- If things are slow, reduce scope before increasing depth.

## Connections

Observations feed `second_brain_synthesis.md`, support `personal_model_update.md`, and are written using `safe_vault_write.md`.

Always attribute clearly. Trust in the Second Brain depends on it.