"""
JARVIS tool definitions for Groq function calling.
JARVIS understands intent and calls the right function — no keyword guessing.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def _get_weather(city: str) -> str:
    try:
        import urllib.request, json
        city_enc = city.replace(' ', '+')
        url = f"https://wttr.in/{city_enc}?format=j1"
        with urllib.request.urlopen(url, timeout=8) as r:
            data = json.loads(r.read())
        c = data['current_condition'][0]
        desc = c['weatherDesc'][0]['value']
        temp_f = c['temp_F']
        feels_f = c['FeelsLikeF']
        humidity = c['humidity']
        return f"{city}: {desc}, {temp_f}°F (feels {feels_f}°F), humidity {humidity}%"
    except Exception as e:
        return f"Could not get weather: {e}"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email to someone",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Email subject line"},
                    "body": {"type": "string", "description": "Email body content"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_imessage",
            "description": "Send an iMessage or SMS to someone. CRITICAL: The 'message' field MUST be exactly what the user said to send. NEVER pull message content from conversation history, briefings, news, or any other context. If the user did not explicitly say what to send, do NOT call this tool — ask them first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact": {"type": "string", "description": "Contact's real name as it appears in Contacts (e.g. 'Mom', 'Dad'). Never guess a phone number."},
                    "message": {"type": "string", "description": "The exact message the user told you to send. Must come directly from the user's words, nothing else."},
                },
                "required": ["contact", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_emails",
            "description": "Read recent unread emails from inbox",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "Number of emails to read (default 5)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open a Mac application",
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {"type": "string", "description": "Application name e.g. Safari, Spotify, Xcode"},
                },
                "required": ["app"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_task",
            "description": "Add a task or reminder to the task list",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Task title"},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"], "description": "Task priority"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tasks",
            "description": "Get all pending tasks",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Take a screenshot of the current screen",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_battery",
            "description": "Get the current battery level",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "control_screen",
            "description": "Control the Mac screen — click, type, navigate apps, open websites. Use for multi-step tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Full description of what to do on screen"},
                },
                "required": ["task"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Save an important fact about Elnatan — phone numbers, preferences, schedules, anything he tells you to remember.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Category like 'contact', 'preference', 'schedule', 'goal'"},
                    "key": {"type": "string", "description": "Short label, e.g. 'Mom phone', 'wake up time'"},
                    "value": {"type": "string", "description": "The value to remember"},
                },
                "required": ["category", "key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name, e.g. 'Madison, SD'"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_volume",
            "description": "Set the Mac system volume (0-100) or mute/unmute",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "description": "Volume level 0-100, or -1 to toggle mute"},
                },
                "required": ["level"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_whatsapp",
            "description": "Send a WhatsApp message to a phone number or contact",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Phone number with country code e.g. +251911202059"},
                    "message": {"type": "string", "description": "Message to send"},
                },
                "required": ["to", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_news",
            "description": "Get the latest news relevant to Elnatan — Africa, business, tech, ecommerce",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "focus_mode",
            "description": "Enable or disable focus mode — monitors for distracting websites and warns via Telegram",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["on", "off"], "description": "Turn focus mode on or off"},
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_goal",
            "description": "Add a new long-term goal",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "The goal"},
                    "category": {"type": "string", "description": "Category e.g. business, health, personal"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_habit",
            "description": "Add a new daily habit to track",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "The habit to track daily"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_habit",
            "description": "Mark a habit as done for today",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "The habit to mark complete"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_habits",
            "description": "Get today's habit completion status",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_goals",
            "description": "Get all active goals",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_calendar",
            "description": "Check calendar events for today or a specific date",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date to check in YYYY-MM-DD format. Leave empty for today."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "morning_briefing",
            "description": "Generate a morning briefing with real weather, calendar, tasks, and habits data. Use this whenever the user asks for a briefing, morning update, or daily summary.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "Set a reminder or alarm to notify Elnatan at a specific time with a message",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "What to remind him about"},
                    "minutes": {"type": "integer", "description": "Minutes from now to trigger the reminder"},
                },
                "required": ["message", "minutes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_screen",
            "description": "Take a screenshot and read all text visible on screen using OCR. Use when asked 'what's on my screen' or to read something visible.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_price",
            "description": "Get the current price of a cryptocurrency or stock ticker",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Crypto name (bitcoin, ethereum, solana) or stock ticker (AAPL, TSLA, NVDA)"},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": "Create an event in Apple Calendar",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Event title"},
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                    "time": {"type": "string", "description": "Time in HH:MM 24h format, e.g. 14:30"},
                    "duration_minutes": {"type": "integer", "description": "Duration in minutes (default 60)"},
                },
                "required": ["title", "date", "time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "control_music",
            "description": "Control Apple Music — play, pause, skip to next or previous track",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["play", "pause", "next", "prev", "toggle"], "description": "Music action"},
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_code",
            "description": "Execute code in any programming language and return the output. Use this whenever the user asks to run code, test something, calculate something with code, or when you write code that should be executed. Supported: python, javascript, bash, typescript, go, rust, ruby, r, swift, c, cpp, sql.",
            "parameters": {
                "type": "object",
                "properties": {
                    "language": {"type": "string", "description": "Programming language: python, javascript, bash, typescript, go, rust, ruby, r, swift, c, cpp, sql"},
                    "code": {"type": "string", "description": "The complete code to execute"},
                    "timeout": {"type": "integer", "description": "Max execution time in seconds (default 30)", "default": 30},
                    "cwd": {"type": "string", "description": "Working directory path (optional)"},
                },
                "required": ["language", "code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run any shell command on the Mac and return the output. Use for: installing packages, running scripts, git commands, checking system info, npm/pip/brew commands, starting/stopping processes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to run"},
                    "cwd": {"type": "string", "description": "Working directory path (optional)"},
                    "timeout": {"type": "integer", "description": "Max time in seconds (default 30)", "default": 30},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of any file on the Mac. Use to read source code, text files, config files, logs, anything.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path (supports ~ for home directory)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to an existing file (overwrites completely). Use to update source code, config files, documents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write to"},
                    "content": {"type": "string", "description": "Complete file content"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new file with content. Creates any missing parent directories automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to create"},
                    "content": {"type": "string", "description": "File content (can be empty string)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file or directory. Only use when the user explicitly asks to delete something.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File or directory path to delete"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_file",
            "description": "Move or rename a file or directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "src": {"type": "string", "description": "Source path"},
                    "dst": {"type": "string", "description": "Destination path"},
                },
                "required": ["src", "dst"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and folders in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (default: home directory)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "make_directory",
            "description": "Create a new directory (and all parent directories needed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to create"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scaffold_project",
            "description": "Create a complete software project from scratch — folder structure, boilerplate code, dependencies installed, git initialized. Use when asked to 'build a project', 'create a new app', 'start a React app', etc. Supported types: react, nextjs, vue, svelte, html, flask, fastapi, express, django, expo, python_cli.",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "description": "Project type: react | nextjs | vue | svelte | html | flask | fastapi | express | django | expo | python_cli"},
                    "name": {"type": "string", "description": "Project name (becomes the folder name)"},
                    "path": {"type": "string", "description": "Parent directory to create the project in (default: ~/Desktop)", "default": "~/Desktop"},
                    "features": {"type": "array", "items": {"type": "string"}, "description": "Optional feature flags (e.g. ['typescript', 'tailwind', 'auth'])"},
                },
                "required": ["type", "name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_in_browser",
            "description": "Open a URL or local HTML file in Chrome. Use after scaffolding a frontend project or when the user asks to preview or open something in the browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "URL (https://...) or absolute local file path (e.g. /Users/elnatananbelu/Desktop/site/index.html) to open in Chrome"},
                },
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Show git status of a project — staged, unstaged, untracked files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Project directory path (default: current dir)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_add",
            "description": "Stage files for commit. Use 'files': '.' to stage everything.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Project directory path"},
                    "files": {"type": "string", "description": "Files to stage: '.' for all, or specific file paths", "default": "."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Commit staged changes with a message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Project directory path"},
                    "message": {"type": "string", "description": "Commit message"},
                },
                "required": ["path", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_push",
            "description": "Push commits to a remote repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Project directory path"},
                    "remote": {"type": "string", "description": "Remote name (default: origin)", "default": "origin"},
                    "branch": {"type": "string", "description": "Branch to push (default: current branch)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_branch",
            "description": "Manage git branches — list, create, switch, or delete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Project directory path"},
                    "action": {"type": "string", "enum": ["list", "create", "switch", "delete"], "description": "Action to perform", "default": "list"},
                    "name": {"type": "string", "description": "Branch name (required for create/switch/delete)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "Show recent commit history for a project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Project directory path"},
                    "n": {"type": "integer", "description": "Number of commits to show (default: 10)", "default": 10},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "Show what changed in a project — unstaged by default, or staged if specified.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Project directory path"},
                    "staged": {"type": "boolean", "description": "Show staged (cached) diff instead of unstaged", "default": False},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_clone",
            "description": "Clone a git repository to a local directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Repository URL to clone"},
                    "path": {"type": "string", "description": "Directory to clone into (default: ~/Desktop)"},
                    "name": {"type": "string", "description": "Local folder name (optional, defaults to repo name)"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_init",
            "description": "Initialize a new git repository in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory to initialize as a git repo"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_create_github_repo",
            "description": "Create a GitHub repository and push the local project to it. Requires gh CLI to be authenticated.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "GitHub repo name"},
                    "path": {"type": "string", "description": "Local project directory to push"},
                    "private": {"type": "boolean", "description": "Make repo private (default: true)", "default": True},
                },
                "required": ["name", "path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_data",
            "description": "Load and analyze a data file (CSV, Excel, JSON, SQLite). Returns: shape, column types, missing values, descriptive stats, correlations, and a data preview. Optionally answers a specific question about the data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the data file (CSV, .xlsx, .json, .sqlite, .tsv)"},
                    "question": {"type": "string", "description": "Optional specific question to answer about the data (e.g. 'what is the average revenue?')"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_data",
            "description": "Run a SQL query against any data file (CSV, Excel, JSON). The file is loaded as a table called 'data' in an in-memory SQLite database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the data file"},
                    "sql": {"type": "string", "description": "SQL query to run (table name is always 'data')"},
                },
                "required": ["path", "sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_chart",
            "description": "Generate a chart from a data file and display it in the HUD. Supported types: line, bar, scatter, pie, histogram, heatmap, box, area, candlestick. Chart is saved to ~/Desktop/jarvis_charts/ and shown as a panel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_path": {"type": "string", "description": "Path to the data file (CSV, Excel, JSON)"},
                    "chart_type": {"type": "string", "description": "Chart type: line | bar | scatter | pie | histogram | heatmap | box | area | candlestick"},
                    "x": {"type": "string", "description": "Column name for x-axis (auto-selected if omitted)"},
                    "y": {"type": "string", "description": "Column name for y-axis / values (auto-selected if omitted)"},
                    "title": {"type": "string", "description": "Chart title (auto-generated if omitted)"},
                    "hue": {"type": "string", "description": "Column to use for color grouping (optional)"},
                    "bins": {"type": "integer", "description": "Number of bins for histogram (default: 30)"},
                    "top_n": {"type": "integer", "description": "Limit bar/pie to top N entries (optional)"},
                },
                "required": ["data_path", "chart_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_charts",
            "description": "List all charts that have been saved to ~/Desktop/jarvis_charts/.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_report",
            "description": "Generate a professional report (PDF, Excel, or HTML) with charts and data. Saves to ~/Desktop/jarvis_reports/. Use for monthly business reports, analysis summaries, investor updates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Report title"},
                    "sections": {
                        "type": "array",
                        "description": "Report sections. Each section has 'heading' (string), 'content' (text), and optionally 'chart' (path to a chart PNG).",
                        "items": {
                            "type": "object",
                            "properties": {
                                "heading": {"type": "string"},
                                "content": {"type": "string"},
                                "chart": {"type": "string", "description": "Path to chart PNG (optional)"},
                            },
                        },
                    },
                    "output_format": {"type": "string", "description": "Output format: pdf | excel | html (default: pdf)", "default": "pdf"},
                    "data_path": {"type": "string", "description": "Optional data file to auto-include an analysis section"},
                    "output_path": {"type": "string", "description": "Custom output path (optional — defaults to ~/Desktop/jarvis_reports/)"},
                },
                "required": ["title"],
            },
        },
    },

    # ── PHASE 4: BUSINESS OS ─────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "add_business",
            "description": "Register a new business under the Nexel empire. Use when told 'add Addis Market' or 'register a new business'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Business name"},
                    "type": {"type": "string", "description": "Business type (marketplace, saas, service, product, etc.)"},
                    "stage": {"type": "string", "description": "Stage: idea | mvp | growth | scaling | profitable", "default": "idea"},
                    "description": {"type": "string", "description": "What the business does"},
                    "revenue_model": {"type": "string", "description": "How it makes money"},
                    "founded": {"type": "string", "description": "Founding date (YYYY-MM-DD)"},
                    "mrr": {"type": "number", "description": "Current monthly recurring revenue in USD", "default": 0},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_business",
            "description": "Update an existing business's details — stage, MRR, description, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Business name"},
                    "stage": {"type": "string", "description": "New stage"},
                    "mrr": {"type": "number", "description": "New MRR"},
                    "description": {"type": "string"},
                    "revenue_model": {"type": "string"},
                    "type": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_business",
            "description": "Get the full profile of a business — team, goals, KPIs, stage, financials summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Business name"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "nexel_overview",
            "description": "Show the full Nexel empire overview — all businesses, their stage, MRR, and combined P&L.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_team_member",
            "description": "Add a team member to a business.",
            "parameters": {
                "type": "object",
                "properties": {
                    "business": {"type": "string"},
                    "name": {"type": "string", "description": "Person's name"},
                    "role": {"type": "string", "description": "Their role"},
                },
                "required": ["business", "name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_business_goal",
            "description": "Add an active goal or milestone to a business.",
            "parameters": {
                "type": "object",
                "properties": {
                    "business": {"type": "string"},
                    "title": {"type": "string", "description": "Goal title"},
                    "description": {"type": "string"},
                    "target_date": {"type": "string", "description": "Target completion date (YYYY-MM-DD)"},
                },
                "required": ["business", "title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_goal",
            "description": "Mark a business goal as completed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "business": {"type": "string"},
                    "title": {"type": "string", "description": "Goal title (partial match)"},
                },
                "required": ["business", "title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_kpi",
            "description": "Define a KPI and its target for a business. Use for: vendors onboarded, daily active users, GMV, delivery rate, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "business": {"type": "string"},
                    "kpi_name": {"type": "string", "description": "KPI name (e.g. 'Vendors Onboarded', 'DAU', 'GMV')"},
                    "target": {"type": "number", "description": "Target value"},
                    "unit": {"type": "string", "description": "Unit label (e.g. 'vendors', 'users', 'USD')"},
                    "period": {"type": "string", "description": "Tracking period: daily | weekly | monthly", "default": "monthly"},
                    "current": {"type": "number", "description": "Current value (default 0)", "default": 0},
                },
                "required": ["business", "kpi_name", "target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_kpi",
            "description": "Update the current value of a KPI for a business.",
            "parameters": {
                "type": "object",
                "properties": {
                    "business": {"type": "string"},
                    "kpi_name": {"type": "string"},
                    "current": {"type": "number", "description": "New current value"},
                },
                "required": ["business", "kpi_name", "current"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kpi_report",
            "description": "Show all KPIs for a business with progress bars and on-target status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "business": {"type": "string"},
                },
                "required": ["business"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_contact",
            "description": "Add a business contact to the CRM — investor, vendor, customer, partner, or advisor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "business": {"type": "string", "description": "Business this contact is associated with"},
                    "name": {"type": "string"},
                    "role": {"type": "string", "description": "investor | vendor | customer | partner | advisor"},
                    "company": {"type": "string"},
                    "email": {"type": "string"},
                    "phone": {"type": "string"},
                    "notes": {"type": "string"},
                    "pipeline_stage": {"type": "string", "description": "lead | contacted | negotiating | closed", "default": "lead"},
                },
                "required": ["business", "name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_interaction",
            "description": "Log a meeting, call, email, or message with a business contact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_name": {"type": "string"},
                    "interaction_type": {"type": "string", "description": "meeting | call | email | message | deal"},
                    "notes": {"type": "string", "description": "What was discussed"},
                    "business": {"type": "string", "description": "Related business (optional)"},
                    "date_str": {"type": "string", "description": "Date (YYYY-MM-DD, default: today)"},
                },
                "required": ["contact_name", "interaction_type", "notes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_pipeline",
            "description": "Move a contact to a new pipeline stage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_name": {"type": "string"},
                    "stage": {"type": "string", "description": "lead | contacted | negotiating | closed | churned"},
                },
                "required": ["contact_name", "stage"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_follow_up",
            "description": "Set a follow-up reminder date for a contact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_name": {"type": "string"},
                    "follow_up_date": {"type": "string", "description": "Date to follow up (YYYY-MM-DD)"},
                },
                "required": ["contact_name", "follow_up_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "show_pipeline",
            "description": "Show the full deal pipeline — all contacts grouped by stage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "business": {"type": "string", "description": "Filter by business (optional — shows all if omitted)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "follow_ups_due",
            "description": "Show contacts who need a follow-up — overdue follow-ups or not contacted in N days.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days_since": {"type": "integer", "description": "Flag contacts not touched in this many days (default: 14)", "default": 14},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "contact_history",
            "description": "Show the full interaction history with a contact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_name": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["contact_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_revenue",
            "description": "Log a revenue entry for a business.",
            "parameters": {
                "type": "object",
                "properties": {
                    "business": {"type": "string"},
                    "amount": {"type": "number", "description": "Amount in USD"},
                    "category": {"type": "string", "description": "Revenue category (e.g. subscription, commission, one-time)"},
                    "date_str": {"type": "string", "description": "Date (YYYY-MM-DD, default: today)"},
                    "notes": {"type": "string"},
                },
                "required": ["business", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_expense",
            "description": "Log an expense for a business.",
            "parameters": {
                "type": "object",
                "properties": {
                    "business": {"type": "string"},
                    "amount": {"type": "number", "description": "Amount in USD"},
                    "category": {"type": "string", "description": "Expense category (e.g. hosting, marketing, salaries, tools)"},
                    "date_str": {"type": "string", "description": "Date (YYYY-MM-DD, default: today)"},
                    "notes": {"type": "string"},
                },
                "required": ["business", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "financial_summary",
            "description": "Show revenue, expenses, and profit for a business.",
            "parameters": {
                "type": "object",
                "properties": {
                    "business": {"type": "string"},
                    "period": {"type": "string", "description": "month | year | all (default: month)", "default": "month"},
                },
                "required": ["business"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "nexel_financials",
            "description": "Show consolidated P&L across all Nexel businesses.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cash_flow",
            "description": "Show cash flow projection for a business — average burn, net monthly, status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "business": {"type": "string"},
                },
                "required": ["business"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "business_briefing",
            "description": "Generate the full business briefing — all active businesses, KPI status, follow-ups due, and Nexel P&L snapshot. Use every morning or when asked for a business update.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tax_estimate",
            "description": "Calculate estimated taxes for a business based on annual profit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "business": {"type": "string"},
                    "tax_rate_pct": {"type": "number", "description": "Tax rate percentage (default: 30)", "default": 30},
                },
                "required": ["business"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "export_for_accountant",
            "description": "Export all financial records for a business to an Excel file for an accountant.",
            "parameters": {
                "type": "object",
                "properties": {
                    "business": {"type": "string"},
                    "output_path": {"type": "string", "description": "Custom save path (optional)"},
                },
                "required": ["business"],
            },
        },
    },

    # ── PHASE 5: MARKETING ────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "generate_ad_copy",
            "description": "Generate ad copy variants for a product on a specific platform. Use when asked to write ads, marketing copy, or campaign content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product": {"type": "string", "description": "What you're advertising"},
                    "platform": {"type": "string", "description": "Platform: meta | tiktok | google | twitter | linkedin | telegram | instagram"},
                    "audience": {"type": "string", "description": "Target audience description"},
                    "tone": {"type": "string", "description": "Tone: confident | friendly | urgent | professional", "default": "confident"},
                    "goal": {"type": "string", "description": "Campaign goal: sign-ups | sales | awareness | downloads", "default": "sign-ups"},
                    "variants": {"type": "integer", "description": "Number of variants to generate (default: 3)", "default": 3},
                    "context": {"type": "string", "description": "Additional context about the product or campaign"},
                },
                "required": ["product", "platform"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "social_media_calendar",
            "description": "Generate a weekly social media content calendar with ready-to-post captions and hashtags.",
            "parameters": {
                "type": "object",
                "properties": {
                    "business": {"type": "string"},
                    "platform": {"type": "string", "description": "instagram | twitter | tiktok | linkedin | telegram", "default": "instagram"},
                    "posts": {"type": "integer", "description": "Number of posts to generate (default: 7)", "default": 7},
                    "content_pillars": {"type": "string", "description": "Content pillars to cover (optional)"},
                    "brand_voice": {"type": "string", "description": "Brand voice description (optional)"},
                },
                "required": ["business"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "campaign_strategy",
            "description": "Generate a complete marketing campaign strategy — concept, channels, timeline, metrics, A/B tests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "business": {"type": "string"},
                    "goal": {"type": "string", "description": "Campaign goal (e.g. 'get 100 vendor sign-ups', 'launch in Addis Ababa')"},
                    "budget_usd": {"type": "number", "description": "Campaign budget in USD (0 if not specified)", "default": 0},
                    "duration_days": {"type": "integer", "description": "Campaign duration in days", "default": 30},
                    "channels": {"type": "string", "description": "Channels to use (optional — auto-suggested if omitted)"},
                    "context": {"type": "string", "description": "Additional campaign context"},
                },
                "required": ["business", "goal"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pitch_writer",
            "description": "Write an investor pitch, vendor proposal, client proposal, one-pager, or executive summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "business": {"type": "string"},
                    "type": {"type": "string", "description": "investor | vendor | partner | client | one_pager | executive_summary", "default": "investor"},
                    "ask": {"type": "string", "description": "What you're asking for (funding amount, partnership terms, etc.)"},
                    "context": {"type": "string", "description": "Additional context about the business or deal"},
                },
                "required": ["business"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "market_research",
            "description": "Research a market, trend, or topic using web search and synthesize the findings into a sharp analysis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Market, trend, or topic to research"},
                    "business": {"type": "string", "description": "Related business for context (optional)"},
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "strategic_review",
            "description": "Generate a strategic review for a business using real KPI, financial, and market data. Use when asked 'should I do X?', 'what's my strategic situation?', or 'what should I focus on?'",
            "parameters": {
                "type": "object",
                "properties": {
                    "business": {"type": "string"},
                    "question": {"type": "string", "description": "Specific strategic question to answer (optional)"},
                },
                "required": ["business"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "competitor_scan",
            "description": "Research a specific competitor and return intelligence on their pricing, features, funding, and how to compete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "business": {"type": "string", "description": "Your business"},
                    "competitor": {"type": "string", "description": "Competitor name or description"},
                },
                "required": ["business", "competitor"],
            },
        },
    },

    # ── PHASE 6: LIFE OS ─────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "log_health",
            "description": "Log a health or fitness metric — workout, weight, sleep, steps, meal, heart rate, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "description": "Type: workout | weight | sleep | steps | meal | water | hr | bench | squat | etc."},
                    "value": {"type": "number", "description": "Numeric value"},
                    "unit": {"type": "string", "description": "Unit (lbs, hours, steps, reps, kcal, etc.)"},
                    "notes": {"type": "string", "description": "Additional notes"},
                    "date_str": {"type": "string", "description": "Date (YYYY-MM-DD, default: today)"},
                },
                "required": ["type", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "health_summary",
            "description": "Show health data summary for the past N days. Can filter by type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "description": "Filter by type (optional — shows all if omitted)"},
                    "days": {"type": "integer", "description": "Days to look back (default: 7)", "default": 7},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_personal_expense",
            "description": "Log a personal expense (separate from business expenses).",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "category": {"type": "string", "description": "food | transport | entertainment | shopping | subscriptions | etc."},
                    "notes": {"type": "string"},
                    "date_str": {"type": "string"},
                },
                "required": ["amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_personal_income",
            "description": "Log personal income (job, freelance, family, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "category": {"type": "string"},
                    "notes": {"type": "string"},
                    "date_str": {"type": "string"},
                },
                "required": ["amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "personal_finance_summary",
            "description": "Show personal income vs expenses breakdown.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {"type": "string", "description": "month | year | all", "default": "month"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_book",
            "description": "Add a book to the reading list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "author": {"type": "string"},
                    "status": {"type": "string", "description": "want | reading | done", "default": "want"},
                    "notes": {"type": "string"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_book",
            "description": "Update reading status or rating for a book.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Book title (partial match)"},
                    "status": {"type": "string", "description": "want | reading | done | dropped"},
                    "rating": {"type": "integer", "description": "Rating out of 5"},
                    "notes": {"type": "string"},
                },
                "required": ["title", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reading_list",
            "description": "Show the reading list — currently reading, want to read, finished.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter: want | reading | done (optional — shows all if omitted)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_important_date",
            "description": "Save an important date — birthday, anniversary, deadline. JARVIS alerts 3 days before.",
            "parameters": {
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Person's name"},
                    "event_type": {"type": "string", "description": "birthday | anniversary | deadline | other"},
                    "date_str": {"type": "string", "description": "Date (YYYY-MM-DD)"},
                    "notes": {"type": "string"},
                },
                "required": ["person", "event_type", "date_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "upcoming_dates",
            "description": "Show upcoming important dates — birthdays, anniversaries, deadlines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Days ahead to check (default: 30)", "default": 30},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_relationship",
            "description": "Log a conversation or interaction with someone important to you.",
            "parameters": {
                "type": "object",
                "properties": {
                    "person": {"type": "string"},
                    "notes": {"type": "string", "description": "What was discussed or how they're doing"},
                    "date_str": {"type": "string"},
                },
                "required": ["person", "notes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_learning",
            "description": "Log a learning session — book, course, skill practice, video, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill": {"type": "string", "description": "Skill or subject area"},
                    "type": {"type": "string", "description": "session | book | course | video | practice", "default": "session"},
                    "title": {"type": "string", "description": "Title of what you studied"},
                    "notes": {"type": "string", "description": "Key takeaways or progress"},
                },
                "required": ["skill"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "learning_summary",
            "description": "Show learning activity for the past N days.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "default": 7},
                },
                "required": [],
            },
        },
    },

    # ── PHASE 7: INTELLIGENCE ─────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "Search all past conversations for any topic, person, or event. Use when asked 'what did we discuss about X?', 'when did I mention Y?', 'what was that thing about Z?'",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for"},
                    "limit": {"type": "integer", "description": "Max results (default: 10)", "default": 10},
                    "days_back": {"type": "integer", "description": "Limit to past N days (0 = all time)", "default": 0},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_timeline",
            "description": "Show how a topic evolved over time in conversation history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "days": {"type": "integer", "default": 30},
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_patterns",
            "description": "Analyze conversation patterns to detect focus areas, procrastination signals, silent days, and topic distribution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Days to analyze (default: 30)", "default": 30},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "proactive_scan",
            "description": "Scan the web for news and intel relevant to Elnatan's businesses and interests — Ethiopian e-commerce, competitors, market moves.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topics": {"type": "array", "items": {"type": "string"}, "description": "Custom topics to scan (optional — uses defaults if omitted)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "weekly_strategy_checkin",
            "description": "Full weekly strategic review — pulls all business data, life OS, patterns, and market intel. Use every Monday or when asked for a weekly check-in.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "decision_framework",
            "description": "Build a structured decision framework for a hard choice. Options, pros/cons, risks, JARVIS recommendation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The decision to make"},
                    "context": {"type": "string", "description": "Relevant context"},
                    "options": {"type": "string", "description": "Options being considered (optional)"},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_decision",
            "description": "Record a decision that was made — for tracking and learning over time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "chosen": {"type": "string", "description": "What was decided"},
                    "reasoning": {"type": "string", "description": "Why this was chosen"},
                },
                "required": ["question", "chosen"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_decision",
            "description": "Record the outcome of a past decision — what happened after you made that call.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The original question (partial match)"},
                    "outcome": {"type": "string", "description": "What actually happened"},
                },
                "required": ["question", "outcome"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "decision_history",
            "description": "Show all logged decisions and their outcomes.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


def execute_tool(name: str, args: dict) -> str:
    """Execute a tool call and return the result string."""
    try:
        if name == "send_email":
            from control.email import send_email
            return send_email(args["to"], args.get("subject", "From JARVIS"), args["body"])

        elif name == "send_imessage":
            from control.messages import send_imessage
            return send_imessage(args["contact"], args["message"])

        elif name == "read_emails":
            from control.email import read_emails
            return read_emails(args.get("count", 5))

        elif name == "open_app":
            import subprocess
            subprocess.Popen(["open", "-a", args["app"]])
            return f"Opened {args['app']}."

        elif name == "web_search":
            from control.search import web_search
            return web_search(args["query"])

        elif name == "add_task":
            from memory.life import add_task
            return add_task(args["title"], priority=args.get("priority", "medium"))

        elif name == "get_tasks":
            from memory.life import get_tasks
            return get_tasks()

        elif name == "take_screenshot":
            from control.mac import screenshot
            import time
            time.sleep(1.5)  # wait for browser/app to finish loading
            path = screenshot()
            return f"Screenshot taken. [SHOW: {path}] Tell me what you see on screen and whether it looks correct."

        elif name == "get_battery":
            from control.mac import get_battery
            return f"Battery: {get_battery()}"

        elif name == "control_screen":
            from control.agent import get_agent
            steps = []
            result = get_agent().run(args["task"], on_progress=lambda s, a: steps.append(f"[{s}] {a}"))
            return result

        elif name == "remember":
            from memory.memory import save_fact
            save_fact(args["category"], args["key"], args["value"])
            return f"Remembered: [{args['category']}] {args['key']} = {args['value']}"

        elif name == "get_weather":
            return _get_weather(args["city"])

        elif name == "set_volume":
            import subprocess
            level = int(args["level"])
            if level == -1:
                subprocess.run(['osascript', '-e', 'set volume output muted not (output muted of (get volume settings))'])
                return "Volume toggled."
            subprocess.run(['osascript', '-e', f'set volume output volume {max(0, min(100, level))}'])
            return f"Volume set to {level}."

        elif name == "send_whatsapp":
            from control.whatsapp import send_whatsapp
            return send_whatsapp(args["to"], args["message"])

        elif name == "get_news":
            from brain.news import get_news
            return get_news()

        elif name == "focus_mode":
            from control.focus import enable_focus, disable_focus
            return enable_focus() if args.get("action") == "on" else disable_focus()

        elif name == "add_goal":
            from memory.goals import add_goal
            return add_goal(args["title"], args.get("category", "general"))

        elif name == "add_habit":
            from memory.goals import add_habit
            return add_habit(args["title"])

        elif name == "check_habit":
            from memory.goals import check_habit
            return check_habit(args["title"])

        elif name == "get_habits":
            from memory.goals import get_habits_status
            return get_habits_status()

        elif name == "get_goals":
            from memory.goals import get_goals
            return get_goals()

        elif name == "check_calendar":
            from control.calendar import get_events_str
            from datetime import date
            d = None
            if args.get("date"):
                try:
                    d = date.fromisoformat(args["date"])
                except Exception:
                    pass
            return get_events_str(d)

        elif name == "morning_briefing":
            from brain.briefing import generate_briefing
            return generate_briefing()

        elif name == "set_reminder":
            import threading, subprocess
            msg = args["message"]
            mins = max(1, int(args.get("minutes", 5)))
            def _fire():
                subprocess.run([
                    "osascript", "-e",
                    f'display notification "{msg}" with title "JARVIS REMINDER" sound name "Ping"'
                ])
            threading.Timer(mins * 60, _fire).start()
            return f"Reminder set for {mins} minute{'s' if mins != 1 else ''}: {msg}"

        elif name == "read_screen":
            import subprocess, tempfile, os
            tmp = tempfile.mktemp(suffix=".png")
            subprocess.run(["screencapture", "-x", tmp], timeout=5)
            try:
                import pytesseract
                from PIL import Image
                text = pytesseract.image_to_string(Image.open(tmp)).strip()
                os.unlink(tmp)
                return text[:2000] if text else "No readable text found on screen."
            except Exception as e:
                try: os.unlink(tmp)
                except: pass
                return f"OCR error: {e}"

        elif name == "get_price":
            import urllib.request, json
            symbol = args["symbol"].strip().lower()
            # Try CoinGecko for crypto
            COIN_IDS = {
                "btc": "bitcoin", "bitcoin": "bitcoin",
                "eth": "ethereum", "ethereum": "ethereum",
                "sol": "solana", "solana": "solana",
                "bnb": "binancecoin", "xrp": "ripple",
                "doge": "dogecoin", "ada": "cardano",
            }
            coin_id = COIN_IDS.get(symbol)
            if coin_id:
                url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true"
                with urllib.request.urlopen(url, timeout=8) as r:
                    d = json.loads(r.read())
                price = d[coin_id]["usd"]
                change = d[coin_id].get("usd_24h_change", 0)
                return f"{coin_id.title()}: ${price:,.2f} ({change:+.2f}% 24h)"
            # Try Yahoo Finance for stocks
            ticker = symbol.upper()
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                d = json.loads(r.read())
            meta = d["chart"]["result"][0]["meta"]
            price = meta["regularMarketPrice"]
            prev = meta.get("chartPreviousClose", price)
            change_pct = ((price - prev) / prev * 100) if prev else 0
            return f"{ticker}: ${price:,.2f} ({change_pct:+.2f}%)"

        elif name == "create_calendar_event":
            import subprocess
            title = args["title"].replace('"', "'")
            date_str = args["date"]
            time_str = args["time"]
            duration = args.get("duration_minutes", 60)
            from datetime import datetime, timedelta
            start_dt = datetime.fromisoformat(f"{date_str}T{time_str}:00")
            end_dt = start_dt + timedelta(minutes=duration)
            start_apple = start_dt.strftime("%B %d, %Y at %I:%M %p")
            end_apple = end_dt.strftime("%B %d, %Y at %I:%M %p")
            script = f'''tell application "Calendar"
    tell calendar "Home"
        make new event with properties {{summary:"{title}", start date:date "{start_apple}", end date:date "{end_apple}"}}
    end tell
end tell'''
            subprocess.run(["osascript", "-e", script], timeout=6)
            return f"Event created: {title} on {date_str} at {time_str}"

        elif name == "control_music":
            import subprocess
            action = args.get("action", "toggle")
            scripts = {
                "play":   'tell application "Music" to play',
                "pause":  'tell application "Music" to pause',
                "next":   'tell application "Music" to next track',
                "prev":   'tell application "Music" to previous track',
                "toggle": 'tell application "Music" to playpause',
            }
            if action in scripts:
                subprocess.run(["osascript", "-e", scripts[action]], timeout=3)
            return {"play": "Playing.", "pause": "Paused.", "next": "Next track.",
                    "prev": "Previous track.", "toggle": "Toggled."}.get(action, "Done.")

        elif name == "execute_code":
            from control.code_executor import execute_code, format_execution_result
            result = execute_code(
                language=args["language"],
                code=args["code"],
                timeout=int(args.get("timeout", 30)),
                cwd=args.get("cwd"),
            )
            return format_execution_result(result, args["language"])

        elif name == "run_shell":
            from control.code_executor import run_shell
            result = run_shell(
                command=args["command"],
                cwd=args.get("cwd"),
                timeout=int(args.get("timeout", 30)),
            )
            if result.get("error"):
                return f"Error: {result['error']}"
            out = []
            if result["stdout"]:
                out.append(result["stdout"])
            if result["stderr"]:
                out.append(f"stderr: {result['stderr']}")
            if not out:
                return f"Done. Exit code: {result['exit_code']}"
            return "\n".join(out)

        elif name == "read_file":
            from control.files import read_file
            return read_file(args["path"])

        elif name == "write_file":
            from control.files import write_file
            return write_file(args["path"], args["content"])

        elif name == "create_file":
            from control.files import create_file
            return create_file(args["path"], args.get("content", ""))

        elif name == "delete_file":
            from control.files import delete_file
            return delete_file(args["path"])

        elif name == "move_file":
            from control.files import move_file
            return move_file(args["src"], args["dst"])

        elif name == "list_directory":
            from control.files import list_directory
            return list_directory(args.get("path", "."))

        elif name == "make_directory":
            from control.files import make_directory
            return make_directory(args["path"])

        elif name == "scaffold_project":
            from control.scaffold import scaffold_project
            return scaffold_project(
                type=args["type"],
                name=args["name"],
                path=args.get("path", "~/Desktop"),
                features=args.get("features"),
            )

        elif name == "open_in_browser":
            from control.browser import open_in_browser
            target = args.get("target") or args.get("url") or args.get("path") or ""
            return open_in_browser(target)

        elif name == "git_status":
            from control.git_ops import git_status
            return git_status(args.get("path", "."))

        elif name == "git_add":
            from control.git_ops import git_add
            return git_add(args.get("path", "."), args.get("files", "."))

        elif name == "git_commit":
            from control.git_ops import git_commit
            return git_commit(args.get("path", "."), args.get("message", "update"))

        elif name == "git_push":
            from control.git_ops import git_push
            return git_push(args.get("path", "."), args.get("remote", "origin"), args.get("branch", ""))

        elif name == "git_branch":
            from control.git_ops import git_branch
            return git_branch(args.get("path", "."), args.get("name", ""), args.get("action", "list"))

        elif name == "git_log":
            from control.git_ops import git_log
            return git_log(args.get("path", "."), args.get("n", 10))

        elif name == "git_diff":
            from control.git_ops import git_diff
            return git_diff(args.get("path", "."), args.get("staged", False))

        elif name == "git_clone":
            from control.git_ops import git_clone
            return git_clone(args["url"], args.get("path", "~/Desktop"), args.get("name", ""))

        elif name == "git_init":
            from control.git_ops import git_init
            return git_init(args.get("path", "."))

        elif name == "git_create_github_repo":
            from control.git_ops import git_create_github_repo
            return git_create_github_repo(args["name"], args.get("private", True), args.get("path", "."))

        elif name == "analyze_data":
            from control.analyst import analyze_data
            return analyze_data(args["path"], args.get("question"))

        elif name == "query_data":
            from control.analyst import query_data
            return query_data(args["path"], args["sql"])

        elif name == "generate_chart":
            from control.charts import generate_chart
            result = generate_chart(
                data_path=args["data_path"],
                chart_type=args["chart_type"],
                x=args.get("x"),
                y=args.get("y"),
                title=args.get("title"),
                hue=args.get("hue"),
                bins=args.get("bins", 30),
                top_n=args.get("top_n"),
            )
            # If it's a file path (success), return the [CHART:] tag for HUD rendering
            if result.endswith(".png") and not result.startswith("Chart") and not result.startswith("Could"):
                return f"Chart saved to {result}\n[CHART: {result}]"
            return result

        elif name == "list_charts":
            from control.charts import list_charts
            return list_charts()

        elif name == "generate_report":
            from control.reports import generate_report
            result = generate_report(
                title=args["title"],
                sections=args.get("sections", []),
                output_format=args.get("output_format", "pdf"),
                output_path=args.get("output_path"),
                data_path=args.get("data_path"),
            )
            return f"Report saved to {result}"

        # ── PHASE 4: BUSINESS OS ─────────────────────────────────────────────
        elif name == "add_business":
            from control.business_tools import tool_add_business
            return tool_add_business(
                args["name"], args.get("type",""), args.get("stage","idea"),
                args.get("description",""), args.get("revenue_model",""),
                args.get("founded",""), args.get("mrr",0)
            )

        elif name == "update_business":
            from control.business_tools import tool_update_business
            n = args.pop("name")
            return tool_update_business(n, **args)

        elif name == "get_business":
            from control.business_tools import tool_get_business
            return tool_get_business(args["name"])

        elif name == "nexel_overview":
            from control.business_tools import tool_nexel_overview
            return tool_nexel_overview()

        elif name == "add_team_member":
            from control.business_tools import tool_add_team_member
            return tool_add_team_member(args["business"], args["name"], args.get("role",""))

        elif name == "add_business_goal":
            from control.business_tools import tool_add_goal
            return tool_add_goal(args["business"], args["title"], args.get("description",""), args.get("target_date",""))

        elif name == "complete_goal":
            from control.business_tools import tool_complete_goal
            return tool_complete_goal(args["business"], args["title"])

        elif name == "set_kpi":
            from control.business_tools import tool_set_kpi
            return tool_set_kpi(args["business"], args["kpi_name"], args["target"],
                                args.get("unit",""), args.get("period","monthly"), args.get("current",0))

        elif name == "update_kpi":
            from control.business_tools import tool_update_kpi
            return tool_update_kpi(args["business"], args["kpi_name"], args["current"])

        elif name == "kpi_report":
            from control.business_tools import tool_kpi_report
            return tool_kpi_report(args["business"])

        elif name == "add_contact":
            from control.business_tools import tool_add_contact
            return tool_add_contact(args["business"], args["name"], args.get("role",""),
                                    args.get("company",""), args.get("email",""), args.get("phone",""),
                                    args.get("notes",""), args.get("pipeline_stage","lead"))

        elif name == "log_interaction":
            from control.business_tools import tool_log_interaction
            return tool_log_interaction(args["contact_name"], args["interaction_type"], args["notes"],
                                        args.get("business",""), args.get("date_str",""))

        elif name == "update_pipeline":
            from control.business_tools import tool_update_pipeline
            return tool_update_pipeline(args["contact_name"], args["stage"])

        elif name == "set_follow_up":
            from control.business_tools import tool_set_follow_up
            return tool_set_follow_up(args["contact_name"], args["follow_up_date"])

        elif name == "show_pipeline":
            from control.business_tools import tool_show_pipeline
            return tool_show_pipeline(args.get("business",""))

        elif name == "follow_ups_due":
            from control.business_tools import tool_follow_ups_due
            return tool_follow_ups_due(args.get("days_since", 14))

        elif name == "contact_history":
            from control.business_tools import tool_contact_history
            return tool_contact_history(args["contact_name"], args.get("limit", 10))

        elif name == "log_revenue":
            from control.business_tools import tool_log_revenue
            return tool_log_revenue(args["business"], args["amount"], args.get("category",""),
                                    args.get("date_str",""), args.get("notes",""))

        elif name == "log_expense":
            from control.business_tools import tool_log_expense
            return tool_log_expense(args["business"], args["amount"], args.get("category",""),
                                    args.get("date_str",""), args.get("notes",""))

        elif name == "financial_summary":
            from control.business_tools import tool_financial_summary
            return tool_financial_summary(args["business"], args.get("period","month"))

        elif name == "nexel_financials":
            from control.business_tools import tool_nexel_financials
            return tool_nexel_financials()

        elif name == "cash_flow":
            from control.business_tools import tool_cash_flow
            return tool_cash_flow(args["business"])

        elif name == "business_briefing":
            from control.business_tools import business_briefing
            return business_briefing()

        elif name == "tax_estimate":
            from control.business_tools import tool_tax_estimate
            return tool_tax_estimate(args["business"], args.get("tax_rate_pct", 30.0))

        elif name == "export_for_accountant":
            from control.business_tools import tool_export_for_accountant
            return tool_export_for_accountant(args["business"], args.get("output_path", ""))

        # ── PHASE 5: MARKETING ────────────────────────────────────────────────
        elif name == "generate_ad_copy":
            from control.marketing import generate_ad_copy
            return generate_ad_copy(args["product"], args["platform"], args.get("audience",""),
                                    args.get("tone","confident"), args.get("goal","sign-ups"),
                                    args.get("variants",3), args.get("context",""))

        elif name == "social_media_calendar":
            from control.marketing import social_media_calendar
            return social_media_calendar(args["business"], args.get("platform","instagram"),
                                         args.get("posts",7), args.get("content_pillars",""),
                                         args.get("brand_voice",""))

        elif name == "campaign_strategy":
            from control.marketing import campaign_strategy
            return campaign_strategy(args["business"], args["goal"], args.get("budget_usd",0),
                                     args.get("duration_days",30), args.get("channels",""),
                                     args.get("context",""))

        elif name == "pitch_writer":
            from control.marketing import pitch_writer
            return pitch_writer(args["business"], args.get("type","investor"),
                                args.get("context",""), args.get("ask",""))

        elif name == "market_research":
            from control.marketing import market_research
            return market_research(args["topic"], args.get("business",""))

        elif name == "strategic_review":
            from control.marketing import strategic_review
            return strategic_review(args["business"], args.get("question",""))

        elif name == "competitor_scan":
            from control.marketing import competitor_scan
            return competitor_scan(args["business"], args["competitor"])

        # ── PHASE 6: LIFE OS ─────────────────────────────────────────────────
        elif name == "log_health":
            from control.life_os import tool_log_health
            return tool_log_health(args["type"], args["value"], args.get("unit",""),
                                   args.get("notes",""), args.get("date_str",""))

        elif name == "health_summary":
            from control.life_os import tool_health_summary
            return tool_health_summary(args.get("type",""), args.get("days",7))

        elif name == "log_personal_expense":
            from control.life_os import tool_log_personal_expense
            return tool_log_personal_expense(args["amount"], args.get("category",""),
                                             args.get("notes",""), args.get("date_str",""))

        elif name == "log_personal_income":
            from control.life_os import tool_log_personal_income
            return tool_log_personal_income(args["amount"], args.get("category",""),
                                            args.get("notes",""), args.get("date_str",""))

        elif name == "personal_finance_summary":
            from control.life_os import tool_personal_finance_summary
            return tool_personal_finance_summary(args.get("period","month"))

        elif name == "add_book":
            from control.life_os import tool_add_book
            return tool_add_book(args["title"], args.get("author",""),
                                 args.get("status","want"), args.get("notes",""))

        elif name == "update_book":
            from control.life_os import tool_update_book
            return tool_update_book(args["title"], args["status"],
                                    args.get("rating"), args.get("notes",""))

        elif name == "reading_list":
            from control.life_os import tool_reading_list
            return tool_reading_list(args.get("status",""))

        elif name == "add_important_date":
            from control.life_os import tool_add_important_date
            return tool_add_important_date(args["person"], args["event_type"],
                                           args["date_str"], args.get("notes",""))

        elif name == "upcoming_dates":
            from control.life_os import tool_upcoming_dates
            return tool_upcoming_dates(args.get("days",30))

        elif name == "log_relationship":
            from control.life_os import tool_log_relationship
            return tool_log_relationship(args["person"], args["notes"], args.get("date_str",""))

        elif name == "log_learning":
            from control.life_os import tool_log_learning
            return tool_log_learning(args["skill"], args.get("type","session"),
                                     args.get("title",""), args.get("notes",""))

        elif name == "learning_summary":
            from control.life_os import tool_learning_summary
            return tool_learning_summary(args.get("days",7))

        # ── PHASE 7: INTELLIGENCE ─────────────────────────────────────────────
        elif name == "search_memory":
            from control.intel import search_memory
            return search_memory(args["query"], args.get("limit",10), args.get("days_back",0))

        elif name == "memory_timeline":
            from control.intel import memory_timeline
            return memory_timeline(args["topic"], args.get("days",30))

        elif name == "analyze_patterns":
            from control.intel import analyze_patterns
            return analyze_patterns(args.get("days",30))

        elif name == "proactive_scan":
            from control.intel import proactive_scan
            return proactive_scan(args.get("topics"))

        elif name == "weekly_strategy_checkin":
            from control.intel import weekly_strategy_checkin
            return weekly_strategy_checkin()

        elif name == "decision_framework":
            from control.life_os import tool_decision_framework
            return tool_decision_framework(args["question"], args.get("context",""), args.get("options",""))

        elif name == "log_decision":
            from control.life_os import tool_log_decision
            return tool_log_decision(args["question"], args["chosen"], args.get("reasoning",""))

        elif name == "resolve_decision":
            from control.life_os import tool_resolve_decision
            return tool_resolve_decision(args["question"], args["outcome"])

        elif name == "decision_history":
            from control.life_os import tool_decision_history
            return tool_decision_history()

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        return f"Tool error ({name}): {e}"
