"""
voice/wake.py — Speech wake-word detector for Alfred.

Primary path: openwakeword (offline, low-latency) — ONLY when the owner supplies a
custom Alfred wake model via ALFRED_WAKE_MODEL (openwakeword ships no "alfred" model).
Fallback path (default): energy-gate → local Whisper keyword confirm (fully offline;
cloud Groq used only if a key is set and local STT is unavailable).

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
WAKE_NAME     = "Alfred"
KEYWORDS      = ("alfred", "hey alfred")

# Energy threshold for voice onset (int16 RMS). ~450 reliably catches normal speech
# while ignoring silence/quiet ambient (silence≈0-50). Tune via ALFRED_WAKE_THRESH.
_ENERGY_THRESH = int(os.environ.get("ALFRED_WAKE_THRESH", "450"))

# Command-capture VAD (used after the wake word, on the SAME always-open stream).
_CMD_ENERGY_ON   = int(os.environ.get("ALFRED_CMD_THRESH", "300"))  # command speech onset
_CMD_SILENCE_END = 2      # 0.5 s chunks of trailing silence → end of utterance (~1.0 s)
_CMD_PRE_MAX     = 8.0    # seconds to wait for the command to start before giving up


class WakeWordListener:
    """Continuous wake-word detector that calls `on_wake` on detection."""

    def __init__(self, on_wake, on_command=None, on_level=None, keywords=KEYWORDS):
        self._on_wake    = on_wake
        self._on_command = on_command   # called with the transcribed command after capture
        self._on_level   = on_level     # called each chunk with the live mic RMS (UI waveform)
        self._keywords   = keywords
        self._running    = False
        self._muted      = False
        self._mode       = "wake"       # "wake" (listen for 'Alfred') | "command" (capture)
        self._thread     = None
        self._oww        = self._init_oww()

    def capture_now(self):
        """Enter command-capture mode immediately — for a follow-up turn in an active
        conversation (no wake word needed). Same single stream, just a mode flip."""
        self._mode = "command"

    def cancel_capture(self):
        """Abort command capture and go back to listening for the wake word."""
        self._mode = "wake"

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
        """Suppress detection while Alfred is speaking (echo guard)."""
        self._muted = True

    def unmute(self):
        self._muted = False

    # ── Internal ──────────────────────────────────────────────────────────────

    def _init_oww(self):
        # openwakeword ships pretrained models for "hey_jarvis"/"alexa"/etc. — NOT
        # "alfred". Using the jarvis acoustic model would make Alfred wake to the wrong
        # word, so the neural path is OPT-IN: set ALFRED_WAKE_MODEL=/path/to/alfred.onnx
        # (a custom-trained model). Without it we use the offline energy-gate + local-STT
        # keyword path below, which matches "alfred" today; the model is a drop-in upgrade.
        model_path = os.environ.get("ALFRED_WAKE_MODEL", "").strip()
        if not model_path:
            print("[Wake] no ALFRED_WAKE_MODEL — using offline energy-gate + local-STT "
                  "keyword detection for 'Alfred'.", flush=True)
            return None
        last_err = None
        for framework in ("onnx", "tflite"):
            try:
                from openwakeword.model import Model
                m = Model(wakeword_models=[model_path], inference_framework=framework)
                print(f"[Wake] Alfred wake model loaded: {model_path} ({framework})", flush=True)
                return m
            except Exception as e:
                last_err = e
                continue
        print(f"[Wake] custom wake model unavailable ({last_err}); using keyword fallback.", flush=True)
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
        """ONE always-open mic stream, mode-switched between wake-word detection and
        command capture. Never closing/reopening the stream avoids the CoreAudio
        'second stream reads silence' bug. `mute()` just skips processing (echo guard
        while Alfred speaks) — it does NOT close the stream."""
        import queue as _q
        import time as _t
        q: _q.Queue = _q.Queue()

        def _cb(indata, frames, t, status):
            q.put(indata.copy())

        speech_buf   = []        # wake-word detection buffer
        cmd_buf      = []        # command-capture buffer
        cmd_started  = False
        cmd_silent   = 0
        cmd_deadline = 0.0
        cmd_peak     = 0.0
        prev_mode    = self._mode

        while self._running:
            try:
                with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                                    blocksize=CHUNK_SAMPLES, callback=_cb):
                    print(f"[Wake] mic open (single stream, gate={_ENERGY_THRESH})", flush=True)
                    while self._running:
                        try:
                            chunk = q.get(timeout=0.3)
                        except _q.Empty:
                            continue
                        if self._muted:                       # echo guard while speaking
                            speech_buf.clear(); cmd_buf = []; cmd_started = False
                            prev_mode = self._mode
                            continue

                        if self._mode != prev_mode:           # (re)arm on a mode flip
                            prev_mode = self._mode
                            if self._mode == "command":
                                cmd_buf = []; cmd_started = False; cmd_silent = 0; cmd_peak = 0.0
                                cmd_deadline = _t.time() + _CMD_PRE_MAX
                                speech_buf.clear()

                        rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
                        # (UI waveform runs on its own animation; no per-frame bridge push.)

                        if self._mode == "command":
                            if rms > cmd_peak:
                                cmd_peak = rms
                            if rms >= _CMD_ENERGY_ON:
                                cmd_started = True; cmd_silent = 0; cmd_buf.append(chunk)
                            elif cmd_started:
                                cmd_buf.append(chunk); cmd_silent += 1
                                if cmd_silent >= _CMD_SILENCE_END:        # end of utterance
                                    audio = (np.concatenate(cmd_buf).flatten() if cmd_buf
                                             else np.array([], dtype="int16"))
                                    cmd_buf = []; cmd_started = False; cmd_silent = 0
                                    self._mode = "wake"; prev_mode = "wake"
                                    text = self._transcribe_int16(audio)
                                    print(f"[Wake] command: {text!r}  (peak RMS={cmd_peak:.0f})", flush=True)
                                    self._emit_command(text)
                            elif _t.time() > cmd_deadline:                # no speech → give up
                                cmd_buf = []; cmd_started = False
                                self._mode = "wake"; prev_mode = "wake"
                                print(f"[Wake] command timeout — no speech (peak RMS={cmd_peak:.0f})", flush=True)
                                self._emit_command("")
                        else:  # wake mode — listen for 'Alfred'
                            if rms > _ENERGY_THRESH:
                                speech_buf.append(chunk)
                                if len(speech_buf) > int(5.0 / CHUNK_SECS):
                                    speech_buf.pop(0)
                            elif speech_buf:
                                audio = np.concatenate(speech_buf).flatten()
                                speech_buf.clear()
                                if self._keyword_check(audio):
                                    print("[Wake] 'Alfred' detected → capturing command", flush=True)
                                    self._mode = "command"; prev_mode = "command"
                                    cmd_buf = []; cmd_started = False; cmd_silent = 0; cmd_peak = 0.0
                                    cmd_deadline = _t.time() + _CMD_PRE_MAX
                                    self._fire()
            except Exception as e:
                print(f"[Wake] stream error: {e}", flush=True)
                _t.sleep(0.3)

    def _emit_command(self, text):
        if self._on_command:
            try:
                self._on_command(text)
            except Exception as e:
                print(f"[Wake] on_command error: {e}", flush=True)

    def _transcribe_int16(self, audio_int16) -> str:
        """Transcribe a captured int16 mono buffer (16 kHz) to text, fully local-first."""
        import scipy.io.wavfile as wavfile
        import tempfile
        if audio_int16 is None or len(audio_int16) == 0:
            return ""
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp = f.name
            wavfile.write(tmp, SAMPLE_RATE, audio_int16)
            return (self._transcribe(tmp) or "").strip()
        except Exception:
            return ""
        finally:
            if tmp:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    def _keyword_check(self, audio_int16: np.ndarray) -> bool:
        """Transcribe the captured speech (LOCAL Whisper first; Groq only if local is
        unavailable and a key is set) and check for the 'Alfred' wake keyword. Fully
        offline on a machine with faster-whisper installed."""
        import scipy.io.wavfile as wavfile
        import tempfile

        tmp = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp = f.name
            wavfile.write(tmp, SAMPLE_RATE, audio_int16)
            text = self._transcribe(tmp).lower().strip()
            matched = any(kw in text for kw in self._keywords)
            if matched:
                print(f"[Wake] keyword matched in: '{text}'", flush=True)
            return matched
        except Exception:
            return False
        finally:
            if tmp:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    def _transcribe(self, wav_path) -> str:
        """Local-first transcription for wake detection (offline by default)."""
        def _groq_fn(path):
            groq_key = os.environ.get("GROQ_API_KEY", "")
            if not groq_key:
                return ""
            try:
                from groq import Groq
                client = Groq(api_key=groq_key)
                with open(path, "rb") as fh:
                    return client.audio.transcriptions.create(
                        model="whisper-large-v3-turbo",
                        file=("audio.wav", fh, "audio/wav"),
                        response_format="text",
                    ) or ""
            except Exception:
                return ""

        try:
            from voice import local_stt
            return local_stt.transcribe_or(wav_path, cloud_fn=_groq_fn) or ""
        except Exception:
            return _groq_fn(wav_path)

    def _fire(self):
        try:
            self._on_wake()
        except Exception as e:
            print(f"[Wake] on_wake callback error: {e}", flush=True)
