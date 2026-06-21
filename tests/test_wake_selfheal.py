"""Proves the wake listener SELF-HEALS a dead microphone stream.

The recurring "stuck on listening" failure: after a quit/relaunch, the new process'
CoreAudio input stream sometimes delivers pure digital silence (RMS exactly 0) — the
device wasn't released in time. voice/wake.py detects that (a live mic always has a
non-zero noise floor) and reopens the stream until real audio flows.

This test can't make a real device go dead, so it injects a fake InputStream that
emits silence for the first couple seconds then real audio, and asserts the listener
(a) notices the dead stream and resets it, and (b) recovers to a live stream.
"""
import time
import threading
import numpy as np
import voice.wake as wake


class _FakeStream:
    """Stands in for sounddevice.InputStream: pushes zero-valued chunks (a dead
    device) until DEAD_SECS have elapsed since START, then non-zero chunks (live)."""
    START = 0.0
    DEAD_SECS = 2.2

    def __init__(self, *a, callback=None, blocksize=None, **k):
        self.callback = callback
        self.blocksize = blocksize or 8000
        self._run = False
        self._th = None

    def __enter__(self):
        self._run = True

        def feed():
            while self._run:
                elapsed = time.time() - _FakeStream.START
                val = 0 if elapsed < _FakeStream.DEAD_SECS else 120
                chunk = np.full((self.blocksize, 1), val, dtype="int16")
                try:
                    self.callback(chunk, self.blocksize, None, None)
                except Exception:
                    pass
                time.sleep(0.5)

        self._th = threading.Thread(target=feed, daemon=True)
        self._th.start()
        return self

    def __exit__(self, *a):
        self._run = False
        return False


def test_dead_mic_self_heals(capsys, monkeypatch):
    _FakeStream.START = time.time()
    monkeypatch.setattr(wake.sd, "InputStream", _FakeStream)
    monkeypatch.setattr(wake, "_DEAD_STREAM_CHUNKS", 4)  # 4 × 0.5 s = 2 s → reset

    lis = wake.WakeWordListener(on_wake=lambda: None)
    lis._oww = None  # force the offline energy-gate path (the single-stream loop)
    lis.start()
    time.sleep(4.6)   # ~2 s dead → reset → reopen → live; +1.2 s to log ambient
    lis.stop()
    time.sleep(0.6)

    out = capsys.readouterr().out
    assert "resetting mic stream" in out, f"self-heal never fired:\n{out}"
    assert "mic live" in out, f"never recovered to a live stream:\n{out}"
