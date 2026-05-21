import subprocess
import time
import requests


def send_whatsapp(to: str, message: str) -> str:
    """Send WhatsApp via the macOS desktop app using AppleScript."""
    # Look up number if name given
    number = _resolve_number(to)
    if not number:
        return f"Contact '{to}' not found in contacts."

    clean = number.replace("+", "").replace(" ", "").replace("-", "")

    # Open the chat via URL scheme
    subprocess.run(["open", f"whatsapp://send?phone={clean}"], check=False)
    time.sleep(3)

    safe_msg = message.replace('"', '\\"').replace("'", "\\'")
    script = f'''
tell application "WhatsApp"
    activate
end tell
delay 1
tell application "System Events"
    tell process "WhatsApp"
        keystroke "{safe_msg}"
        delay 0.5
        key code 36
    end tell
end tell
'''
    try:
        result = subprocess.run(["osascript", "-e", script],
                                capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return f"WhatsApp sent to {to}."
        return f"WhatsApp error: {result.stderr.strip()}"
    except Exception as e:
        return f"WhatsApp error: {e}"


def _resolve_number(name: str) -> str:
    """Get phone number from contacts.json or return as-is if already a number."""
    import json
    from pathlib import Path

    if any(c.isdigit() for c in name):
        return name

    contacts_path = Path(__file__).parent.parent / "contacts.json"
    if contacts_path.exists():
        contacts = json.loads(contacts_path.read_text())
        needle = name.lower().strip()
        for contact_name, phone in contacts.items():
            if needle in contact_name.lower() or contact_name.lower().startswith(needle):
                return phone

    # Try macOS Contacts app
    contacts_script = f'tell application "Contacts" to set r to every person whose name contains "{name}"\nif length of r > 0 then\nset p to item 1 of r\nif (count of phones of p) > 0 then\nreturn value of item 1 of phones of p\nend if\nend if'
    script = contacts_script
    try:
        result = subprocess.run(["osascript", "-e", script],
                                capture_output=True, text=True, timeout=8)
        num = result.stdout.strip()
        if num:
            return num
    except Exception:
        pass
    return ""


def whatsapp_status() -> bool:
    try:
        result = subprocess.run(["pgrep", "-x", "WhatsApp"],
                                capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False
