#!/usr/bin/env python3
"""
JARVIS macOS App — pywebview window.
Spawns Flask as a subprocess using sys.executable + explicit PYTHONPATH.
"""
import sys
import os
import subprocess
import threading
import time
import signal
import platform

# ── ARM64 GUARD ──────────────────────────────────────────────────────────────
# When launched from JARVIS.app via LaunchServices, the CommandLineTools Python
# can start as x86_64. But the venv's native libs (sounddevice/cffi, pydantic_core)
# are arm64 — a mismatch that makes the mic (and other native modules) fail to load
# with "incompatible architecture". If we're not arm64, re-exec ourselves as arm64.
if (not getattr(sys, "frozen", False) and
        platform.machine() != "arm64" and
        os.environ.get("JARVIS_ARCH_REEXEC") != "1"):
    os.environ["JARVIS_ARCH_REEXEC"] = "1"
    try:
        os.execvp("arch", ["arch", "-arm64", sys.executable] + sys.argv)
    except Exception:
        pass

# ── FROZEN-AWARE PROJECT ROOT ────────────────────────────────────────────────
# When frozen (PyInstaller .app), __file__ points inside the bundle — useless.
# JARVIS_HOME env var (default ~/jarvis) locates the project directory.
if getattr(sys, "frozen", False):
    ROOT = os.path.expanduser(os.environ.get("JARVIS_HOME", "~/jarvis"))
else:
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import webview

ICON_PATH   = os.path.join(ROOT, "app", "icon.icns")
FLASK_PORT  = 8080
VENV_SITE   = os.path.join(ROOT, "venv", "lib", "python3.9", "site-packages")
VENV_PYTHON = os.path.join(ROOT, "venv", "bin", "python3")
FFMPEG      = "/opt/homebrew/bin/ffmpeg"  # installed via Homebrew

_flask_proc = None
_window     = None
_bubble     = None
_js_api     = None
_loaded_once = False
_session_summarizer = None  # joined in main() after webview closes


