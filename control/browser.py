"""
Browser control — open URLs or local files in Chrome.
"""
import os
import subprocess
import time
from pathlib import Path


def open_in_browser(target: str) -> str:
    """Open a URL or local file path in Chrome."""
    # Normalize local file paths to file:// URLs
    if not target.startswith("http://") and not target.startswith("https://") and not target.startswith("file://"):
        expanded = str(Path(os.path.expanduser(target)).resolve())
        if os.path.exists(expanded):
            target = f"file://{expanded}"
        else:
            return f"File not found: {expanded}"

    try:
        subprocess.Popen(["open", "-a", "Google Chrome", target])
        time.sleep(1.5)
        return f"Opened in Chrome: {target}"
    except Exception:
        # Fall back to default browser
        try:
            subprocess.Popen(["open", target])
            return f"Opened in default browser: {target}"
        except Exception as e:
            return f"Could not open browser: {e}"
