# Camera/Mic TCC Fix — Frozen Signed JARVIS.app Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze only the pywebview front-end (`app/main.py`) into a properly signed `JARVIS.app` so macOS TCC attributes camera/mic requests to "JARVIS" (`com.elnatan.jarvis`) rather than the system Python.

**Architecture:** PyInstaller freezes `app/main.py` + its GUI/capture deps (webview, sounddevice, cv2, numpy, scipy, groq) into a self-contained arm64 binary. The Flask backend continues to spawn as a venv subprocess — unchanged. On close, the front-end fires `POST /api/end_session` to the backend (instead of importing memory/anthropic directly), keeping the freeze boundary lean.

**Tech Stack:** PyInstaller 6.20, pywebview, sounddevice, OpenCV (cv2), groq, Flask (backend, unchanged), codesign, tccutil

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `requirements.txt` | Full venv pip freeze — needed by `setup_new_mac.sh` |
| Modify | `app/main.py` | 4 changes: frozen ROOT, skip arch re-exec, drop `arch -arm64` from backend launch, replace `_on_closed`/`_summarize_session` with `POST /api/end_session` |
| Modify | `ui/server.py` | Add `POST /api/end_session` route (move session-summary Haiku logic here) |
| Create | `app/jarvis.entitlements` | Camera + mic entitlements for `codesign` |
| Create | `jarvis.spec` | PyInstaller spec: freeze boundary, hidden imports, bundle metadata |
| Create | `scripts/build_app.sh` | Repeatable: PyInstaller → codesign → install → tccutil reset |
| Create | `scripts/setup_new_mac.sh` | Bare Apple Silicon Mac → working JARVIS in one command |

---

## Task 1: Generate requirements.txt

**Files:**
- Create: `requirements.txt`

- [ ] **Step 1: Generate from the active venv**

```bash
cd ~/jarvis
./venv/bin/pip freeze > requirements.txt
```

- [ ] **Step 2: Verify the file is non-empty and contains key packages**

```bash
grep -E "^(pywebview|sounddevice|opencv|numpy|scipy|groq|flask|anthropic|pyinstaller)" requirements.txt
```

Expected output: lines like `pywebview==5.x`, `sounddevice==0.5.5`, `opencv-python==4.x`, `numpy==2.0.2`, etc.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add requirements.txt for new-Mac migration"
```

---

## Task 2: Refactor `app/main.py` — 4 targeted changes

**Files:**
- Modify: `app/main.py`

This task makes four surgical edits. Make them in order.

### Change A: Frozen-aware ROOT

- [ ] **Step 1: Replace the static ROOT assignment (lines 26-28)**

Find this block (immediately after the ARM64 guard):
```python
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
```

Replace with:
```python
# ── FROZEN-AWARE PROJECT ROOT ────────────────────────────────────────────────
# When frozen (PyInstaller .app), __file__ points inside the bundle — useless.
# JARVIS_HOME env var (default ~/jarvis) locates the project directory.
if getattr(sys, "frozen", False):
    ROOT = os.path.expanduser(os.environ.get("JARVIS_HOME", "~/jarvis"))
else:
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
```

### Change B: Skip arch re-exec guard when frozen

- [ ] **Step 2: Gate the ARM64 re-exec on non-frozen mode**

Find this block (lines 19-24):
```python
if platform.machine() != "arm64" and os.environ.get("JARVIS_ARCH_REEXEC") != "1":
    os.environ["JARVIS_ARCH_REEXEC"] = "1"
    try:
        os.execvp("arch", ["arch", "-arm64", sys.executable] + sys.argv)
    except Exception:
        pass
```

Replace with:
```python
if (not getattr(sys, "frozen", False) and
        platform.machine() != "arm64" and
        os.environ.get("JARVIS_ARCH_REEXEC") != "1"):
    os.environ["JARVIS_ARCH_REEXEC"] = "1"
    try:
        os.execvp("arch", ["arch", "-arm64", sys.executable] + sys.argv)
    except Exception:
        pass