def _load_groq_key():
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if key:
        return key
    env_path = os.path.join(ROOT, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("GROQ_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return ""


class JsApi:
    """Native audio/camera for the pywebview desktop app.
    Bypasses WKWebView media APIs (which require extra config) entirely.
    Exposed to JS as window.pywebview.api.*
    """

    def __init__(self):
        self._recording = False
        self._stream    = None
        self._chunks    = []
        self._hud       = None     # full HUD window (shown when bubble expands)
        self._bubble    = None     # the always-on bubble window
        self._hud_visible = False
        self._wake_listener = None  # WakeWordListener, started after windows load

    # ── BUBBLE ↔ HUD WINDOW CONTROL ─────────────────────────────────────────
    def show_hud(self):
        try:
            if self._hud:
                self._hud.show()
                self._hud_visible = True
                return True
        except Exception as e:
            print(f"[JsApi.show_hud] {e}", flush=True)
        return False

    def hide_hud(self):
        try:
            if self._hud:
                self._hud.hide()
                self._hud_visible = False
                return True
        except Exception as e:
            print(f"[JsApi.hide_hud] {e}", flush=True)
        return False

    def toggle_hud(self):
        return self.hide_hud() if self._hud_visible else self.show_hud()

    def quit_app(self):
        """Clean shutdown from the bubble (frameless windows have no close button)."""
        try:
            import webview as _wv
            for w in list(_wv.windows):
                try:
                    w.destroy()
                except Exception:
                    pass
        except Exception as e:
            print(f"[JsApi.quit_app] {e}", flush=True)
        return True

    # ── WAKE WORD ────────────────────────────────────────────────────────────

    def start_wake_listener(self):
        """Start the continuous background wake-word listener.
        Called once from bubble.html on pywebviewready.
        Returns True on success, error string on failure."""
        if self._wake_listener is not None:
            return True
        try:
            from voice.wake import WakeWordListener

            def _on_wake():
                """Fire JS wakeWordFired() in the bubble window."""
                try:
                    if self._bubble:
                        self._bubble.evaluate_js("wakeWordFired()")
                except Exception as e:
                    print(f"[Wake] evaluate_js error: {e}", flush=True)

            self._wake_listener = WakeWordListener(on_wake=_on_wake)
            self._wake_listener.start()
            print("[Wake] listener started", flush=True)
            return True
        except Exception as e:
            print(f"[Wake] start failed: {e}", flush=True)
            return str(e)

    def mute_wake(self):
        """Echo guard — suppress wake detection while TTS is playing."""
        if self._wake_listener:
            self._wake_listener.mute()

    def unmute_wake(self):
        """Re-enable wake detection after TTS ends."""
        if self._wake_listener:
            self._wake_listener.unmute()

    def show_content(self, payload: str):
        """Called by bubble.html to push a [SHOW:...] payload to the HUD window.
        Avoids localStorage cross-window isolation issue in WKWebView."""
        import json
        try:
            if self._hud:
                self._hud.show()
                self._hud_visible = True
                self._hud.evaluate_js(f"showSurface({json.dumps(payload)})")
        except Exception as e:
            print(f"[JsApi.show_content] {e}", flush=True)

    # ── PERMISSION DIAGNOSTICS (callable from JS) ───────────────────────────

    def check_mic_permission(self):
        """Try to open the mic briefly. Returns 'granted', 'denied', or error string."""
        try:
            import sounddevice as sd
            st = sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=256)
            st.start()
            time.sleep(0.1)
            st.stop()
            st.close()
            return "granted"
        except Exception as e:
            msg = str(e).lower()
            if "permission" in msg or "denied" in msg or "not authorized" in msg:
                return "denied"
            return f"error: {e}"

    def request_mic_permission(self):
        """
        Aggressively force the macOS microphone permission prompt.
        This version opens the mic stream for a longer period and retries briefly.
        Call this explicitly from the UI when the user wants to fix mic permissions.
        """
        import sounddevice as sd
        import time

        for attempt in range(3):  # Try up to 3 times
            try:
                st = sd.InputStream(
                    samplerate=16000, 
                    channels=1, 
                    dtype="int16", 
                    blocksize=512
                )
                st.start()
                # Keep it open longer on later attempts to force the dialog
                time.sleep(0.8 if attempt == 0 else 1.5)
                st.stop()
                st.close()
                return "granted"
            except Exception as e:
                msg = str(e).lower()
                if "permission" in msg or "denied" in msg or "not authorized" in msg:
                    if attempt == 2:  # Last attempt
                        return "denied"
                    time.sleep(0.5)  # Wait a bit before retry
                    continue
                return f"error: {e}"
        return "denied"

    def check_camera_permission(self):
        """Try a quick camera frame. Returns 'granted', 'denied', or error string."""
        try:
            import subprocess
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                tmp = f.name
            cmd = [
                FFMPEG if os.path.exists(FFMPEG) else "ffmpeg",
                "-f", "avfoundation", "-video_size", "320x240", "-framerate", "10",
                "-i", "0", "-frames:v", "1", "-y", tmp
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            try:
                os.unlink(tmp)
            except:
                pass
            if result.returncode == 0:
                return "granted"
            else:
                return "denied"
        except Exception as e:
            return f"error: {e}"

    # ── MICROPHONE ──────────────────────────────────────────────────────────

    def start_recording(self):
        """VAD-based recording. Opens mic, waits for speech, auto-stops on silence,
        transcribes, then fires autoTranscript(text) or autoTranscriptEmpty() in JS.
        Returns True immediately — result comes back asynchronously via evaluate_js."""
        if self._recording:
            return True  # already running

        self._recording = True
        self._chunks = []

        def _vad_thread():
            import queue as _q
            import numpy as np
            import sounddevice as sd

            SR          = 16000
            CHUNK_SECS  = 0.4
            CHUNK_SAMP  = int(SR * CHUNK_SECS)
            ENERGY_ON   = 300    # int16 RMS — speech start
            ENERGY_OFF  = 200    # int16 RMS — speech end
            SILENCE_END = 6      # chunks of silence before auto-stop (~2.4 s)
            MAX_CHUNKS  = 75     # hard cap ~30 s

            q: _q.Queue = _q.Queue()
            speech_started = False
            silent_count   = 0
            chunks_all     = []

            def _cb(indata, frames, t, status):
                q.put(indata.copy())

            try:
                with sd.InputStream(samplerate=SR, channels=1, dtype="int16",
                                    blocksize=CHUNK_SAMP, callback=_cb):
                    while self._recording and len(chunks_all) < MAX_CHUNKS:
                        try:
                            chunk = q.get(timeout=1.5)
                        except _q.Empty:
                            break

                        rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))

                        if rms >= ENERGY_ON:
                            speech_started = True
                            silent_count   = 0
                            chunks_all.append(chunk)
                        elif speech_started:
                            chunks_all.append(chunk)
                            silent_count += 1
                            if silent_count >= SILENCE_END:
                                break   # natural end of utterance
                        # else: pre-speech silence, discard
            except Exception as e:
                print(f"[VAD] {e}", flush=True)

            self._recording = False
            self._stream    = None

            # Transcribe
            text = ""
            if chunks_all:
                try:
                    import numpy as np
                    import scipy.io.wavfile as wavfile
                    import tempfile as tf

                    audio = np.concatenate(chunks_all, axis=0)
                    with tf.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                        tmp = f.name
                    wavfile.write(tmp, SR, audio)
                    groq_key = _load_groq_key()
                    if groq_key:
                        from groq import Groq
                        client = Groq(api_key=groq_key)
                        with open(tmp, "rb") as fh:
                            result = client.audio.transcriptions.create(
                                model="whisper-large-v3-turbo",
                                file=("audio.wav", fh, "audio/wav"),
                                response_format="text",
                            )
                        text = (result or "").strip()
                    try:
                        os.unlink(tmp)
                    except Exception:
                        pass
                except Exception as e:
                    print(f"[VAD transcribe] {e}", flush=True)

            # Fire callback into JS
            try:
                import json as _json
                if self._bubble:
                    if text:
                        self._bubble.evaluate_js(
                            f"autoTranscript({_json.dumps(text)})"
                        )
                    else:
                        self._bubble.evaluate_js("autoTranscriptEmpty()")
            except Exception as e:
                print(f"[VAD callback] {e}", flush=True)

        threading.Thread(target=_vad_thread, daemon=True).start()
        return True

    def stop_recording(self):
        """Force-stop VAD recording early (barge-in / cancel).
        Returns empty string — result will still arrive via autoTranscript callback."""
        self._recording = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        return ""

    # ── CAMERA ──────────────────────────────────────────────────────────────

    def capture_frame(self):
        """Capture one frame from the default camera.
        Tries OpenCV first (clean permission attribution), then robust ffmpeg fallback.
        Returns base64 JPEG or empty string on total failure.
        Prints detailed diagnostics to terminal."""
        import base64

        # ── 1. OpenCV (preferred) ─────────────────────────────────────────────
        try:
            import cv2
            # Try explicit AVFoundation backend on macOS for better reliability
            cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(0)  # fallback to default

            try:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                frame = None
                for _ in range(15):
                    ok, f = cap.read()
                    if ok and f is not None:
                        frame = f
                        break
                    time.sleep(0.08)
                if frame is not None:
                    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                    if ok:
                        print("[Camera] OpenCV capture succeeded", flush=True)
                        return base64.b64encode(buf.tobytes()).decode()
            finally:
                cap.release()
            print("[Camera] OpenCV opened but returned no usable frame", flush=True)
        except Exception as e:
            print(f"[Camera] OpenCV failed: {e}", flush=True)

        # ── 2. More robust ffmpeg fallback ────────────────────────────────────
        import tempfile
        import os as _os
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            tmp_path = f.name

        ffmpeg_bin = FFMPEG if _os.path.exists(FFMPEG) else "ffmpeg"

        # Try a couple of common avfoundation inputs
        for dev in ["0", "default", "1"]:
            try:
                result = subprocess.run(
                    [ffmpeg_bin,
                     "-f", "avfoundation",
                     "-video_size", "1280x720",
                     "-framerate", "15",
                     "-i", dev,
                     "-frames:v", "1",
                     "-f", "image2",
                     "-vcodec", "mjpeg",
                     "-y", tmp_path],
                    capture_output=True,
                    timeout=8
                )
                if result.returncode == 0 and _os.path.getsize(tmp_path) > 0:
                    with open(tmp_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    print(f"[Camera] ffmpeg succeeded on device {dev}", flush=True)
                    try:
                        _os.unlink(tmp_path)
                    except:
                        pass
                    return b64
                else:
                    err = result.stderr.decode(errors='ignore')[:400]
                    print(f"[Camera] ffmpeg failed on device '{dev}' (code {result.returncode}): {err}", flush=True)
            except Exception as e:
                print(f"[Camera] ffmpeg exception on device '{dev}': {e}", flush=True)
            # clean for next try
            try:
                _os.unlink(tmp_path)
            except:
                pass

        print("[Camera] All capture methods failed. Check permissions for 'ffmpeg' and 'Terminal' in System Settings > Camera, then fully restart the app.", flush=True)
        return ""


def _request_mic_permission():
    """
    Trigger the macOS Microphone permission prompt early by briefly opening the mic.
    On macOS, if you run from Terminal, the prompt will be for "Terminal".
    If you run a bundled .app, it will be for the app name.
    """
    try:
        import sounddevice as sd
        st = sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=512)
        st.start()
        time.sleep(0.2)
        st.stop()
        st.close()
        print("[Permission] Microphone access ready (or prompt was shown).", flush=True)
    except Exception as e:
        print(f"[Permission] Microphone trigger failed: {e}", flush=True)
        print("→ If you don't see a permission popup, go to:", flush=True)
        print("   System Settings → Privacy & Security → Microphone", flush=True)
        print("   and manually enable it for Terminal / Python / JARVIS.", flush=True)


