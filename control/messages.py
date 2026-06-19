import subprocess
import re
import json
from pathlib import Path

CONTACTS_FILE = Path(__file__).parent.parent / "contacts.json"


def _osa_str(s) -> str:
    """Escape an arbitrary value for safe embedding inside an AppleScript
    double-quoted string literal.

    Without this, a value like `a@b" \\n do shell script "rm -rf ~" \\n "` would
    close the literal and inject a `do shell script` line — an AppleScript→shell
    RCE. We escape backslashes and quotes and strip newlines/control chars
    (an AppleScript string literal can't span lines, so a raw newline is itself
    a breakout primitive)."""
    s = str(s)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\r", " ").replace("\n", " ")
    return "".join(ch for ch in s if ch >= " " or ch == "\t")


def _load_contacts() -> dict:
    try:
        data = json.loads(CONTACTS_FILE.read_text())
        return {k.lower(): v for k, v in data.items() if v}
    except Exception:
        return {}


def _resolve_contact(name: str) -> str:
    """Check contacts.json first (exact then fuzzy), then fall back to Contacts app."""
    book = _load_contacts()
    needle = name.lower().strip()

    # Exact match
    if needle in book:
        return book[needle]

    # Fuzzy: contact name starts with or contains the search term
    for contact_name, phone in book.items():
        if contact_name.startswith(needle) or needle in contact_name:
            return phone

    # Fall back to macOS Contacts app
    script = f'''
    tell application "Contacts"
        launch
        set matches to (every person whose name contains "{_osa_str(name)}")
        if (count of matches) = 0 then return ""
        set p to item 1 of matches
        set allPhones to phones of p
        repeat with ph in allPhones
            if label of ph is "mobile" or label of ph is "iPhone" then
                return value of ph
            end if
        end repeat
        if (count of allPhones) > 0 then return value of item 1 of allPhones
        set allEmails to emails of p
        if (count of allEmails) > 0 then return value of item 1 of allEmails
        return ""
    end tell
    '''
    result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    return result.stdout.strip()


_PHONE_RE = re.compile(r'^[\d\+\-\(\)\s]{7,}$')
# A real email: exactly one @, no quotes/whitespace/control chars that could be
# used to break out of the AppleScript literal. NOT "any string containing @".
_EMAIL_RE = re.compile(r'^[^@\s"\'\\]+@[^@\s"\'\\]+\.[^@\s"\'\\]+$')


def _looks_like_handle(s: str) -> bool:
    s = (s or "").strip()
    return bool(_PHONE_RE.match(s) or _EMAIL_RE.match(s))


def send_imessage(contact: str, message: str) -> str:
    handle = contact.strip()

    if not _looks_like_handle(handle):
        resolved = _resolve_contact(handle)
        if not resolved:
            return f"Could not find '{contact}'. Add their number to contacts.json in the JARVIS folder."
        handle = resolved

    script = f'''
    tell application "Messages"
        set targetService to 1st service whose service type = iMessage
        set targetBuddy to buddy "{_osa_str(handle)}" of targetService
        send "{_osa_str(message)}" to targetBuddy
    end tell
    '''
    result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    if result.returncode == 0:
        label = f"{contact} ({handle})" if handle != contact else contact
        return f"Message sent to {label}."
    return f"Could not send message: {result.stderr.strip()}"


def read_imessages(contact: str = None, count: int = 5) -> str:
    try:
        count = max(1, min(int(count), 200))  # coerce: it is interpolated into the script
    except (TypeError, ValueError):
        count = 5
    if contact:
        handle = contact.strip()
        if not _looks_like_handle(handle):
            resolved = _resolve_contact(handle)
            if resolved:
                handle = resolved
        script = f'''
        tell application "Messages"
            set output to ""
            repeat with c in chats
                repeat with p in participants of c
                    if handle of p = "{_osa_str(handle)}" then
                        set msgs to messages of c
                        set n to count of msgs
                        if n > {count} then set msgs to items (n - {count} + 1) thru n of msgs
                        repeat with m in msgs
                            set output to output & (text of m) & "\\n"
                        end repeat
                    end if
                end repeat
            end repeat
            return output
        end tell
        '''
    else:
        script = f'''
        tell application "Messages"
            set output to ""
            set n to 0
            repeat with c in chats
                if n >= {count} then exit repeat
                try
                    set output to output & (name of c) & ": " & (text of last message of c) & "\\n"
                    set n to n + 1
                end try
            end repeat
            return output
        end tell
        '''
    result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    return result.stdout.strip() or "No messages found."