```

### Change C: Drop redundant `arch -arm64` from backend launch

- [ ] **Step 3: Remove `arch -arm64` prefix in `_start_flask()`**

Find this inside `_start_flask()`:
```python
    _flask_proc = subprocess.Popen(
        ["arch", "-arm64", VENV_PYTHON, os.path.join(ROOT, "ui", "server.py")],
```

Replace with:
```python
    _flask_proc = subprocess.Popen(
        [VENV_PYTHON, os.path.join(ROOT, "ui", "server.py")],
```

### Change D: Replace `_on_closed` / `_summarize_session` with backend delegation

- [ ] **Step 4: Delete `_summarize_session` entirely and replace `_on_closed`**

Delete the entire `_summarize_session` function (lines 481–531).

Find the current `_on_closed`:
```python
def _on_closed():
    global _session_summarizer
    try:
        from voice.speak import stop_speaking
        stop_speaking()
    except Exception:
        pass
    # Non-daemon so it survives the webview shutdown; joined in main() with timeout
    _session_summarizer = threading.Thread(target=_summarize_session, daemon=False)
    _session_summarizer.start()
```

Replace with:
```python
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
```

- [ ] **Step 5: Verify the file compiles cleanly**

```bash
cd ~/jarvis
./venv/bin/python3 -m py_compile app/main.py && echo "OK"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add app/main.py
git commit -m "refactor: make app/main.py frozen-app compatible (JARVIS_HOME, end_session)"
```

---

## Task 3: Add `/api/end_session` route to `ui/server.py`

**Files:**
- Modify: `ui/server.py`

- [ ] **Step 1: Add the route at the end of `ui/server.py`, before the `if __name__` block**

Open `ui/server.py` and find the last `@app.route` block (around `/bubble`). Add the following immediately after it:

```python
@app.route("/api/end_session", methods=["POST"])
def end_session():
    """Called by the pywebview front-end on window close.
    Summarises the session with Haiku and saves it for next startup."""
    import threading as _t

    def _summarize():
        try:
            from memory.memory import get_recent_history, save_session_summary
            history = get_recent_history(limit=40)
            if not history or len(history) < 4:
                return
            lines = []
            for role, content in history:
                label = "Elnatan" if role == "user" else "JARVIS"
                lines.append("{}: {}".format(label, content[:400]))
            convo = "\n".join(lines[-24:])

            # Load .env keys if not already in environment
            env_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
            )
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f.read().splitlines():
                        if "=" in line and not line.startswith("#"):
                            k, v = line.split("=", 1)
                            if v.strip() and k.strip() not in os.environ:
                                os.environ[k.strip()] = v.strip()

            api_key = (
                os.environ.get("ANTHROPIC_API_KEY", "").strip() or
                os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
            )
            if not api_key:
                return

            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=180,
                messages=[{
                    "role": "user",
                    "content": (
                        "Summarize this JARVIS session in 2-3 short sentences so JARVIS can pick up "
                        "next session without re-explaining context. Focus on: what was worked on, key "
                        "decisions made, current status of ongoing tasks. Start with 'Last session,' "
                        "and be specific — name actual projects, files, or topics discussed.\n\n"
                        "SESSION:\n{}".format(convo)
                    )
                }]
            )
            summary = (resp.content[0].text or "").strip()
            if summary:
                save_session_summary(summary)
        except Exception as e:
            print(f"[end_session] {e}", flush=True)

    _t.Thread(target=_summarize, daemon=True).start()
    return jsonify({"ok": True})
```

- [ ] **Step 2: Verify the file compiles cleanly**

```bash
cd ~/jarvis
./venv/bin/python3 -m py_compile ui/server.py && echo "OK"
```

Expected: `OK`

- [ ] **Step 3: Smoke-test the route against the running server**

```bash
curl -s -X POST http://127.0.0.1:8080/api/end_session
```

Expected: `{"ok": true}`

- [ ] **Step 4: Commit**

```bash
git add ui/server.py
git commit -m "feat: add POST /api/end_session route for session summarization"
```

---

## Task 4: Create `app/jarvis.entitlements`

**Files:**
- Create: `app/jarvis.entitlements`

- [ ] **Step 1: Write the entitlements file**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <!-- TCC entitlements: camera and microphone access -->
    <key>com.apple.security.device.camera</key>
    <true/>
    <key>com.apple.security.device.audio-input</key>
    <true/>
    <!-- Required for PyInstaller frozen apps: dynamic Python bytecode and
         third-party native extensions (cv2, sounddevice, cffi) -->
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>
    <key>com.apple.security.cs.disable-library-validation</key>
    <true/>
</dict>
</plist>
```

- [ ] **Step 2: Verify it is valid XML**

```bash
plutil -lint app/jarvis.entitlements && echo "OK"
```

Expected: `app/jarvis.entitlements: OK`

- [ ] **Step 3: Commit**

```bash
git add app/jarvis.entitlements
git commit -m "chore: add camera/mic entitlements for JARVIS.app codesigning"
```

