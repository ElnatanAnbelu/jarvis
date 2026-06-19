"""Alfred wake word — the rebrand + offline-first detection.

Locks: the keyword is "Alfred" (not JARVIS); the neural openwakeword path is OPT-IN
(no pretrained 'alfred' model, so default = offline energy-gate + local-STT keyword
match); and keyword matching is on the transcript, cloud-independent."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from voice import wake


def _listener(monkeypatch, model_env=None):
    if model_env is None:
        monkeypatch.delenv("ALFRED_WAKE_MODEL", raising=False)
    else:
        monkeypatch.setenv("ALFRED_WAKE_MODEL", model_env)
    return wake.WakeWordListener(on_wake=lambda: None)


def test_wake_keyword_is_alfred():
    assert wake.WAKE_NAME == "Alfred"
    assert "alfred" in wake.KEYWORDS and "hey alfred" in wake.KEYWORDS
    assert "jarvis" not in wake.KEYWORDS


def test_oww_is_opt_in_without_custom_model(monkeypatch):
    # No ALFRED_WAKE_MODEL → no neural model loaded → offline keyword path is used.
    lis = _listener(monkeypatch, model_env=None)
    assert lis._oww is None


def test_keyword_check_matches_alfred_in_transcript(monkeypatch):
    lis = _listener(monkeypatch)
    monkeypatch.setattr(lis, "_transcribe", lambda _p: "hey alfred are you there")
    silence = np.zeros(16000, dtype=np.int16)
    assert lis._keyword_check(silence) is True


def test_keyword_check_ignores_unrelated_speech(monkeypatch):
    lis = _listener(monkeypatch)
    monkeypatch.setattr(lis, "_transcribe", lambda _p: "what's the weather like")
    silence = np.zeros(16000, dtype=np.int16)
    assert lis._keyword_check(silence) is False


def test_transcribe_prefers_local_stt(monkeypatch):
    """_transcribe must go through local_stt.transcribe_or (local-first), not call
    Groq directly when local is available."""
    from voice import local_stt
    monkeypatch.setattr(local_stt, "available", lambda: True)
    monkeypatch.setattr(local_stt, "transcribe", lambda _p: "hey alfred")
    lis = _listener(monkeypatch)
    assert lis._transcribe("/tmp/x.wav") == "hey alfred"
