import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from control.mac import handle_command, screenshot, get_battery, get_wifi, notify
from control.email import send_email, read_emails
from control.messages import send_imessage, read_imessages
from control.search import web_search, news_search
from control.screen import analyze_screen, get_active_window
from control.docs import summarize_document

CONTROL_KEYWORDS = [
    'open ', 'close ', 'launch ', 'start ', 'quit ',
    'volume', 'mute', 'unmute', 'brightness',
    'screenshot', 'take a screenshot',
    'send email', 'read email', 'check email',
    'send message', 'text ', 'imessage',
    'play music', 'pause music', 'next track', 'next song',
    'search for', 'google ', 'go to ',
    'battery', 'wifi', 'lock screen', 'sleep',
    'empty trash', 'find file', 'create file',
    'notify', 'reminder',
    'what is on my screen', "what's on my screen", 'read my screen', 'look at my screen',
    'summarize this file', 'read this pdf', 'summarize document', 'read this file',
]

def is_control_command(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in CONTROL_KEYWORDS)

def execute(text: str):
    lower = text.lower()

    # Screenshot
    if 'screenshot' in lower:
        path = screenshot()
        return f"Screenshot saved to {path}."

    # Battery
    if 'battery' in lower:
        return f"Battery: {get_battery()}"

    # WiFi
    if 'wifi' in lower or 'wi-fi' in lower:
        return f"Connected to: {get_wifi()}"

    # Email
    if 'read email' in lower or 'check email' in lower or 'any emails' in lower:
        return read_emails(5)

    if 'send email' in lower:
        # Parse: "send email to X saying Y"
        import re
        to_match = re.search(r'to ([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]+)', text)
        if to_match:
            to = to_match.group(1)
            body = re.sub(r'send email to \S+', '', text, flags=re.IGNORECASE).strip()
            return send_email(to, "From JARVIS", body)
        return "Please specify who to send the email to."

    # iMessage
    if 'send message' in lower or 'text ' in lower:
        import re
        to_match = re.search(r'(?:text|message|send message to)\s+(\w+)', lower)
        saying_match = re.search(r'(?:saying|that|:)\s+(.+)', text, re.IGNORECASE)
        if to_match and saying_match:
            contact = to_match.group(1).capitalize()
            msg = saying_match.group(1).strip()
            return send_imessage(contact, msg)

    if 'read messages' in lower or 'check messages' in lower:
        return read_imessages()

    # Screen awareness
    if any(p in lower for p in ["what's on my screen", "what is on my screen", "read my screen", "look at my screen"]):
        return analyze_screen()

    # Document reading
    if any(p in lower for p in ['summarize this file', 'read this pdf', 'summarize document', 'read this file']):
        import re
        path_match = re.search(r'["\']?(/[^\s"\']+|~/[^\s"\']+)["\']?', text)
        if path_match:
            return summarize_document(path_match.group(1))
        return "Please provide the file path. Example: summarize this file /path/to/document.pdf"

    # Mac commands
    result = handle_command(text)
    if result:
        return result

    return None