---

## Task 5: Create `jarvis.spec` (PyInstaller spec)

**Files:**
- Create: `jarvis.spec`

- [ ] **Step 1: Write the spec file**

```python
# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for JARVIS.app front-end.
Freezes ONLY app/main.py + GUI/capture deps.
The Flask backend (ui/server.py) is NOT frozen — it runs as a venv subprocess.
"""
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

# Collect all files for packages that have native binaries or data
sd_datas, sd_binaries, sd_hiddenimports = collect_all('sounddevice')
cv2_datas, cv2_binaries, cv2_hiddenimports = collect_all('cv2')
wv_datas, wv_binaries, wv_hiddenimports = collect_all('webview')

a = Analysis(
    ['app/main.py'],
    pathex=['.'],
    binaries=sd_binaries + cv2_binaries + wv_binaries,
    datas=(
        sd_datas + cv2_datas + wv_datas +
        [('app/icon.icns', '.')]
    ),
    hiddenimports=(
        sd_hiddenimports + cv2_hiddenimports + wv_hiddenimports + [
            # pywebview Cocoa backend
            'webview.platforms.cocoa',
            'webview.platforms',
            # pyobjc — screen size + app icon
            'AppKit',
            'Foundation',
            'objc',
            # audio / capture
            'numpy',
            'numpy.core',
            'numpy.core._multiarray_umath',
            'scipy',
            'scipy.io',
            'scipy.io.wavfile',
            'cffi',
            '_cffi_backend',
            # Groq transcription
            'groq',
            'groq._client',
            'groq.resources',
            'groq.resources.audio',
            'groq.resources.audio.transcriptions',
            # stdlib used directly
            'urllib.request',
        ]
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Explicitly exclude backend modules so they are never pulled in
    excludes=[
        'memory', 'brain', 'voice', 'control', 'scripts',
        'flask', 'flask_cors', 'anthropic', 'openai',
        'telegram', 'whatsapp',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='JARVIS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch='arm64',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='JARVIS',
)

app = BUNDLE(
    coll,
    name='JARVIS.app',
    icon='app/icon.icns',
    bundle_identifier='com.elnatan.jarvis',
    info_plist={
        'CFBundleName': 'JARVIS',
        'CFBundleDisplayName': 'JARVIS',
        'CFBundleIdentifier': 'com.elnatan.jarvis',
        'CFBundleVersion': '1.0',
        'CFBundleShortVersionString': '1.0',
        'NSHighResolutionCapable': True,
        # LSUIElement: the app has no Dock icon — it's the floating bubble
        'LSUIElement': True,
        'LSMinimumSystemVersion': '12.0',
        'NSCameraUsageDescription':
            'JARVIS uses the camera to scan and describe your physical environment.',
        'NSMicrophoneUsageDescription':
            'JARVIS uses the microphone for voice commands and conversation.',
        'NSSpeechRecognitionUsageDescription':
            'JARVIS transcribes your voice so you can speak to it naturally.',
        'NSAppleEventsUsageDescription':
            'JARVIS controls Music, Messages, and other apps on your behalf.',
    },
)
```

- [ ] **Step 2: Verify the spec parses (dry-run)**

```bash
cd ~/jarvis
./venv/bin/python3 -c "exec(open('jarvis.spec').read()); print('spec OK')" 2>&1 | tail -5
```

Expected: ends with `spec OK` (some warnings about Analysis not being defined outside PyInstaller are normal).

- [ ] **Step 3: Commit**

```bash
git add jarvis.spec
git commit -m "chore: add PyInstaller spec for frozen JARVIS.app front-end"
```

---

## Task 6: Create `scripts/build_app.sh`

**Files:**
- Create: `scripts/build_app.sh`

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# scripts/build_app.sh
# Builds, signs, installs, and TCC-resets JARVIS.app.
# Run: bash scripts/build_app.sh
# Re-run any time you change app/main.py or jarvis.spec.
set -euo pipefail

JARVIS_HOME="${JARVIS_HOME:-$HOME/jarvis}"
VENV="$JARVIS_HOME/venv"
PYINSTALLER="$VENV/bin/pyinstaller"
ENTITLEMENTS="$JARVIS_HOME/app/jarvis.entitlements"
DIST="$JARVIS_HOME/dist/JARVIS.app"
DEST="$JARVIS_HOME/JARVIS.app"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║     JARVIS App Builder               ║"
echo "╚══════════════════════════════════════╝"
echo "  Project:  $JARVIS_HOME"
echo "  venv:     $VENV"
echo ""

