"""Local speech-to-text via faster-whisper — fully offline, free.

Degrades gracefully: if faster-whisper isn't installed (or fails), `available()`
is False and `transcribe()` returns "" so the caller can fall back to cloud STT.
The transcription path prefers this when JARVIS_LOCAL_STT != "0".
"""
import os

_MODEL = None
_MODEL_NAME = os.environ.get("JARVIS_WHISPER_MODEL", "small.en")
_DISABLED = os.environ.get("JARVIS_LOCAL_STT", "1") == "0"


def available() -> bool:
    if _DISABLED:
        return False
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:
        return False


def _get_model():
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel
        _MODEL = WhisperModel(_MODEL_NAME, device="auto", compute_type="int8")
    return _MODEL


def transcribe(wav_path) -> str:
    """Transcribe a WAV file fully locally. Returns text, or '' on any failure."""
    if _DISABLED:
        return ""
    try:
        model = _get_model()
        segments, _info = model.transcribe(str(wav_path), language="en", vad_filter=True)
        return " ".join(s.text for s in segments).strip()
    except Exception:
        return ""


def transcribe_or(wav_path, cloud_fn=None) -> str:
    """Prefer local STT; fall back to `cloud_fn(wav_path)` (e.g. Groq) when local
    is unavailable or returns nothing. Either path may be empty — caller handles."""
    if available():
        text = transcribe(wav_path)
        if text:
            return text
    if cloud_fn is not None:
        try:
            return cloud_fn(wav_path) or ""
        except Exception:
            return ""
    return ""
