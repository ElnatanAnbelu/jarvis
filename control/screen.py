import sys
import os
import subprocess
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def capture_screen() -> str:
    """Take a screenshot and return the file path."""
    path = os.path.expanduser("~/Desktop/jarvis_screen.png")
    subprocess.run(["screencapture", "-x", path], check=True)
    return path


def analyze_screen() -> str:
    """Screenshot the screen and describe what's on it."""
    app = get_active_window()
    ocr = _ocr_screen()
    return f"Active app: {app}. {ocr}"


def _ocr_screen() -> str:
    """Fallback: OCR the screen text."""
    try:
        import pytesseract
        from PIL import Image
        path = capture_screen()
        img = Image.open(path)
        text = pytesseract.image_to_string(img)
        lines = [l.strip() for l in text.splitlines() if l.strip()][:20]
        if not lines:
            return "Screen captured but no readable text found."
        return "Screen text: " + " | ".join(lines[:10])
    except Exception as e:
        return f"OCR failed: {e}"


def get_active_window() -> str:
    """Get the name of the frontmost application."""
    try:
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of first application process whose frontmost is true'],
            capture_output=True, text=True
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


if __name__ == "__main__":
    print(analyze_screen())
