# JARVIS — Tool Reference

All 100+ tools available to JARVIS. Tools are invoked automatically — JARVIS decides when to use them based on your request. You never need to call them explicitly.

---

## Computer Control

| Tool | What It Does |
|------|-------------|
| `click` | Click at screen coordinates or on a named element |
| `right_click` | Right-click at coordinates |
| `double_click` | Double-click at coordinates |
| `type_text` | Type text into the focused field |
| `press_key` | Press a keyboard key or shortcut |
| `scroll` | Scroll up or down at coordinates |
| `drag` | Click-drag from one point to another |
| `move_mouse` | Move cursor to coordinates without clicking |
| `take_screenshot` | Capture the screen and analyze it visually |
| `get_screen_size` | Get the current display resolution |

**Example prompts:**
- *"Take a screenshot and tell me what's on screen"*
- *"Click the send button"*
- *"Type 'hello world' into the search bar"*

---

## App & System Control

| Tool | What It Does |
|------|-------------|
| `open_app` | Launch an application by name |
| `close_app` | Close a running application |
| `run_applescript` | Execute arbitrary AppleScript |
| `set_volume` | Set system volume (0–100) |
| `get_volume` | Get current volume level |
| `lock_screen` | Lock the Mac screen |
| `sleep_display` | Put the display to sleep |
| `open_in_browser` | Open a URL or local file in Chrome |

---

## Code Execution

| Tool | What It Does |
|------|-------------|
| `execute_code` | Run Python code in a real sandbox and return actual output |
| `execute_bash` | Run a bash command and return the result |
| `execute_javascript` | Run JavaScript in a Node.js context |
| `scaffold_project` | Create a full project structure from scratch |
| `write_file` | Write content to a file |
| `read_file` | Read a file from disk |
| `list_files` | List files in a directory |
| `delete_file` | Delete a file |

**Example prompts:**
- *"Write a Python script that calculates compound interest and run it"*
- *"Build me a landing page for my product"*
- *"Create a data visualization script for this CSV"*

---

## Git & Development

| Tool | What It Does |
|------|-------------|
| `git_status` | Show working tree status |
| `git_add` | Stage files for commit |
| `git_commit` | Create a commit with a message |
| `git_push` | Push to remote |
| `git_pull` | Pull from remote |
| `git_log` | Show recent commits |
| `git_diff` | Show changes |
| `git_branch` | Create or switch branches |

---

## Web & Research

| Tool | What It Does |
|------|-------------|
| `web_search` | Search the web and return results |
| `read_url` | Fetch and read the full content of a URL |
| `get_news` | Fetch latest news on a topic |
| `research` | Deep multi-source research on a topic |
| `get_weather` | Get weather for a city |

**Example prompts:**
- *"Search for the latest news on AI funding"*
- *"Read this article for me: [URL]"*
- *"Research the Nigerian e-commerce market"*

---

## Communication

| Tool | What It Does |
|------|-------------|
| `send_imessage` | Send an iMessage to a contact |
| `send_whatsapp` | Send a WhatsApp message |
| `send_email` | Send an email via Gmail |
| `read_emails` | Read recent emails from Gmail |
| `send_telegram` | Send a Telegram message |

**Example prompts:**
- *"Text John: running 10 minutes late"*
- *"Send an email to the team about tomorrow's meeting"*
- *"Read my last 5 emails"*

---

## Calendar & Time

| Tool | What It Does |
|------|-------------|
| `get_events` | Get upcoming calendar events |
| `create_event` | Create a new calendar event |
| `update_event` | Update an existing event |
| `delete_event` | Delete a calendar event |
| `set_timer` | Set a countdown timer |
| `set_alarm` | Set an alarm |
| `get_time` | Get the current time |

---

## Business OS

| Tool | What It Does |
|------|-------------|
| `generate_report` | Generate a business report |
| `create_chart` | Create a data visualization chart |
| `analyze_data` | Analyze a dataset and return insights |
| `write_marketing_copy` | Write ads, email campaigns, product descriptions |
| `competitor_analysis` | Research and compare competitors |
| `financial_breakdown` | Analyst-grade financial analysis |

---

## Personal Life OS

| Tool | What It Does |
|------|-------------|
| `get_goals` | Read your current goals |
| `add_goal` | Add a new goal |
| `update_goal` | Update goal progress |
| `get_morning_briefing` | Generate a full morning briefing |
| `add_life_note` | Add a note to your personal wiki |
| `focus_mode` | Start a Pomodoro focus session |

---

## Voice

| Tool | What It Does |
|------|-------------|
| `speak` | Make JARVIS speak a message aloud |
| `listen` | Activate voice input |
| `get_tts_status` | Check voice daemon status |

---

## Memory

Tools aren't the only way JARVIS learns. Every conversation is automatically saved and JARVIS uses the last 15 messages as context. Long-term facts, goals, and business data are stored in separate databases and loaded into context on relevant queries.
