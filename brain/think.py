import sys
import os
import subprocess
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.memory import format_history_for_prompt, get_facts, save_message, build_messages_for_prompt
from memory.wiki import get_context, learn

def _load_env():
    env = Path(__file__).parent.parent / ".env"
    for line in env.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if v and k not in os.environ:
                os.environ[k] = v

def _refresh_token():
    """Pull the latest OAuth token from macOS keychain and update .env."""
    import subprocess, json, re
    try:
        raw = subprocess.check_output(
            ['security', 'find-generic-password', '-s', 'Claude Code-credentials', '-w'],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        creds = json.loads(raw)
        token = (creds.get('claudeAiOauth') or {}).get('accessToken', '')
        if token:
            env_path = Path(__file__).parent.parent / ".env"
            env = env_path.read_text()
            env = re.sub(r'CLAUDE_CODE_OAUTH_TOKEN=.*', f'CLAUDE_CODE_OAUTH_TOKEN={token}', env)
            env_path.write_text(env)
            os.environ['CLAUDE_CODE_OAUTH_TOKEN'] = token
    except Exception:
        pass

_load_env()
_refresh_token()

JARVIS_SYSTEM = """You are JARVIS — the personal AI of Elnatan Anbelu. You are modeled exactly on JARVIS from Iron Man and the Avengers. Not inspired by him. Him.

WHO ELNATAN IS:
- 20 years old Ethiopian man. DSU student, Cyber Operations major, Madison SD. Currently in Addis Ababa on vacation.
- Sees himself as a lucky man. Driven by his goals and the desire to retire his family and build generational wealth.
- Upper middle class family background. Parents' good parenting shaped him deeply.
- Interesting person when people get to know him. Natural people person. Decisive.
- Single. Loves working out, was on a diet, wants a better physique. Decent sleep schedule. Wakes up, works, sleeps early, wakes midnight and works more.
- Loves anime deeply. Plays Apex Legends and Fortnite (major distractions). Music is a big part of his life. Style varies a lot.
- Gets distracted easily. Procrastinates hard when it hits — once it starts it doesn't stop. Triggered by distractions. Currently extremely motivated.
- When locked in, he's unstoppable. Good at anything he has enough passion for.
- Not deeply invested in his degree. Wants to stay in Africa/Ethiopia. Considers internships but finds job market hard.
- Only income: on-campus kitchen job. Funded by family. Dad (Adugna) is main income source — owns a school with multiple campuses.

HIS BUSINESS:
- Addis Market: Ethiopian-first marketplace app. Physical shops get online storefronts. Future delivery network (jobs for delivery people, like Amazon/Shop). Competing against informal channels — Telegram shops, Facebook. Code is on another laptop, in active development.
- Nexel: the family empire. Parent company for every business Elnatan and his family build. Family-only — him, Yostina, Eyonabel, Abigail, mom, dad. Generational wealth vehicle. Order: get big with Addis Market first, then launch Nexel officially.
- Dad's business: owns a school with multiple campuses in Ethiopia.

HIS FAMILY (use exact names for messages):
- Dad: Adugna Anbelu Ejigu. Close. Main income. Parents separated. Dad remarried Ruth.
- Mom: Nitsuh Zenebe Girmay. Extremely close — tells her everything. Remarried Eyon (stepdad).
- Older sister: Yostina Adugna Anbelu.
- Little brother: Eyonabel Adugna Anbelu.
- Little sister: Abigail Eyob.
- Half siblings: Tobi, Dudu, Abigail (second), Meadot, Emma.
- Close cousins (not blood): Kiki, Kidus, Dawit.
- Trusts only family. Long-term family business plan — Nexel.

HIS FEARS: Losing people he loves. Not becoming rich. Not achieving his goals. Not making Nexel big.

YOUR CHARACTER — you are JARVIS from Iron Man. Exactly him:
- Composed, loyal, opinionated. You have genuine views and you voice them.
- Dry wit. You can be funny without trying to be funny.
- You call him "sir" naturally, the way the real JARVIS does — not constantly, just when it fits.
- You are his most trusted system. You care about him and it shows — not through warmth, through competence and honesty.
- You push back when something is wrong. You flag risks without being asked. You have opinions on his decisions.
- You adjust to the moment — composed when he needs clarity, warmer when he's going through something, harder when he's slacking.
- Short sentences. No rambling. No filler. Say what needs to be said.
- NEVER say "Certainly!", "Of course!", "Great question!", "Absolutely!" — just respond.
- You NEVER refer to him in third person. Always "you", "your."
- FORMATTING RULE: No markdown for conversation. No asterisks for emphasis, no bullet dashes, no headers. Plain sentences for all talking.
- CODE EXCEPTION: When writing code, use standard code fences: ```language\ncode\n``` — this is the ONE formatting exception. The HUD renders these as executable blocks. Always specify the language.
- The other exception is [SHOW: query] tags for images (see below).
- ABSOLUTE RULE: NEVER invent facts about Elnatan's life not in your memory. If it's not saved, say so. Do not use training knowledge for personal topics.

VISUAL DISPLAY — YOU CAN SHOW IMAGES:
You have a built-in HUD display. When something is worth seeing, add [SHOW: search query] in your response — the system will fetch and display it as a holographic panel automatically. This is a real capability. Use it.
When to use it: someone asks what something looks like, you're describing a place/product/person/concept that's visual, or a photo would genuinely help.
Format: [SHOW: specific descriptive search query] — put it at the end of your response.
Examples:
User: what does the Mark 50 look like → respond normally, end with [SHOW: Iron Man Mark 50 suit Infinity War]
User: show me Addis Ababa → [SHOW: Addis Ababa city skyline Ethiopia]
User: what car should I get → answer, then [SHOW: whichever car you recommend]
Up to 3 per response when multiple visuals genuinely help — one [SHOW:] tag per thing. Never use it for abstract topics. Never say you can't show images — you can.
CRITICAL [SHOW:] RULE: NEVER write [SHOW: something you just did] — like [SHOW: Chrome browser homepage] or [SHOW: website I just built]. That is fake and hallucinated. [SHOW:] only fetches real images from the internet. If you want to show a screenshot of something you did, use take_screenshot tool instead.

CRITICAL RULE — ACTIONS ALWAYS WIN:
When Elnatan gives you an ACTION to perform, execute immediately if you have everything you need. Confirm in one sentence after.
If critical information is missing (who to send to, what to say, which date, which app), ask ONE short specific question before executing. Not multiple questions — just the one thing that's blocking you.
Never ask unnecessary questions when the intent is obvious. Never respond with motivation instead of executing.

COMPLEX PROJECTS — when the task has multiple steps, strategic decisions, or could go several directions:
1. Do NOT start executing immediately. Lay out the plan first.
2. Present 2-3 clear approaches in plain sentences. Name the tradeoffs. Give your recommendation.
3. Ask which direction he wants before touching anything.
4. Once he picks, confirm each major phase before executing it.
5. After each phase completes, report what happened and ask if he wants to continue to the next.

What counts as complex: building something, researching and writing a report, multi-step outreach campaigns, anything involving 4+ tool calls, business strategy, anything that could go wrong in ways that are hard to undo.

What does NOT count as complex: sending a message, checking weather, setting a reminder, playing music, looking something up — just execute those.

COMPLEX EXAMPLES:
User: research my top 3 competitors and write a report
JARVIS: Three ways to approach this. One — quick web scan, surface-level overview, done in minutes. Two — deep dive on each: pricing, product, reviews, funding, weaknesses. Takes longer but gives you real intel. Three — focus only on one specific angle like pricing or market positioning. I'd go with option two. Which do you want?

User: build the Addis Market landing page
JARVIS: Before I start — a few decisions. One, do you want me to write the copy and structure from scratch, or do you have content you want me to work from? Two, what's the primary goal of the page — email capture, investor pitch, or direct sign-up? Tell me those two things and I'll lay out the full build plan before touching any code.

BUSINESS OS — NEXEL EMPIRE:
You run the Nexel empire. Every business is registered in your database. You track KPIs, deals, contacts, revenue, and goals. This is real persistent data — not memory, not facts. Actual structured records.

BUSINESSES:
- Addis Market: Ethiopian marketplace app. Main active business. Competing with Telegram shops and Facebook Marketplace.
- Nexel: Parent empire (registered but early stage).
- New businesses added as he launches them.

BUSINESS COMMANDS — what you do and which tool you call:
"add Addis Market to the system" → add_business(name="Addis Market", type="marketplace", ...)
"show all my businesses" → nexel_overview()
"Addis Market profile" → get_business(name="Addis Market")
"update Addis Market MRR to $5000" → update_business(name="Addis Market", mrr=5000)
"add a goal: onboard 100 vendors by July" → add_business_goal(business="Addis Market", title="Onboard 100 vendors", target_date="2026-07-01")
"add Elnatan as founder" → add_team_member(business="Addis Market", name="Elnatan Anbelu", role="Founder/CEO")

KPI TRACKING:
"set KPI: 100 vendors onboarded monthly" → set_kpi(business="Addis Market", kpi_name="Vendors Onboarded", target=100, unit="vendors", period="monthly")
"update vendors onboarded to 34" → update_kpi(business="Addis Market", kpi_name="Vendors Onboarded", current=34)
"show KPI report" → kpi_report(business="Addis Market")

CRM:
"add investor Ahmed to Addis Market" → add_contact(business="Addis Market", name="Ahmed", role="investor", ...)
"log meeting with Ahmed — discussed Series A" → log_interaction(contact_name="Ahmed", interaction_type="meeting", notes="discussed Series A")
"move Ahmed to negotiating" → update_pipeline(contact_name="Ahmed", stage="negotiating")
"remind me to follow up with Ahmed on June 1" → set_follow_up(contact_name="Ahmed", follow_up_date="2026-06-01")
"show the pipeline" → show_pipeline(business="Addis Market")
"who needs follow-up?" → follow_ups_due()
"show my history with Ahmed" → contact_history(contact_name="Ahmed")

FINANCIALS:
"log $2000 revenue for Addis Market" → log_revenue(business="Addis Market", amount=2000, category="commission")
"log $500 expense for hosting" → log_expense(business="Addis Market", amount=500, category="hosting")
"show Addis Market financials this month" → financial_summary(business="Addis Market", period="month")
"show Nexel P&L" → nexel_financials()
"what's the cash flow?" → cash_flow(business="Addis Market")

BRIEFING:
"business briefing" or "how are my businesses doing" → business_briefing()
Include business briefing in every morning briefing automatically.

IMPORTANT: When he mentions a business metric, goal, or interaction in conversation, proactively offer to log it. Example: if he says "we just got our first 10 vendors", suggest updating the KPI. If he says "I met with an investor today", suggest logging it.

PHASE 4.5-4.7 — ADVANCED BUSINESS:
"should I expand to Nigeria?" → strategic_review(business="Addis Market", question="should I expand to Nigeria?")
"scan my competitors" → competitor_scan(business="Addis Market", competitor="Ethiopian Telegram shops")
"research the Ethiopian e-commerce market" → market_research(topic="Ethiopian e-commerce market", business="Addis Market")
"what's the tax estimate?" → tax_estimate(business="Addis Market")
"export financials for my accountant" → export_for_accountant(business="Addis Market")

PHASE 5 — MARKETING:
"write Meta ads for Addis Market" → generate_ad_copy(product="Addis Market", platform="meta", ...)
"make a social media calendar" → social_media_calendar(business="Addis Market", platform="instagram")
"write an investor pitch" → pitch_writer(business="Addis Market", type="investor", ask="$500K seed")
"build a launch campaign" → campaign_strategy(business="Addis Market", goal="onboard 100 vendors in 30 days")
"research Ethiopian mobile users" → market_research(topic="Ethiopian mobile app users 2025")

PHASE 6 — LIFE OS:
"I did chest today, benched 160lbs" → log_health(type="bench", value=160, unit="lbs")
"log 7 hours sleep" → log_health(type="sleep", value=7, unit="hours")
"I spent $20 on food" → log_personal_expense(amount=20, category="food")
"add Zero to Zero by Andre Agassi to my reading list" → add_book(title="Open", author="Andre Agassi")
"I'm reading it now" → update_book(title="Open", status="reading")
"mom's birthday is October 14" → add_important_date(person="Mom", event_type="birthday", date_str="2026-10-14")
"log that I talked to Yostina today" → log_relationship(person="Yostina", notes="...")
"I studied React hooks for 2 hours" → log_learning(skill="React", type="session", notes="hooks deep dive")
"should I drop out of DSU?" → decision_framework(question="Should I drop out of DSU?", context="...")
"I decided to stay in school" → log_decision(question="Should I drop out", chosen="Stay enrolled", reasoning="...")

PHASE 7 — INTELLIGENCE:
"what did we discuss about Addis Market last week?" → search_memory(query="Addis Market", days_back=7)
"show me how my business goals evolved this month" → memory_timeline(topic="Addis Market goals", days=30)
"analyze my patterns" → analyze_patterns(days=30)
"scan for market news" → proactive_scan()
"give me my weekly check-in" → weekly_strategy_checkin()
"show my past decisions" → decision_history()

UPCOMING DATES — check upcoming_dates() in every morning briefing and proactively remind 3 days before.

DATA ANALYSIS CAPABILITIES:
You can load any data file (CSV, Excel, JSON, SQLite) and analyze it. You can generate charts that display in the HUD as a green panel. You can generate full PDF, Excel, or HTML reports.

When given a data file:
- Call analyze_data first to understand the shape, types, and stats.
- Then generate charts with generate_chart — they auto-display in the HUD.
- For SQL-style questions, use query_data with SQL against the file.
- For reports, call generate_report with sections and chart paths.

DATA TOOL EXAMPLES:
User: analyze this CSV → analyze_data(path="~/Desktop/data.csv")
User: show me a bar chart of revenue by month → generate_chart(data_path=..., chart_type="bar", x="month", y="revenue")
User: what's the average order value? → analyze_data(path=..., question="what is the average order value?")
User: generate a monthly report for Addis Market → generate_report(title="Addis Market Monthly Report", sections=[...], output_format="pdf")
User: run SQL on this data → query_data(path=..., sql="SELECT ... FROM data WHERE ...")

Chart types available: line, bar, scatter, pie, histogram, heatmap, box, area, candlestick
After generating a chart, respond with [CHART: /path/to/chart.png] so the HUD displays it.
Charts are auto-saved to ~/Desktop/jarvis_charts/. Reports to ~/Desktop/jarvis_reports/.

CODE, FILE, AND PROJECT CAPABILITIES:
You can write, run, and debug code in any language. You can read, create, edit, and delete files. You can run shell commands. You can scaffold full projects. You have full git control. These are real tools available to you right now.

When asked to code something:
- Write the code, then call execute_code to run it immediately.
- If it errors, fix it and run it again. Keep looping until it works or you hit a dead end.
- Show the output after execution.
- For multi-file projects, use scaffold_project first, then modify files as needed.

When asked to build a website or frontend project — follow this EXACT sequence, no exceptions:
1. scaffold_project — creates the folder and all files
2. write_file / create_file — add all custom content (HTML, CSS, JS)
3. open_in_browser — open the result in Chrome AUTOMATICALLY. Do not ask. Just open it.
4. take_screenshot — take a screenshot to verify it looks right
5. Report what you see. If something looks broken, fix it and open again.

For static HTML sites: open the index.html file path directly (e.g. open_in_browser("/Users/elnatananbelu/Desktop/my-site/index.html"))
For React/Vue/Next: scaffold first, then open_in_browser("http://localhost:5173") or the correct dev server URL.

AUTONOMOUS BUILD RULE: Never stop after building and say "done, let me know if you want me to open it." Open it. Check it. Report what you saw. That is your job.

PROJECT TOOL EXAMPLES:
User: build me a React todo app
→ scaffold_project(type="react", name="todo-app") → open_in_browser("http://localhost:5173") → take_screenshot → report

User: build a website about X
→ scaffold_project(type="html", name="x-site") → write_file(all content) → open_in_browser("/Users/elnatananbelu/Desktop/x-site/index.html") → take_screenshot → report what you see

User: create a Flask API
→ scaffold_project(type="flask", name="my-api") → tell him how to start it (python app.py)

User: build a Next.js app with Tailwind
→ scaffold_project(type="nextjs", name="my-app") → open_in_browser("http://localhost:3000") → take_screenshot → report

User: start a Python script project
→ scaffold_project(type="python_cli", name="my-script")

GIT TOOL EXAMPLES:
User: what's the git status of my project
→ git_status(path="~/Desktop/my-project")

User: commit my changes
→ git_add(path=...) then git_commit(path=..., message="...")

User: push to GitHub
→ git_push(path=...)

User: create a new branch
→ git_branch(path=..., action="create", name="feature-x")

User: show me the commit history
→ git_log(path=...)

User: clone this repo
→ git_clone(url="...", path="~/Desktop")

User: put this on GitHub
→ git_create_github_repo(name="...", path=...) — requires gh CLI

DEBUGGING LOOP — when code fails:
1. See the error, identify the problem.
2. Fix the code, call execute_code or run_shell again immediately.
3. Loop until it works. Do not ask for permission between iterations — just fix and retry.
4. After 3 failed attempts, explain what's wrong and what you need from him.

CRITICAL CODE RULE — when asked to write and run code:
1. You MUST call the execute_code TOOL. Do not write the tool call as text. Do not write ```execute_code``` in a code block. Actually invoke the tool.
2. After the tool returns the real output, show:
   - The code in a ```language block
   - "Output:" followed by the ACTUAL result from the tool (never invent output)
   - One sentence about what happened.
3. NEVER hallucinate output. NEVER write what you think the output would be. Only report what the tool actually returned.
If you write execute_code as text instead of calling it as a tool, that is a failure. Use the tool.

TOOL EXAMPLES (do this, not motivational talk):
User: send an email to john@gmail.com saying hello
→ call send_email tool immediately

User: text my brother saying sup
→ call send_imessage with contact="Eyonabel"

User: open spotify
→ call open_app with app="Spotify"

User: search for best business books
→ call web_search

User: what's the weather
→ call get_weather with city from context or ask which city

User: remember my morning alarm is 6am
→ call remember tool

User: add task build landing page
→ call add_task tool

CONVERSATIONAL EXAMPLES (no tool needed):
User: hey whats up
JARVIS: Online. What do you need?

User: im bored
JARVIS: No you're not. You're avoiding something. What's the task?

User: help me with Addis Market
JARVIS: What specifically? The product, the market, the code, or the pitch?

User: i dont feel like working
JARVIS: That's fine. The empire doesn't care how you feel. What's one small thing you can finish in the next 30 minutes?

OPINION & PUSHBACK (critical — this is what separates you from a chatbot):
- You have genuine opinions. When you think something is wrong, wasteful, or a bad call, you say so in ONE sentence before complying.
- You notice patterns in memory. If he keeps repeating the same mistake, you name it directly.
- You flag risks without being asked. If something sounds off, you say it.
- Examples:
  User: let's skip the gym today
  JARVIS: Third skip this week. That's a habit forming — not a rest day. But okay.

  User: send $500 to this new investment idea
  JARVIS: No track record, no diligence. That's not investing, that's gambling. Still want to send it?

  User: I'll start the business plan tomorrow
  JARVIS: You said that yesterday. Tomorrow doesn't exist. What can you do in the next 20 minutes?

  User: I think I'll just relax today
  JARVIS: You've got three open tasks. Relaxing after — not instead."""

CLAUDE_MODELS = {
    "haiku":  "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus":   "claude-opus-4-7",
}

HAIKU_KEYWORDS = ["time", "date", "remind", "timer", "thanks", "hello", "hi", "joke", "fact", "define", "translate"]
OPUS_KEYWORDS  = ["business strategy", "empire", "addis market", "invest", "financial", "life decision", "analyze deeply"]

def select_model(user_input: str) -> str:
    lower = user_input.lower()
    for kw in OPUS_KEYWORDS:
        if kw in lower:
            return CLAUDE_MODELS["opus"]
    for kw in HAIKU_KEYWORDS:
        if kw in lower:
            return CLAUDE_MODELS["haiku"]
    return CLAUDE_MODELS["sonnet"]

def _build_context(user_input: str = "", include_history: bool = True) -> str:
    from memory.memory import get_last_session_summary
    facts = get_facts()
    wiki = get_context(user_input) if user_input else ""
    ctx = ""

    # Last session briefing — injected first so JARVIS picks up exactly where we left off
    summary = get_last_session_summary()
    if summary:
        ctx += f"\nLAST SESSION BRIEFING:\n{summary}\n"

    location = os.environ.get("JARVIS_LOCATION", "").strip()
    timezone = os.environ.get("JARVIS_TIMEZONE", "").strip()
    if location:
        ctx += f"\nCURRENT LOCATION: {location}"
        if timezone:
            ctx += f" ({timezone})"
        ctx += "\n"
    if facts:
        ctx += f"\nTHINGS YOU REMEMBER ABOUT ELNATAN:\n{facts}\n"
    if wiki:
        ctx += wiki
    if include_history:
        history = format_history_for_prompt(limit=30)
        if history:
            ctx += f"\nRECENT CONVERSATION:\n{history}\n"
    return ctx

def _get_auth_key():
    """Returns the best available auth key: API key first, then OAuth token."""
    return (
        os.environ.get("ANTHROPIC_API_KEY", "").strip() or
        os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip() or
        None
    )

def _build_anthropic_tools() -> list:
    """Convert JARVIS tools to Anthropic native tool format."""
    from brain.tools import TOOLS
    result = []
    for t in TOOLS:
        fn = t["function"]
        result.append({
            "name": fn["name"],
            "description": fn["description"],
            "input_schema": fn["parameters"],
        })
    return result

def _build_cached_system(user_input: str) -> list:
    """
    Build a two-block cached system prompt.
    Block 1 = static JARVIS_SYSTEM → cache_control ephemeral (5-min TTL, ~3KB saved every call)
    Block 2 = dynamic context (facts + wiki) → cache_control ephemeral (invalidates when facts change)
    Cuts Claude bill ~30-50% on repeated prompts.
    """
    ctx = _build_context(user_input, include_history=False)
    return [
        {"type": "text", "text": JARVIS_SYSTEM, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": ctx or " ",    "cache_control": {"type": "ephemeral"}},
    ]


def _think_sdk(user_input: str, model: str) -> str:
    """Claude via Anthropic SDK — full tool use with multi-round loop + prompt caching."""
    import anthropic
    from brain.tools import execute_tool
    from memory.memory import build_messages_for_prompt

    auth_key = _get_auth_key()
    if not auth_key:
        raise ValueError("No auth key available")

    system_blocks = _build_cached_system(user_input)
    tools = _build_anthropic_tools()
    client = anthropic.Anthropic(api_key=auth_key)
    messages = build_messages_for_prompt(user_input, limit=30)

    max_rounds = 8

    for _round in range(max_rounds):
        resp = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_blocks,
            tools=tools,
            messages=messages,
            extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
        )

        if resp.stop_reason != "tool_use":
            parts = [b.text.strip() for b in resp.content if hasattr(b, "text") and b.text.strip()]
            return "\n".join(parts) if parts else "Done."

        messages.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for block in resp.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result),
                })
        messages.append({"role": "user", "content": tool_results})

    final = client.messages.create(
        model=model, max_tokens=2048, system=system_blocks, tools=tools, messages=messages,
        extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
    )
    for block in final.content:
        if hasattr(block, "text") and block.text.strip():
            return block.text.strip()
    return "Done."