# ── 1. Prerequisites ──────────────────────────────────────────────────────────
if [ ! -x "$PYINSTALLER" ]; then
    echo "ERROR: PyInstaller not found at $PYINSTALLER"
    echo "Run:  $VENV/bin/pip install pyinstaller"
    exit 1
fi
if [ ! -f "$JARVIS_HOME/app/main.py" ]; then
    echo "ERROR: $JARVIS_HOME/app/main.py not found."
    echo "Is JARVIS_HOME set correctly? (current: $JARVIS_HOME)"
    exit 1
fi
if [ ! -f "$ENTITLEMENTS" ]; then
    echo "ERROR: Entitlements file not found at $ENTITLEMENTS"
    exit 1
fi

# ── 2. Build ──────────────────────────────────────────────────────────────────
echo "[1/5] Building frozen app with PyInstaller..."
cd "$JARVIS_HOME"
"$PYINSTALLER" --clean -y jarvis.spec
echo "      Build complete → $DIST"

# ── 3. Sign ───────────────────────────────────────────────────────────────────
echo ""
echo "[2/5] Code-signing with entitlements (ad-hoc)..."
codesign --force --deep --sign - \
    --entitlements "$ENTITLEMENTS" \
    --identifier com.elnatan.jarvis \
    "$DIST"
echo "      Signed OK"

# ── 4. Install ────────────────────────────────────────────────────────────────
echo ""
echo "[3/5] Installing JARVIS.app to $DEST..."
rm -rf "$DEST"
cp -R "$DIST" "$DEST"
echo "      Installed OK"

# ── 5. Reset TCC ──────────────────────────────────────────────────────────────
echo ""
echo "[4/5] Resetting TCC entries for com.elnatan.jarvis..."
tccutil reset Camera      com.elnatan.jarvis 2>/dev/null || true
tccutil reset Microphone  com.elnatan.jarvis 2>/dev/null || true
echo "      TCC reset OK"

# ── 6. Done ───────────────────────────────────────────────────────────────────
echo ""
echo "[5/5] Done!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  NEXT STEP: Launch JARVIS.app and grant permissions"
echo ""
echo "  Option A (GUI):  double-click ~/jarvis/JARVIS.app"
echo "  Option B (CLI):  open '$DEST'"
echo ""
echo "  When macOS asks, click ALLOW for:"
echo "    • Camera"
echo "    • Microphone"
echo ""
echo "  Both prompts should say 'JARVIS wants access to...'."
echo "  If they say 'Python wants access', something went wrong —"
echo "  re-run this script."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/build_app.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts/build_app.sh
git commit -m "feat: add scripts/build_app.sh for repeatable JARVIS.app builds"
```

---

## Task 7: Create `scripts/setup_new_mac.sh`

**Files:**
- Create: `scripts/setup_new_mac.sh`

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# scripts/setup_new_mac.sh
# One-command setup on a fresh Apple Silicon Mac.
# Usage: cd ~/jarvis && bash scripts/setup_new_mac.sh
set -euo pipefail

JARVIS_HOME="${JARVIS_HOME:-$HOME/jarvis}"
VENV="$JARVIS_HOME/venv"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║    JARVIS New-Mac Setup              ║"
echo "╚══════════════════════════════════════╝"
echo "  Target: $JARVIS_HOME"
echo ""

# ── 1. Homebrew ───────────────────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
    echo "[1/4] Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add Homebrew to PATH for this session (Apple Silicon default)
    eval "$(/opt/homebrew/bin/brew shellenv)"
else
    echo "[1/4] Homebrew already installed — skipping."
fi

# ── 2. ffmpeg ─────────────────────────────────────────────────────────────────
if ! command -v ffmpeg &>/dev/null; then
    echo "[2/4] Installing ffmpeg..."
    brew install ffmpeg
else
    echo "[2/4] ffmpeg already installed — skipping."
fi

# ── 3. Python venv ────────────────────────────────────────────────────────────
echo "[3/4] Creating arm64 venv and installing dependencies..."

if [ ! -d "$VENV" ]; then
    echo "  Creating venv at $VENV..."
    arch -arm64 python3 -m venv "$VENV"
fi

"$VENV/bin/pip" install --upgrade pip --quiet

if [ ! -f "$JARVIS_HOME/requirements.txt" ]; then
    echo "ERROR: requirements.txt not found at $JARVIS_HOME/requirements.txt"
    echo "Generate it on the old Mac: cd ~/jarvis && ./venv/bin/pip freeze > requirements.txt"
    exit 1
fi

echo "  Installing from requirements.txt (this takes a few minutes)..."
"$VENV/bin/pip" install -r "$JARVIS_HOME/requirements.txt" --quiet

# Ensure PyInstaller is present (may not be in requirements.txt)
"$VENV/bin/pip" install pyinstaller --quiet

echo "  Dependencies installed OK"

# ── 4. Build the app ──────────────────────────────────────────────────────────
echo "[4/4] Building JARVIS.app..."
bash "$JARVIS_HOME/scripts/build_app.sh"
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/setup_new_mac.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts/setup_new_mac.sh
git commit -m "feat: add scripts/setup_new_mac.sh for one-command Apple Silicon setup"
```

