"""P2: local STT availability + the local-first/cloud-fallback router (model-free)."""
from voice import local_stt


def test_disabled_is_unavailable(monkeypatch):
    monkeypatch.setattr(local_stt, "_DISABLED", True)
    assert local_stt.available() is False
    assert local_stt.transcribe("x.wav") == ""


def test_transcribe_or_prefers_local(monkeypatch):
    monkeypatch.setattr(local_stt, "available", lambda: True)
    monkeypatch.setattr(local_stt, "transcribe", lambda p: "local text")
    assert local_stt.transcribe_or("x.wav", cloud_fn=lambda p: "CLOUD") == "local text"


def test_transcribe_or_falls_back_when_unavailable(monkeypatch):
    monkeypatch.setattr(local_stt, "available", lambda: False)
    assert local_stt.transcribe_or("x.wav", cloud_fn=lambda p: "CLOUD") == "CLOUD"


def test_transcribe_or_falls_back_when_local_empty(monkeypatch):
    monkeypatch.setattr(local_stt, "available", lambda: True)
    monkeypatch.setattr(local_stt, "transcribe", lambda p: "")
    assert local_stt.transcribe_or("x.wav", cloud_fn=lambda p: "CLOUD") == "CLOUD"


def test_transcribe_or_no_cloud_returns_empty(monkeypatch):
    monkeypatch.setattr(local_stt, "available", lambda: False)
    assert local_stt.transcribe_or("x.wav", cloud_fn=None) == ""
