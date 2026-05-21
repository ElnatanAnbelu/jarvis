import subprocess
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def run_applescript(script: str) -> str:
    result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    return result.stdout.strip() or result.stderr.strip()

def run_shell(cmd: str) -> str:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip() or result.stderr.strip()

# — Apps —
def open_app(name: str) -> str:
    result = run_shell(f'open -a "{name}"')
    return f"Opened {name}." if not result else result

def close_app(name: str) -> str:
    run_applescript(f'tell application "{name}" to quit')
    return f"Closed {name}."

def list_running_apps() -> str:
    return run_applescript('tell application "System Events" to get name of every process whose background only is false')

# — Volume —
def set_volume(level: int) -> str:
    run_applescript(f'set volume output volume {level}')
    return f"Volume set to {level}."

def mute() -> str:
    run_applescript('set volume with output muted')
    return "Muted."

def unmute() -> str:
    run_applescript('set volume without output muted')
    return "Unmuted."

# — Screen —
def screenshot(path: str = "/tmp/jarvis_screenshot.png") -> str:
    run_shell(f'screencapture -x {path}')
    return path

def set_brightness(level: float) -> str:
    run_shell(f'brightness {level}')
    return f"Brightness set to {int(level*100)}%."

# — Files —
def open_file(path: str) -> str:
    run_shell(f'open "{path}"')
    return f"Opened {path}."

def create_file(path: str, content: str = "") -> str:
    Path(path).write_text(content)
    return f"Created {path}."

def list_files(directory: str = "~") -> str:
    return run_shell(f'ls -la {directory}')

def search_file(name: str, directory: str = "~") -> str:
    return run_shell(f'find {directory} -name "*{name}*" 2>/dev/null | head -10')

def move_file(src: str, dst: str) -> str:
    run_shell(f'mv "{src}" "{dst}"')
    return f"Moved {src} to {dst}."

def delete_file(path: str) -> str:
    run_shell(f'trash "{path}" 2>/dev/null || rm "{path}"')
    return f"Deleted {path}."

# — System —
def get_battery() -> str:
    return run_shell('pmset -g batt | grep -o "[0-9]*%" | head -1')

def get_wifi() -> str:
    return run_shell('/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I | grep " SSID" | awk \'{print $2}\'')

def empty_trash() -> str:
    run_applescript('tell application "Finder" to empty trash')
    return "Trash emptied."

def lock_screen() -> str:
    run_shell('/System/Library/CoreServices/Menu\\ Extras/User.menu/Contents/Resources/CGSession -suspend')
    return "Screen locked."

def sleep_mac() -> str:
    run_shell('pmset sleepnow')
    return "Going to sleep."

def get_clipboard() -> str:
    return run_shell('pbpaste')

def set_clipboard(text: str) -> str:
    subprocess.run('pbcopy', input=text.encode(), check=True)
    return "Copied to clipboard."

# — Notifications —
def notify(title: str, message: str) -> str:
    run_applescript(f'display notification "{message}" with title "{title}"')
    return f"Notification sent: {title}"

# — Web —
def open_url(url: str) -> str:
    run_shell(f'open "{url}"')
    return f"Opened {url}."

def google_search(query: str) -> str:
    url = f'https://www.google.com/search?q={query.replace(" ", "+")}'
    open_url(url)
    return f"Searching for: {query}"

# — Music —
def play_music() -> str:
    run_applescript('tell application "Music" to play')
    return "Playing music."

def pause_music() -> str:
    run_applescript('tell application "Music" to pause')
    return "Music paused."

def next_track() -> str:
    run_applescript('tell application "Music" to next track')
    return "Next track."

# — Clipboard & typing —
def type_text(text: str) -> str:
    run_applescript(f'tell application "System Events" to keystroke "{text}"')
    return f"Typed: {text}"

# — Natural language command router —
COMMANDS = {
    # Apps
    'open chrome': lambda: open_app('Google Chrome'),
    'open safari': lambda: open_app('Safari'),
    'open vscode': lambda: open_app('Visual Studio Code'),
    'open terminal': lambda: open_app('Terminal'),
    'open finder': lambda: open_app('Finder'),
    'open spotify': lambda: open_app('Spotify'),
    'open notion': lambda: open_app('Notion'),
    'open slack': lambda: open_app('Slack'),
    # System
    'take screenshot': screenshot,
    'empty trash': empty_trash,
    'lock screen': lock_screen,
    'sleep': sleep_mac,
    'mute': mute,
    'unmute': unmute,
    # Music
    'play music': play_music,
    'pause music': pause_music,
    'next track': next_track,
    'next song': next_track,
}

def handle_command(text: str):
    lower = text.lower()
    # Direct matches
    for key, fn in COMMANDS.items():
        if key in lower:
            return fn()
    # Volume
    if 'volume' in lower:
        import re
        nums = re.findall(r'\d+', lower)
        if nums:
            return set_volume(int(nums[0]))
    # Open app by name
    if lower.startswith('open '):
        app = text[5:].strip().title()
        return open_app(app)
    # Search web
    if 'search' in lower or 'google' in lower:
        query = lower.replace('search for','').replace('google','').replace('search','').strip()
        return google_search(query)
    # Open URL
    if 'open http' in lower or 'go to' in lower:
        import re
        urls = re.findall(r'https?://\S+', text)
        if urls:
            return open_url(urls[0])
    return None