def _request_camera_permission():
    """
    Force the macOS Camera permission prompt early.
    We do a very quick, silent capture using ffmpeg (avfoundation) so the
    permission dialog appears for "Python" / Terminal / JARVIS on first launch.
    This is better UX than waiting until the user clicks Room Scan.
    """
    try:
        import subprocess
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            tmp = f.name

        # Very short capture (1 frame) just to trigger TCC prompt
        cmd = [
            FFMPEG if os.path.exists(FFMPEG) else "ffmpeg",
            "-f", "avfoundation",
            "-video_size", "640x480",
            "-framerate", "15",
            "-i", "0",
            "-frames:v", "1",
            "-f", "image2",
            "-y", tmp
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=6
        )
        # Clean up temp file immediately
        try:
            os.unlink(tmp)
        except:
            pass

        if result.returncode != 0:
            # Permission not yet granted or no camera — this is expected on first run
            print("[Permission] Camera prompt should have appeared (or will on first Room Scan).", flush=True)
        else:
            print("[Permission] Camera access OK.", flush=True)

    except Exception as e:
        # Non-fatal — we'll try again properly when user actually uses Room Scan
        print(f"[Permission] Camera pre-check: {e}", flush=True)


def _free_port(port=FLASK_PORT):
    """Kill any stale JARVIS instance holding the port so launches are reliable.
    Gated to JARVIS's own processes (server.py / main.py) — never touches others."""
    try:
        out = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True, text=True, timeout=5,
        )
        pids = [p for p in out.stdout.split() if p.strip().isdigit()]
        killed = False
        for pid in pids:
            try:
                cmd = subprocess.run(["ps", "-p", pid, "-o", "command="],
                                     capture_output=True, text=True, timeout=3).stdout.lower()
            except Exception:
                cmd = ""
            if "server.py" in cmd or "jarvis" in cmd or "app/main.py" in cmd:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    killed = True
                    print(f"Freed port {port}: terminated stale JARVIS pid {pid}", flush=True)
                except Exception:
                    pass
        if killed:
            time.sleep(1.2)
    except Exception as e:
        print(f"_free_port: {e}", flush=True)


