import os
import subprocess
from datetime import datetime, date, timedelta
from pathlib import Path

CREDENTIALS_PATH = Path(__file__).parent.parent / "google_credentials.json"
TOKEN_PATH = Path(__file__).parent.parent / "google_token.json"


# ── APPLE CALENDAR ─────────────────────────────────────────────────────────

def _get_apple_events(target_date: date = None) -> list:
    if target_date is None:
        target_date = date.today()

    script = f"""
tell application "Calendar"
    set targetDate to date "{target_date.strftime('%B %d, %Y')}"
    set dayStart to targetDate - (time of targetDate)
    set dayEnd to dayStart + 86399
    set output to ""
    repeat with c in every calendar
        repeat with e in every event of c
            try
                if start date of e >= dayStart and start date of e <= dayEnd then
                    set t to time of (start date of e)
                    set h to t div 3600
                    set m to (t mod 3600) div 60
                    set timeStr to (h as string) & ":" & text -2 thru -1 of ("0" & (m as string))
                    set output to output & timeStr & " - " & summary of e & "\\n"
                end if
            end try
        end repeat
    end repeat
    if output is "" then return "none"
    return output
end tell
"""
    try:
        result = subprocess.run(["osascript", "-e", script],
                                capture_output=True, text=True, timeout=10)
        raw = result.stdout.strip()
        if raw == "none" or not raw:
            return []
        return [line.strip() for line in raw.splitlines() if line.strip()]
    except Exception:
        return []


# ── GOOGLE CALENDAR ────────────────────────────────────────────────────────

def _get_google_events(target_date: date = None) -> list:
    if not TOKEN_PATH.exists():
        return []
    if target_date is None:
        target_date = date.today()
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
        creds = None

        if TOKEN_PATH.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            elif CREDENTIALS_PATH.exists():
                flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
                creds = flow.run_local_server(port=0)
            else:
                return []
            TOKEN_PATH.write_text(creds.to_json())

        service = build("calendar", "v3", credentials=creds)
        start = datetime.combine(target_date, datetime.min.time()).isoformat() + "Z"
        end = datetime.combine(target_date + timedelta(days=1), datetime.min.time()).isoformat() + "Z"

        events_result = service.events().list(
            calendarId="primary", timeMin=start, timeMax=end,
            singleEvents=True, orderBy="startTime"
        ).execute()

        events = []
        for e in events_result.get("items", []):
            start_raw = e["start"].get("dateTime", e["start"].get("date", ""))
            if "T" in start_raw:
                dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
                time_str = dt.strftime("%-I:%M %p")
            else:
                time_str = "All day"
            events.append(f"{time_str} - {e.get('summary', 'Untitled')}")
        return events
    except Exception:
        return []


# ── UNIFIED ────────────────────────────────────────────────────────────────

def get_events(target_date: date = None) -> list:
    """Returns combined events from Apple + Google Calendar."""
    if target_date is None:
        target_date = date.today()
    apple = _get_apple_events(target_date)
    google = _get_google_events(target_date)
    seen = set()
    combined = []
    for e in apple + google:
        if e not in seen:
            seen.add(e)
            combined.append(e)
    return sorted(combined)


def get_events_str(target_date: date = None) -> str:
    """Returns events as a formatted string."""
    events = get_events(target_date)
    if not events:
        return "No events scheduled."
    return "\n".join(f"• {e}" for e in events)


def setup_google_calendar():
    """Run OAuth flow to connect Google Calendar."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
    if not CREDENTIALS_PATH.exists():
        return "No google_credentials.json found in jarvis folder."
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_PATH.write_text(creds.to_json())
    return "Google Calendar connected."


if __name__ == "__main__":
    print(get_events_str())