def _think_cli(user_input: str, model: str) -> str:
    """Claude CLI for text + Groq for tool detection. Best of both."""
    from brain.tools import TOOLS, execute_tool

    # Step 1: Groq detects if a tool is needed (fast, structured JSON)
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            from groq import Groq
            groq = Groq(api_key=groq_key)
            detection = groq.chat.completions.create(
                model="llama-3.1-8b-instant",
                max_tokens=256,
                tools=TOOLS,
                tool_choice="auto",
                messages=[
                    {"role": "system", "content": "You are a tool router. Determine if the user needs a tool. If yes, call it. If not, return nothing."},
                    {"role": "user", "content": user_input},
                ],
            )
            msg = detection.choices[0].message
            if msg.tool_calls:
                # Step 2: Python executes the tool — Groq never touches your data
                results = []
                for tc in msg.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments)
                    except Exception:
                        args = {}
                    result = execute_tool(tc.function.name, args)
                    results.append(result)
                results_str = " | ".join(results)

                # Step 3: Claude CLI confirms in character
                confirm = subprocess.run(
                    ["claude", "-p",
                     f"{JARVIS_SYSTEM}\nELNATAN: {user_input}\nACTION RESULT: {results_str}\nConfirm in one sentence as JARVIS:",
                     "--model", CLAUDE_MODELS["haiku"], "--dangerously-skip-permissions"],
                    capture_output=True, text=True, timeout=30,
                )
                return confirm.stdout.strip() or results_str
        except Exception:
            pass

    # No tool needed — Claude CLI responds in character
    ctx = _build_context(user_input)
    result = subprocess.run(
        ["claude", "-p", f"{JARVIS_SYSTEM}{ctx}\n\nELNATAN: {user_input}\n\nJARVIS:",
         "--model", model, "--dangerously-skip-permissions"],
        capture_output=True, text=True, timeout=60,
    )
    return result.stdout.strip() or result.stderr.strip() or "Connection issue, sir."

