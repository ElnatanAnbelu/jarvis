import requests
import subprocess
import os
import tempfile
import threading
from pathlib import Path

# Global tracker — only one voice at a time
_current_proc = None
_lock = threading.Lock()

def stop_speaking():
    global _current_proc
    with _lock:
        if _current_proc and _current_proc.poll() is None:
            _current_proc.terminate()
            try:
                _current_proc.wait(timeout=1)
            except Exception:
                _current_proc.kill()
        _current_proc = None

def load_key():
    env_path = Path(__file__).parent.parent / ".env"
    for line in env_path.read_text().splitlines():
        if line.startswith("ELEVENLABS_API_KEY="):
            return line.split("=", 1)[1].strip()
    return None

JARVIS_VOICE_ID   = "onwK4e9ZLuTAKqWW03F9"
FRIDAY_VOICE_ID   = "EXAVITQu4vr4xnSDxMaL"
VERONICA_VOICE_ID = "cgSgspJ2msm6clMCkdW9"
KAREN_VOICE_ID    = "XrExE9yKIg1WjnnlVkGX"

VOICE_MAP = {
    "JARVIS":   JARVIS_VOICE_ID,
    "FRIDAY":   FRIDAY_VOICE_ID,
    "VERONICA": VERONICA_VOICE_ID,
    "KAREN":    KAREN_VOICE_ID,
}

EDGE_VOICE_MAP = {
    "JARVIS":   "en-GB-RyanNeural",
    "FRIDAY":   "en-US-JennyNeural",
    "VERONICA": "en-US-AriaNeural",
    "KAREN":    "en-US-MichelleNeural",
}


def _play_file(path: str):
    global _current_proc
    with _lock:
        proc = subprocess.Popen(["afplay", path])
        _current_proc = proc
    proc.wait()
    try:
        os.unlink(path)
    except Exception:
        pass


def _speak_edge(text: str, speaker: str = "JARVIS") -> bool:
    import asyncio
    import edge_tts
    voice = EDGE_VOICE_MAP.get(speaker, "en-GB-RyanNeural")
    async def _run():
        tts = edge_tts.Communicate(text, voice)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp = f.name
        await tts.save(tmp)
        return tmp
    try:
        tmp = asyncio.run(_run())
        _play_file(tmp)
        return True
    except Exception:
        return False


def speak(text: str, speaker: str = "JARVIS"):
    # Kill whatever is currently playing
    stop_speaking()

    api_key = load_key()

    # Try ElevenLabs first
    if api_key:
        voice_id = VOICE_MAP.get(speaker, JARVIS_VOICE_ID)
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
        payload = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {"stability": 0.75, "similarity_boost": 0.85, "style": 0.2}
        }
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=15)
            if r.status_code == 200:
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    f.write(r.content)
                    tmp_path = f.name
                _play_file(tmp_path)
                return
        except Exception:
            pass

    # Fallback: edge-tts
    if _speak_edge(text, speaker):
        return

    # Last resort: macOS say
    global _current_proc
    with _lock:
        proc = subprocess.Popen(["say", text])
        _current_proc = proc
    proc.wait()


if __name__ == "__main__":
    speak("Online and ready, sir.")
