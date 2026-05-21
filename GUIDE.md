# JARVIS Enhancement Guide
**From:** Kerod (via Citadel) | **Date:** 2026-05-11 | **For:** Elnatan

---

## Part 1 — Auth: One Bucket, Three Surfaces

**Core principle:** Use `CLAUDE_CODE_OAUTH_TOKEN` — same auth as Claude Code CLI, same Pro/Max subscription bucket.

**How to get the token:**
```bash
npm install -g @anthropic-ai/claude-code
claude setup-token   # opens browser, prints sk-ant-oat01-...
```

**Add to .env:**
```
CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-xxxxxxxx
# DO NOT also set ANTHROPIC_API_KEY — API key wins and you get billed separately
```

**SDK auth resolution order:**
`ANTHROPIC_API_KEY` → `CLAUDE_CODE_OAUTH_TOKEN` → `~/.claude/.credentials.json` → macOS Keychain

**Python hello-world:**
```python
import asyncio, os
from claude_agent_sdk import query, ClaudeAgentOptions

os.environ.pop("ANTHROPIC_API_KEY", None)  # ensure OAuth path wins

async def main():
    async for msg in query(
        prompt="Hello",
        options=ClaudeAgentOptions(model="claude-haiku-4-5"),
    ):
        print(msg)

asyncio.run(main())
```

**ToS caveat:** Using Agent SDK with subscription auth is against Anthropic's stated terms for third-party products. For personal/private use only — low risk. Don't redistribute. Open feature request: anthropics/claude-agent-sdk-python#559.

**Shared rate-limit:** Telegram + Web + Terminal all eat from the same Pro/Max 5-hour window.

---

## Part 2 — Telegram Surface (fastest win, ~30 min)

**Reference repo:** github.com/kerodkibatu/claudegram (Kerod will grant access)

**Architecture:**
- Single long-running TypeScript daemon
- Grammy bot framework + `@anthropic-ai/claude-agent-sdk`
- Per-chat message queue (sequentialize middleware)
- Per-chat conversation history (in-memory BoundedMap, max 1000 sessions)
- Persisted Claude SDK `session_ids` on disk (`claudegram.sessions.json`)
- On message: calls `query(...)` with `resume=<session_id>` so context survives restarts
- Voice notes: transcribed via local whisper.cpp → fed as text
- In-process MCP server exposes: `claudegram_extract_media`, `publish_privatebin`, `send_media`, `send_media_group`
- Responses >2500 chars or with markdown tables → auto-published to PrivateBin, user gets link

**Critical files:**
| File | What's in it |
|------|-------------|
| `src/claude/agent.ts` | SDK init + query() call, streaming, subagent routing |
| `src/claude/mcp-tools.ts` | In-process MCP server |
| `src/claude/session-manager.ts` | Session ID persistence + cross-restart resume |
| `src/bot/bot.ts` | Per-chat ordering, /cancel bypass |
| `src/bot/handlers/message.handler.ts` | Main message flow |
| `src/config.ts` | Zod-validated env schema |
| `scripts/claudegram-botctl.sh` | start/stop/restart/status |

**Non-obvious design decisions worth stealing:**
1. Per-chat queue + global cancel bypass — messages FIFO, /cancel jumps queue
2. Dual-layer streaming dedup — `mainTextStreamedViaDeltas` flag prevents posting same content twice
3. Subagent → separate Telegram message — watch tool calls without polluting main conversation
4. Unset `CLAUDECODE`, `CLAUDE_CODE_ENTRYPOINT`, `CLAUDE_CODE_SSE_PORT` at boot — prevents guard conflicts if launched inside a claude session
5. Watchdog on stuck queries — aborts if no activity for N seconds

**Migration path (if no existing bot):**
Fork Claudegram → change auth token → set `ALLOWED_USER_IDS` to your Telegram ID → `botctl.sh start`. Done in 30 minutes.

---

## Part 3 — Web Surface

**Stack:**
- Backend: FastAPI (Python) — async-first, `StreamingResponse` + `async for` maps onto SDK with zero glue
- Frontend: existing shell (HTMX + Alpine if starting fresh)
- Transport: **SSE, not WebSockets** — SSE is one-way (server→client), exactly what streaming needs. POST for prompts.
- Persistence: SQLite — `sessions(id, sdk_session_id, title, created_at)` + `messages(session_id, role, blocks_json, ts)`