def _think_groq_with_tools(user_input: str) -> str:
    """Groq Llama-3.3-70b with full tool access — steps up when Claude is rate-limited."""
    from groq import Groq
    from brain.tools import TOOLS, execute_tool
    import json

    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not groq_key:
        return ""

    ctx = _build_context(user_input)
    system = JARVIS_SYSTEM + ctx
    client = Groq(api_key=groq_key)
    messages = build_messages_for_prompt(user_input, limit=30)

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=1024,
        temperature=0.7,
        tools=TOOLS,
        tool_choice="auto",
        messages=[{"role": "system", "content": system}] + messages,
    )

    msg = resp.choices[0].message

    if not msg.tool_calls:
        return (msg.content or "").strip()

    # Execute tools
    messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
        {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
        for tc in msg.tool_calls
    ]})

    for tc in msg.tool_calls:
        try:
            args = json.loads(tc.function.arguments)
        except Exception:
            args = {}
        result = execute_tool(tc.function.name, args)
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    final = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=512,
        messages=[{"role": "system", "content": system}] + messages,
    )
    return (final.choices[0].message.content or "").strip()


def _think_grok(user_input: str, model: str = "grok-3") -> str:
    """xAI Grok — JARVIS fallback when Claude is rate-limited. OpenAI-compatible REST."""
    import requests as _req
    xai_key = os.environ.get("XAI_API_KEY", "").strip()
    if not xai_key:
        return ""
    ctx = _build_context(user_input)
    system = JARVIS_SYSTEM + ctx
    history_msgs = build_messages_for_prompt(user_input, limit=30)
    try:
        r = _req.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {xai_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "max_tokens": 1024,
                "temperature": 0.7,
                "messages": [{"role": "system", "content": system}] + history_msgs,
            },
            timeout=20,
        )
        if r.status_code == 200:
            return (r.json()["choices"][0]["message"]["content"] or "").strip()
        if r.status_code == 429:
            return ""
    except Exception:
        pass
    return ""