def _start_flask():
    global _flask_proc
    env = os.environ.copy()
    # Prepend venv site-packages so Flask is importable by whatever Python binary runs
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{VENV_SITE}:{ROOT}:{existing}" if existing else f"{VENV_SITE}:{ROOT}"
    # Force arm64 so pydantic_core (arm64 binary) loads correctly
    _flask_proc = subprocess.Popen(
        [VENV_PYTHON, os.path.join(ROOT, "ui", "server.py")],
        env=env,
        cwd=ROOT,
        stdout=open(os.path.join(ROOT, "flask.log"), "w"),
        stderr=subprocess.STDOUT,
    )


def _wait_for_flask(timeout=30):
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{FLASK_PORT}/api/status", timeout=1)
            return True
        except Exception:
            time.sleep(0.4)
    return False


def _greet():
    # Disabled: the HUD itself fires the time-aware greeting via
    # /api/stream?message=__init__ on DOMContentLoaded (see app/hud.html).
    # Triggering anything here would cause a double greeting and previously
    # was injecting "Give me my morning briefing." which auto-pulled news,
    # weather, calendar etc. — not what Elnatan wants on open.
    return


def _on_closed():
    """Fire POST /api/end_session to the backend so it can summarize and save
    the session. Runs in a non-daemon thread so it survives webview shutdown."""
    global _session_summarizer

    def _request_end_session():
        try:
            import urllib.request
            req = urllib.request.Request(
                f"http://127.0.0.1:{FLASK_PORT}/api/end_session",
                data=b"",
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass

    _session_summarizer = threading.Thread(target=_request_end_session, daemon=False)
    _session_summarizer.start()


def _on_loaded():
    global _loaded_once
    if _loaded_once:
        return
    _loaded_once = True
    try:
        _window.evaluate_js("window.__PYWEBVIEW = true;")
    except Exception:
        pass
    threading.Thread(target=_greet, daemon=True).start()


def _screen_size():
    try:
        from AppKit import NSScreen
        fr = NSScreen.mainScreen().frame()
        return int(fr.size.width), int(fr.size.height)
    except Exception:
        return 1440, 900


def main():
    global _window, _bubble, _js_api

    print("\n" + "="*60)
    print("JARVIS — macOS Permission Notes")
    print("="*60)
    print("If microphone or camera doesn't work:")
    print("  1. Go to System Settings → Privacy & Security")
    print("  2. Enable Microphone + Camera for:")
    print("     - Terminal (if running from terminal)")
    print("     - Python")
    print("     - Or the JARVIS app if you built it as a .app")
    print("  3. Restart this app after changing permissions.")
    print()
    print("Still no microphone entry?")
    print("  → Run this dedicated fixer script:")
    print("     ./venv/bin/python3 fix_mic_permission.py")
    print("  (Keep the Microphone settings page open while it runs)")
    print("="*60 + "\n")

    _request_camera_permission()
    _request_mic_permission()
    _free_port()
    _start_flask()

    if not _wait_for_flask(timeout=30):
        # Show what went wrong
        log = os.path.join(ROOT, "flask.log")
        if os.path.exists(log):
            with open(log) as f:
                print(f.read(), file=sys.stderr)
        print("ERROR: Flask did not start", file=sys.stderr)
        sys.exit(1)

    _js_api = JsApi()

    # ── Full HUD window — starts hidden; the bubble expands into it ──────────
    _window = webview.create_window(
        title="J.A.R.V.I.S",
        url=f"http://127.0.0.1:{FLASK_PORT}/",
        width=900,
        height=720,
        min_size=(600, 500),
        resizable=True,
        frameless=False,
        on_top=False,
        hidden=True,
        js_api=_js_api,
    )

    # ── Always-on bubble — small, frameless, transparent, on top, draggable ──
    SW, SH = _screen_size()
    BUBBLE = 150
    _bubble = webview.create_window(
        title="JARVIS Bubble",
        url=f"http://127.0.0.1:{FLASK_PORT}/bubble",
        width=BUBBLE,
        height=BUBBLE,
        x=24,
        y=max(40, SH - BUBBLE - 90),   # bottom-left, above the Dock
        frameless=True,
        easy_drag=True,
        on_top=True,
        transparent=True,
        resizable=False,
        js_api=_js_api,
    )

    _js_api._hud    = _window
    _js_api._bubble = _bubble

    if os.path.exists(ICON_PATH):
        try:
            from AppKit import NSApplication, NSImage
            app_ns = NSApplication.sharedApplication()
            img = NSImage.alloc().initWithContentsOfFile_(ICON_PATH)
            if img:
                app_ns.setApplicationIconImage_(img)
        except Exception:
            pass

    # Closing the HUD hides it (bubble stays always-on); quit is via the bubble.
    def _on_hud_closing():
        try:
            _window.hide()
            _js_api._hud_visible = False
        except Exception:
            pass
        return False  # cancel the destroy

    _window.events.loaded  += _on_loaded
    _window.events.closing += _on_hud_closing
    _bubble.events.closed  += _on_closed
    webview.start(debug=False)

    # webview.start() returned — window is closed.
    # Give the session summarizer up to 8s to finish before the process exits.
    if _session_summarizer and _session_summarizer.is_alive():
        _session_summarizer.join(timeout=8)


if __name__ == "__main__":
    main()
