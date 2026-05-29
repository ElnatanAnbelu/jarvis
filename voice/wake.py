"""
voice/wake.py — Speech wake-word detector for JARVIS.

Primary path: openwakeword (offline, low-latency).
Fallback path: energy-gate → Groq Whisper keyword confirm.

Usage:
    from voice.wake import WakeWordListener
    listener = WakeWordListener(on_wake=my_callback)
    listener.start()          # background thread
    listener.mute()           # suppress during TTS
    listener.unmute()
    listener.stop()
"""
import os
import threading
import time
import numpy as np
import sounddevice as sd

SAMPLE_RATE   = 16000
CHUNK_SECS    = 0.5
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_SECS)
KEYWORDS      = ("jarvis", "hey jarvis")

# Energy threshold for voice onset (int16 RMS). 500 ≈ quiet speech.
_ENERGY_THRESH = 500


class WakeWordListener:
    """Continuous wake-word detector that calls `on_wake` on detection."""

    def __init__(self, on_wake, keywords=KEYWORDS):
        self._on_wake   = on_wake
        self._keywords  = keywords
        self._running   = False
        self._muted     = False
        self._thread    = None
        self._oww       = self._init_oww()

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def mute(self):
        """Suppress detection while JARVIS is speaking (echo guard)."""
        self._muted = True

    def unmute(self):
        self._muted = False

    # ── Internal ──────────────────────────────────────────────────────────────

    def _init_oww(self):
        try:
            from openwakeword.model import Model
            m = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
            print("[Wake] openwakeword loaded (offline mode)", flush=True)
            return m
        except Exception as e:
            print(f"[Wake] openwakeword unavailable ({e}), using energy-gate fallback", flush=True)
            return None

    def _loop(self):
        if self._oww is not None:
            self._loop_oww()
        else:
            self._loop_energy_gate()

    # ── Path A: openwakeword ──────────────────────────────────────────────────

    def _loop_oww(self):
        import queue as _q
        q: _q.Queue = _q.Queue()

        def _cb(indata, frames, t, status):
            q.put(indata.copy())

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                            blocksize=CHUNK_SAMPLES, callback=_cb):
            while self._running:
                try:
                    chunk = q.get(timeout=1.0)
                    if self._muted:
                        continue
                    audio = chunk.flatten()
                    predictions = self._oww.predict(audio)
                    for _model_name, score in predictions.items():
                        if score > 0.5:
                            print(f"[Wake] openwakeword triggered (score={score:.2f})", flush=True)
                            self._fire()
                            break
                except Exception:
                    pass

    # ── Path B: energy-gate + Groq keyword confirm ────────────────────────────

    def _loop_energy_gate(self):
        import queue as _q
        q: _q.Queue = _q.Queue()
        speech_buf: list = []

        def _cb(indata, frames, t, status):
            q.put(indata.copy())

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                            blocksize=CHUNK_SAMPLES, callback=_cb):
            while self._running:
                try:
                    chunk = q.get(timeout=1.0)
                    if self._muted:
                        speech_buf.clear()
                        continue

                    rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
                    if rms > _ENERGY_THRESH:
                        speech_buf.append(chunk)
                        # Keep at most 5 s of audio
                        if len(speech_buf) > int(5.0 / CHUNK_SECS):
                            speech_buf.pop(0)
                    elif speech_buf:
                        # Speech ended — run keyword check
                        audio = np.concatenate(speech_buf).flatten()
                        speech_buf.clear()
                        if self._groq_keyword_check(audio):
                            self._fire()
                except Exception:
                    pass

    def _groq_keyword_check(self, audio_int16: np.ndarray) -> bool:
        """Transcribe audio with Groq Whisper and check for wake keyword."""
        import scipy.io.wavfile as wavfile
        import tempfile
        from groq import Groq

        groq_key = os.environ.get("GROQ_API_KEY", "")
        if not groq_key:
            return False

        tmp = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp = f.name
            wavfile.write(tmp, SAMPLE_RATE, audio_int16)
            client = Groq(api_key=groq_key)
            with open(tmp, "rb") as fh:
                result = client.audio.transcriptions.create(
                    model="whisper-large-v3-turbo",
                    file=("audio.wav", fh, "audio/wav"),
                    response_format="text",
                )
            text = (result or "").lower().strip()
            matched = any(kw in text for kw in self._keywords)
            if matched:
                print(f"[Wake] keyword detected in: '{text}'", flush=True)
            return matched
        except Exception:
            return False
        finally:
            if tmp:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    def _fire(self):
        try:
            self._on_wake()
        except Exception as e:
            print(f"[Wake] on_wake callback error: {e}", flush=True)
        # Debounce: ignore wake signals for 1 s after firing
        time.sleep(1.0)