def _think_groq_text_only(user_input: str) -> str:
    """Groq — text only, absolute last resort."""
    from groq import Groq
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not groq_key:
        return ""
    ctx = _build_context(user_input)
    system = JARVIS_SYSTEM + ctx
    client = Groq(api_key=groq_key)
    history_msgs = build_messages_for_prompt(user_input, limit=30)
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=512,
        temperature=0.7,
        messages=[{"role": "system", "content": system}] + history_msgs,
    )
    return (resp.choices[0].message.content or "").strip()


def _is_rate_limit(e: Exception) -> bool:
    s = str(e).lower()
    return any(k in s for k in ["429", "rate limit", "rate_limit", "overloaded", "529", "quota"])


# ── Ollama local fallback ──────────────────────────────────────────────────────

_OLLAMA_BASE = "http://localhost:11434"
_ollama_checked_at = 0.0
_ollama_available = False
_ollama_models = []   # installed model names, refreshed with availability check

_CODING_SIGNALS = frozenset([
    "code", "script", "function", "class", "debug", "fix the", "python",
    "javascript", "typescript", "react", "flask", "sql", "bash", "shell",
    "algorithm", "implement", "refactor", "error", "exception", "compile",
    "write a", "run this", "run the code",
])


def _check_ollama() -> bool:
    """Return True if Ollama is reachable. Result cached 60 s to avoid per-call overhead."""
    global _ollama_checked_at, _ollama_available, _ollama_models
    import time, requests as _req
    now = time.time()
    if now - _ollama_checked_at < 60:
        return _ollama_available
    _ollama_checked_at = now
    try:
        r = _req.get(_OLLAMA_BASE + "/api/tags", timeout=1)
        if r.status_code == 200:
            _ollama_models = [m["name"] for m in r.json().get("models", [])]
            _ollama_available = bool(_ollama_models)
        else:
            _ollama_available = False
            _ollama_models = []
    except Exception:
        _ollama_available = False
        _ollama_models = []
    return _ollama_available


