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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import webview

ICON_PATH   = os.path.join(ROOT, "app", "icon.icns")
FLASK_PORT  = 8080
VENV_SITE   = os.path.join(ROOT, "venv", "lib", "python3.9", "site-packages")
VENV_PYTHON = os.path.join(ROOT, "venv", "bin", "python3")

_flask_proc = None
_window     = None
_loaded_once = False


def _request_camera_permission():
    """Ask macOS for camera access for this Python process so WKWebView can use it."""
    try:
        import objc as _objc
        _objc.loadBundle(
            'AVFoundation',
            bundle_path='/System/Library/Frameworks/AVFoundation.framework',
            module_globals={},
        )
        AVCaptureDevice = _objc.lookUpClass('AVCaptureDevice')
        status = AVCaptureDevice.authorizationStatusForMediaType_('vide')
        print(f"Camera TCC status: {status} (0=unset,1=restricted,2=denied,3=ok)", flush=True)
        if status == 3:
            return
        if status != 0:
            print("Camera denied — grant in System Settings > Privacy > Camera", flush=True)
            return
        done = threading.Event()
        def _cb(granted):
            print(f"Camera permission: {'granted' if granted else 'denied'}", flush=True)
            done.set()
        AVCaptureDevice.requestAccessForMediaType_completionHandler_('vide', _cb)
        done.wait(timeout=15)
    except Exception as e:
        print(f"Camera permission check: {e}", flush=True)


def _start_flask():
    global _flask_proc
    env = os.environ.copy()
    # Prepend venv site-packages so Flask is importable by whatever Python binary runs
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{VENV_SITE}:{ROOT}:{existing}" if existing else f"{VENV_SITE}:{ROOT}"
    # Force arm64 so pydantic_core (arm64 binary) loads correctly
    _flask_proc = subprocess.Popen(
        ["arch", "-arm64", VENV_PYTHON, os.path.join(ROOT, "ui", "server.py")],
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
    time.sleep(1.2)
    if _window:
        try:
            from brain.briefing import already_sent_today
            briefed = already_sent_today()
        except Exception:
            briefed = False
        msg = "__init__" if briefed else "Give me my morning briefing."
        safe = msg.replace("'", "\\'")
        try:
            _window.evaluate_js(f"document.getElementById('inp').value='{safe}';doSend();")
        except Exception:
            pass


def _on_closed():
    try:
        from voice.speak import stop_speaking
        stop_speaking()
    except Exception:
        pass


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


def main():
    global _window

    _request_camera_permission()
    _start_flask()

    if not _wait_for_flask(timeout=30):
        # Show what went wrong
        log = os.path.join(ROOT, "flask.log")
        if os.path.exists(log):
            with open(log) as f:
                print(f.read(), file=sys.stderr)
        print("ERROR: Flask did not start", file=sys.stderr)
        sys.exit(1)

    _window = webview.create_window(
        title="J.A.R.V.I.S",
        url=f"http://127.0.0.1:{FLASK_PORT}/",
        width=820,
        height=680,
        min_size=(600, 500),
        resizable=True,
        frameless=False,
        on_top=False,
    )

    if os.path.exists(ICON_PATH):
        try:
            from AppKit import NSApplication, NSImage
            app_ns = NSApplication.sharedApplication()
            img = NSImage.alloc().initWithContentsOfFile_(ICON_PATH)
            if img:
                app_ns.setApplicationIconImage_(img)
        except Exception:
            pass

    _window.events.loaded += _on_loaded
    _window.events.closed += _on_closed
    webview.start(debug=False)


if __name__ == "__main__":
    main()