**FastAPI streaming route:**
```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from claude_agent_sdk import (
    ClaudeSDKClient, ClaudeAgentOptions,
    AssistantMessage, ResultMessage, TextBlock, ToolUseBlock,
)
import json

app = FastAPI()
CLIENTS: dict[str, ClaudeSDKClient] = {}

def sse(event: str, data: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()

@app.post("/chat/{sid}")
async def chat(sid: str, body: dict):
    client = CLIENTS.get(sid)
    if client is None:
        opts = ClaudeAgentOptions(
            allowed_tools=["Read", "Write", "Bash"],
            mcp_servers={...},
            include_partial_messages=True,
            resume=body.get("resume"),
        )
        client = await ClaudeSDKClient(options=opts).__aenter__()
        CLIENTS[sid] = client
    await client.query(body["prompt"])

    async def stream():
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        yield sse("text", {"text": block.text})
                    elif isinstance(block, ToolUseBlock):
                        yield sse("tool_use", {"name": block.name, "input": block.input})
            elif isinstance(msg, ResultMessage):
                yield sse("done", {"session_id": msg.session_id, "cost_usd": msg.total_cost_usd})
                return
    return StreamingResponse(stream(), media_type="text/event-stream")
```

**Frontend (minimal):**
```javascript
const es = new EventSource(`/chat/${sid}`);
es.addEventListener("text",     e => append(JSON.parse(e.data).text));
es.addEventListener("tool_use", e => renderToolCard(JSON.parse(e.data)));
es.addEventListener("done",     e => es.close());
```

**Auth gate (ranked by least ops):**
1. Tailscale — bind backend to `100.x.x.x`, only your tailnet devices reach it. **Recommended default.**
2. Cloudflare Tunnel + Access — real domain (`jarvis.yourdomain.com`), browser SSO
3. Tailscale Funnel — public `.ts.net` URL with IdP gating
4. Magic link — ~50 LoC FastAPI

**Deployment:** Keep on your laptop. Backend + SDK + MCPs need filesystem + credential access. VPS = re-plumb everything.

**Reference implementations:**
- `anthropics/claude-agent-sdk-demos` — official, React + Express
- `ninehills/claude-agent-ui` — closest to "Jarvis on my laptop"
- `wbopan/cui` — parallel background sessions, push notifications
- `JimLiu/claude-agent-kit` — helper library for session/message handling

---

## Part 4 — Memory: The Real Compounding Asset

**Three layers:**
1. **Memory** (`_Memory/`) — durable facts, identity, people, decisions, projects. Prose wiki articles with `[[wikilinks]]`. Domains: `identity/`, `personal/`, `work/`, `preferences/`, `research/`, `active/`
2. **Projects** (`projects/personal/`, `projects/work/`) — code, workbenches, project-local task trackers. Isolated from memory.
3. **Logs** (`logs/YYYY-MM-DD.md`) — append-only chronological, `[HH:MM]` timestamped lines. Maintained by session-end hook.

**Why prose over bullets:** Bullets rot. Narrative paragraphs stay retrievable 6 months later. Each entity file:
- Narrative prose (durable facts, current status)
- `## Notes` (ephemeral details, dated bullets ok)
- `## See Also` (tangential wikilinks)

Wikilinks format: `[[_Memory/work/people/alice-smith|Alice]]`

**Memory agent — four modes (dedicated Sonnet subagent, NOT the main agent):**
- **STORE** — create/update entity files. Background-dispatched proactively (no asking permission)
- **RECALL** — overview → wikilinks → Grep fallback. Novel synthesis can be filed as new entity.
- **MAINTAIN** — prune resolved threads, rebuild overviews as prose, lint for contradictions/orphans
- **INGEST** — process external articles/transcripts/papers, ripple updates across entities

**Hooks:**
- `SessionStart`: `git pull --ff-only` (silent offline), load identity + preferences + overview. If memory empty → bootstrap mode (interview user, scaffold wiki).
- `Stop`: single Sonnet agent appends to today's log, updates active/ threads, commits, pushes. Multi-device sync free.

**Migration (if you already have memory):**
- Don't rewrite. Inventory what you have.
- Pick one high-value domain to migrate first (active work threads = easiest win)
- Convert links incrementally as you touch files
- Keep existing tool as reference layer — wiki system is additive

---