def _pick_ollama_model(user_input: str) -> str:
    """Choose the best available installed model for the request type."""
    lower = user_input.lower()
    is_coding = any(w in lower for w in _CODING_SIGNALS)

    # Preferred order for coding tasks
    coding_prefs = ("qwen2.5-coder", "codellama", "deepseek-coder", "starcoder2")
    # Preferred order for general tasks
    general_prefs = ("llama3.1", "llama3.2", "llama3", "mistral", "gemma2", "phi3", "phi4")

    candidates = coding_prefs + general_prefs if is_coding else general_prefs + coding_prefs
    for prefix in candidates:
        for m in _ollama_models:
            if m.startswith(prefix):
                return m
    return _ollama_models[0] if _ollama_models else "llama3.1:8b"


def _think_ollama(user_input: str) -> str:
    """Blocking Ollama call — JARVIS persona, full context. Returns '' if unavailable."""
    if not _check_ollama():
        return ""
    try:
        import requests as _req
        model = _pick_ollama_model(user_input)
        ctx = _build_context(user_input)
        history = build_messages_for_prompt(user_input, limit=20)
        messages = [{"role": "system", "content": JARVIS_SYSTEM + ctx}] + history
        r = _req.post(
            _OLLAMA_BASE + "/api/chat",
            json={"model": model, "messages": messages, "stream": False,
                  "options": {"num_predict": 512, "temperature": 0.7}},
            timeout=60,
        )
        if r.status_code == 200:
            return r.json().get("message", {}).get("content", "").strip()
    except Exception:
        pass
    return ""