---

## Task 8: Build, Fix Import Issues, and Verify

This task is iterative — PyInstaller often needs one or two missing hidden imports discovered at first launch. Follow the debug loop.

**Files:**
- No new files; may modify `jarvis.spec` if imports are missing

- [ ] **Step 1: Kill the running app first**

```bash
pkill -f "app/main.py" 2>/dev/null || true
pkill -f "ui/server.py" 2>/dev/null || true
sleep 1
```

- [ ] **Step 2: Run the build script**

```bash
cd ~/jarvis
bash scripts/build_app.sh 2>&1 | tee /tmp/jarvis_build.log
```

Expected: ends with the "NEXT STEP" banner. If PyInstaller errors, read the output carefully for `ModuleNotFoundError` or missing binary messages.

- [ ] **Step 3: Launch and check the permission prompts**

```bash
open ~/jarvis/JARVIS.app
```

Watch for:
- macOS permission dialog saying **"JARVIS" wants access to the camera** → click Allow
- macOS permission dialog saying **"JARVIS" wants access to the microphone** → click Allow

If the dialog says **"Python"** instead of **"JARVIS"**, the freeze didn't take — re-run the build and check that `dist/JARVIS.app` was actually built (not the old shell-script bundle).

- [ ] **Step 4: Verify the bubble appears and backend is live**

```bash
# Should return {"status":"ok"} within a few seconds of launch
sleep 5
curl -s http://127.0.0.1:8080/api/status
```

Expected: `{"status": "ok"}` (or similar non-error JSON)

- [ ] **Step 5: Check camera works from the frozen app**

In the JARVIS HUD, trigger a "what do you see" / room scan command.
In a second terminal:
```bash
tail -f ~/jarvis/jarvis_app.log
```

Expected log line: `[Camera] OpenCV capture succeeded` or `[Camera] ffmpeg succeeded on device 0`

If you see `not authorized to capture video` — the TCC reset didn't work. Run:
```bash
tccutil reset Camera com.elnatan.jarvis
# Then quit and relaunch JARVIS.app — grant the prompt
```

- [ ] **Step 6: Check mic works**

Click the orb in the bubble. Speak a short sentence. Confirm the orb enters "thinking" state and a reply is generated.

- [ ] **Step 7: Handle missing hidden imports (if app crashes at launch)**

If the frozen app crashes with `ModuleNotFoundError: No module named 'X'`:

1. Add `'X'` to the `hiddenimports` list in `jarvis.spec`
2. Re-run `bash scripts/build_app.sh`
3. Relaunch and check again

Common ones for this stack:
- `webview.platforms.cocoa` → already in spec; if still failing, add `webview.platforms.cocoa.BrowserView`
- `numpy._core` → add `numpy._core`, `numpy._core._multiarray_umath`
- `groq._streaming` → add to hiddenimports

- [ ] **Step 8: Commit final working spec (if it was modified)**

```bash
git add jarvis.spec
git commit -m "fix: tune PyInstaller hidden imports for working frozen JARVIS.app"
```

---

## Verification Checklist

After Task 8 completes successfully:

- [ ] `System Settings → Privacy & Security → Camera` shows **"JARVIS"** with access granted
- [ ] `System Settings → Privacy & Security → Microphone` shows **"JARVIS"** with access granted
- [ ] Camera capture logs `[Camera] OpenCV capture succeeded` (not `not authorized`)
- [ ] Mic click → orb goes listening → speaking → reply heard
- [ ] `POST /api/end_session` returns `{"ok": true}`
- [ ] `bash scripts/build_app.sh` rebuilds and reinstalls the working app in one run
- [ ] `scripts/setup_new_mac.sh` exists and is executable (ready for new Mac)