## Part 5 — Token Strategy

**Where Groq/Qwen still belongs (NOT the main brain):**
- Bulk reformatting / renaming (CSV→JSON, regex across N files)
- Embedding generation (use nomic-embed-text or bge-large locally)
- Local grep-with-judgment
- Low-stakes summarization
- Boilerplate scaffolding from function signature
- Commit message generation from a diff
- **Heuristic:** if a mistake costs <2 min to detect and fix, run local

**Where Claude earns its money:**
- Multi-step tool-use chains (>3 hops) — open models loop or hallucinate args
- Strict-spec code generation
- Multi-file refactors with cross-file invariants
- Agentic workflows (subagents, parallel dispatch, long-horizon planning)
- Hard bug root-causes
- If you've re-prompted Qwen 3+ times to fix the same thing → just use Claude

**Model-tier routing:**
| Model | $/M in | $/M out | When |
|-------|--------|---------|------|
| Haiku 4.5 | ~$1 | ~$5 | Classification, routing, short rewrites, log triage |
| Sonnet 4.6 | ~$3 | ~$15 | Default. 95% of code edits, agentic loops, memory ops |
| Opus 4.7 | ~$15 | ~$75 | Architectural planning, nasty bugs, multilateral synthesis |

Pin subagents to Haiku for memory ops, classification, log writes (80% of agent calls).

**Prompt caching — biggest single saver:**
- 90% discount on cached input tokens, 5-min TTL
- Writes cost 25% more than base input
- Realistic agentic session: 40-70% input cost reduction
- Cache order: system prompt → tool definitions → memory excerpts → long reference docs
- Structure: immutable → mostly-stable → volatile
- Agent SDK manages cache breakpoints automatically

**Context hygiene:**
- `/clear` aggressively at every task boundary
- Auto-compact triggers at 90-95% — pre-empt it
- Lazy memory pulls (recall on demand, not eager load at session start)
- Read with offset/limit — never cat a >500-line file
- Truncate tool output, paginate lists

**Plan tiers:**
- Pro ($20/mo) — ~45 msg/5h on Sonnet. Bad fit for agentic work.
- Max 5× ($100/mo) — ~225 msg/5h. Works for 1-2 focused sessions/day.
- Max 20× ($200/mo) — ~900 msg/5h, generous Opus. The daily driver tier.
- **Recommendation:** Try Max 5× with disciplined /clear + Haiku subagents + Qwen for grunt work.

**Hybrid routing patterns:**
- LiteLLM proxy — single OpenAI-compatible endpoint, route by model name
- Aider's `--model` + `--weak-model` — built-in cheap/strong split
- Subagent-to-Qwen MCP — dispatch bulk grunt work via MCP (cleanest hybrid)

---

## Part 6 — Execution Order

1. `claude setup-token` → save OAuth token → foundation for everything
2. Get Claudegram repo access from Kerod → read: `src/config.ts` → `src/claude/agent.ts` → `src/bot/handlers/message.handler.ts`
3. Fork Claudegram → plug in bot token → set `ALLOWED_USER_IDS` to Telegram ID → `botctl.sh start` → JARVIS on phone
4. Pin subagents to Haiku 4.5 in CLAUDE.md
5. Wire LiteLLM for bulk work → Qwen, not Claude (~1 hour)
6. Web UI: swap backend model layer for FastAPI SSE pattern (~1 day)
7. Memory: create `_Memory/active/` with one entity per current thread → add session-start + stop hooks (~2 hours)
8. One month later: review token usage, adjust plan tier

---

## Part 7 — Open Questions

1. Web stack? (FastAPI assumes Python — Node/Bun needs different example) → **We have Flask, migrating to FastAPI**
2. Where does current memory live? → **SQLite `memory/jarvis.db`**
3. What MCPs are running? → **Custom tools: email, iMessage, web search, screen control, tasks**
4. Linux or Windows for daemon host? → **macOS**

---

## Key Decisions for JARVIS

- **Remove Groq from brain entirely** — Llama had access to email/iMessage/screen. Too risky.
- **Claude Agent SDK + OAuth token = the brain**
- **Flask → FastAPI** for web surface (SSE streaming)
- **Claudegram fork** for Telegram surface
- **`_Memory/` wiki** replacing raw SQLite conversation log
- **Groq kept only as absolute last-resort fallback**, no tool access