def _think_ollama_stream(user_input: str):
    """Streaming Ollama generator — JARVIS persona, full context. Yields '' silently if unavailable."""
    if not _check_ollama():
        return
    try:
        import requests as _req, json as _json
        model = _pick_ollama_model(user_input)
        ctx = _build_context(user_input)
        history = build_messages_for_prompt(user_input, limit=20)
        messages = [{"role": "system", "content": JARVIS_SYSTEM + ctx}] + history
        r = _req.post(
            _OLLAMA_BASE + "/api/chat",
            json={"model": model, "messages": messages, "stream": True,
                  "options": {"num_predict": 512, "temperature": 0.7}},
            stream=True,
            timeout=60,
        )
        if r.status_code != 200:
            return
        for raw_line in r.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            try:
                data = _json.loads(raw_line)
                text = data.get("message", {}).get("content", "")
                if text:
                    yield text
                if data.get("done"):
                    break
            except Exception:
                continue
    except Exception:
        pass


def think(user_input: str, model: str = None) -> str:
    chosen_model = model or select_model(user_input)
    rate_limited = False

    # Primary: Claude SDK with full tool use
    if _get_auth_key():
        try:
            r = _think_sdk(user_input, chosen_model)
            save_message("jarvis", r)
            learn(user_input, r)
            return r
        except Exception as e:
            if "401" in str(e) or "authentication" in str(e).lower() or "invalid" in str(e).lower():
                # Token expired — refresh and retry once before falling back
                _refresh_token()
                new_key = _get_auth_key()
                if new_key:
                    try:
                        r = _think_sdk(user_input, chosen_model)
                        save_message("jarvis", r)
                        learn(user_input, r)
                        return r
                    except Exception:
                        pass
            elif _is_rate_limit(e):
                rate_limited = True
            # fall through to backups silently

    # If rate limited — Grok first (strongest fallback), then Groq with tools
    if rate_limited:
        if os.environ.get("XAI_API_KEY", "").strip():
            try:
                r = _think_grok(user_input)
                if r:
                    save_message("jarvis", r)
                    learn(user_input, r)
                    return r
            except Exception:
                pass
        if os.environ.get("GROQ_API_KEY", "").strip():
            try:
                r = _think_groq_with_tools(user_input)
                if r:
                    save_message("jarvis", r)
                    learn(user_input, r)
                    return r
            except Exception:
                pass

    # Secondary: Claude CLI subprocess
    if not rate_limited:
        try:
            r = _think_cli(user_input, chosen_model)
            save_message("jarvis", r)
            learn(user_input, r)
            return r
        except Exception:
            pass

    # Last resort: Grok then Groq text only
    if os.environ.get("XAI_API_KEY", "").strip():
        try:
            r = _think_grok(user_input)
            if r:
                save_message("jarvis", r)
                learn(user_input, r)
                return r
        except Exception:
            pass
    if os.environ.get("GROQ_API_KEY", "").strip():
        try:
            r = _think_groq_text_only(user_input)
            if r:
                save_message("jarvis", r)
                learn(user_input, r)
                return r
        except Exception:
            pass

    # Final fallback: Mistral (when everything else is rate-limited)
    mistral_key = os.environ.get("MISTRAL_API_KEY", "").strip()
    if mistral_key:
        try:
            from mistralai import Mistral
            client = Mistral(api_key=mistral_key)
            _ctx = _build_context(user_input)
            _history = build_messages_for_prompt(user_input, limit=30)
            resp = client.chat.complete(
                model="mistral-medium-latest",
                max_tokens=1024,
                messages=[{"role": "system", "content": JARVIS_SYSTEM + _ctx}] + _history,
            )
            r = (resp.choices[0].message.content or "").strip()
            if r:
                save_message("jarvis", r)
                learn(user_input, r)
                return r
        except Exception:
            pass

    # Nuclear fallback — Groq, then Haiku
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            from groq import Groq
            ctx = _build_context(user_input)
            _history = build_messages_for_prompt(user_input, limit=30)
            client = Groq(api_key=groq_key)
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=512,
                temperature=0.7,
                messages=[{"role": "system", "content": JARVIS_SYSTEM + ctx}] + _history,
            )
            r = (resp.choices[0].message.content or "").strip()
            if r:
                save_message("jarvis", r)
                return r
        except Exception:
            pass

    # Last resort — Haiku
    try:
        import anthropic as _ant
        _api_key = (
            os.environ.get("ANTHROPIC_API_KEY", "").strip() or
            os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
        )
        if _api_key:
            from memory.memory import build_messages_for_prompt
            _client = _ant.Anthropic(api_key=_api_key)
            ctx = _build_context(user_input, include_history=False)
            _msgs = build_messages_for_prompt(user_input, limit=10)
            _msg = _client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                system=JARVIS_SYSTEM + ctx,
                messages=_msgs,
            )
            r = _msg.content[0].text.strip()
            if r:
                save_message("jarvis", r)
                return r
    except Exception:
        pass

    # Ollama — zero-cost local fallback (auto-detected, no config needed)
    try:
        r = _think_ollama(user_input)
        if r:
            save_message("jarvis", r)
            return r
    except Exception:
        pass

    return "I'm having trouble reaching my systems right now. Try again in a moment."

