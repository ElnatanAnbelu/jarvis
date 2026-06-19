"""brain/resilience.py — graceful degradation (plan §R2).

When a load-bearing subsystem is down (the local brain, STT, TTS, the vault), Alfred
degrades with a clear butler line instead of crashing. All checks are cheap and local
and never raise.
"""
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def subsystem_status() -> dict:
    """Best-effort up/down of the load-bearing subsystems."""
    out = {}
    try:
        from brain import llm
        out["brain"] = bool(llm.available() and llm.any_model_available())
    except Exception:
        out["brain"] = False
    try:
        from voice import local_stt
        out["stt"] = bool(local_stt.available())
    except Exception:
        out["stt"] = False
    try:
        out["tts"] = (_ROOT / "voice" / "kokoro-v1.0.onnx").exists()
    except Exception:
        out["tts"] = False
    try:
        from memory.vault import DEFAULT_VAULT_PATH
        out["vault"] = Path(DEFAULT_VAULT_PATH).exists()
    except Exception:
        out["vault"] = False
    return out


_DEGRADED = {
    "brain": "My reasoning core is offline, sir — Ollama or the model isn't reachable. "
             "I'll keep notes and handle safe local tasks until it's back.",
    "stt": "I can't hear you just now, sir — speech recognition is unavailable. Type to me.",
    "tts": "I can't speak aloud at the moment, sir — I'll reply in text.",
    "vault": "Your Second Brain isn't mounted, sir — I'll work from memory and reconnect when it returns.",
}


def degraded_message(subsystem: str) -> str:
    return _DEGRADED.get(subsystem, f"The {subsystem} subsystem is degraded, sir; I'm working around it.")


def health_line() -> str:
    """One-line health summary for status surfaces, in Alfred's voice."""
    down = [k for k, v in subsystem_status().items() if not v]
    return "All systems nominal, sir." if not down else "Degraded: " + ", ".join(down) + "."
