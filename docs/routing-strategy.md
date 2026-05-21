# JARVIS Routing & Token Strategy

## Core Rule
JARVIS responds to everything by default. His voice (Paul Bettany clone) is the default voice for all interactions. FRIDAY, VERONICA, and KAREN only activate when explicitly called by name.

## JARVIS Tier System
| Score | Task Type | Model | Speed |
|-------|-----------|-------|-------|
| 1–3 | Casual chat, greetings, quick questions, simple facts | claude-haiku-4-5-20251001 | Fast |
| 4 | Medium complexity — tools, planning, multi-step | claude-sonnet-4-6 | Medium |
| 5 | Deep strategy, life decisions, complex reasoning | claude-opus-4-7 | Slow (rare) |

Scoring is done by Groq llama-3.1-8b-instant (near-instant, free).

## Free Agents (by name only)
| Agent | Voice | Model | Personality |
|-------|-------|-------|-------------|
| FRIDAY | Kerry Condon clone | Gemini 2.0 Flash | Quick, Irish, casual responder |
| VERONICA | — | Groq llama-3.3-70b | Clinical, blunt, heavy-duty specialist |
| KAREN | Jennifer Connelly clone | Mistral / Groq llama-3.3-70b | Warm, human, emotional support |

Gemini 2.0 Flash is comparable to Sonnet in intelligence — FRIDAY can handle score 1–4 queries if called directly.

## Token Rules
- History window: last 10 messages only
- Max tokens per response: 1024 (JARVIS), 512 (agents)
- **Sonnet and Opus NEVER handle easy tasks** — score is the only gate, no artificial bumping
- Opus triggers at score 5 only — deep strategy, business decisions, life planning
- Sonnet triggers at score 4 only — medium complexity, multi-step, nuanced reasoning
- Haiku handles score 1-3 — including simple tool calls like timers, weather, quick searches

## Voice
- Every text reply triggers voice automatically (browser calls /api/tts after done event)
- TTS priority: Chatterbox clone daemon → Kokoro preset → ElevenLabs → edge-tts
- JARVIS = Paul Bettany reference audio
- FRIDAY = Kerry Condon reference audio  
- KAREN = Jennifer Connelly reference audio
- VERONICA = FRIDAY reference audio (fallback, no MCU source)