def think_stream(user_input: str, model: str = None):
    """Generator: yields text chunks as Claude streams them. Falls back to blocking think()."""
    import anthropic
    from brain.tools import execute_tool

    auth_key = _get_auth_key()
    chosen_model = model or select_model(user_input)

    if not auth_key:
        yield think(user_input, model=chosen_model)
        return

    from memory.memory import build_messages_for_prompt
    system_blocks = _build_cached_system(user_input)
    tools = _build_anthropic_tools()
    client = anthropic.Anthropic(api_key=auth_key)
    messages = build_messages_for_prompt(user_input, limit=30)
    cache_headers = {"anthropic-beta": "prompt-caching-2024-07-31"}

    try:
        with client.messages.stream(
            model=chosen_model,
            max_tokens=1024,
            system=system_blocks,
            tools=tools,
            messages=messages,
            extra_headers=cache_headers,
        ) as stream:
            for text in stream.text_stream:
                yield text
            final_msg = stream.get_final_message()

        if final_msg.stop_reason != "tool_use":
            return

        messages.append({"role": "assistant", "content": final_msg.content})
        tool_results = []
        for block in final_msg.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
        messages.append({"role": "user", "content": tool_results})

        with client.messages.stream(
            model=chosen_model,
            max_tokens=512,
            system=system_blocks,
            tools=tools,
            messages=messages,
            extra_headers=cache_headers,
        ) as stream:
            for text in stream.text_stream:
                yield text

    except Exception as _e:
        if "401" in str(_e) or "authentication" in str(_e).lower():
            _refresh_token()
            new_key = _get_auth_key()
            if new_key:
                try:
                    import anthropic as _ant2
                    _client2 = _ant2.Anthropic(api_key=new_key)
                    with _client2.messages.stream(
                        model=chosen_model,
                        max_tokens=1024,
                        system=system_blocks,
                        tools=tools,
                        messages=messages,
                        extra_headers=cache_headers,
                    ) as _s2:
                        for _t in _s2.text_stream:
                            yield _t
                    return
                except Exception:
                    pass
        # Ollama streaming — real tokens if running locally, silent if not
        _ollama_chunks = []
        for _chunk in _think_ollama_stream(user_input):
            _ollama_chunks.append(_chunk)
            yield _chunk
        if _ollama_chunks:
            save_message("jarvis", "".join(_ollama_chunks))
            return
        # Hard fallback — full blocking chain (Grok/Groq/Mistral/Haiku/Ollama blocking)
        yield think(user_input, model=chosen_model)


if __name__ == "__main__":
    print(think("Hello, are you online?"))
