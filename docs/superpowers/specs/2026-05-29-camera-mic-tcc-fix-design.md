# Design: Durable Camera/Mic Fix via a Frozen, Signed JARVIS.app

**Date:** 2026-05-29
**Status:** Approved (design phase)
**Author:** JARVIS dev session

## Problem

In the JARVIS macOS desktop app, the **camera does not work** and the **mic is
unreliable across machines**.

### Root cause (confirmed by layered diagnostics)

- All camera capture (`cv2.VideoCapture`, ffmpeg/avfoundation) and all mic
  capture (`sounddevice.InputStream`) live in `app/main.py`'s `JsApi` class —
  the **pywebview front-end process**. The Flask backend (`ui/server.py`) has
  **no** live camera/mic capture.
- `JARVIS.app` is ad-hoc signed, but its launcher `exec`s an **external**
  interpreter: `venv/bin/python3`, which is a symlink chain resolving to
  `/Library/Developer/CommandLineTools/.../Python.app/Contents/MacOS/Python`.
  That framework Python is **its own app bundle** with its own identity.
- Therefore macOS TCC attributes camera/mic requests to **"Python"**, never to
  **"JARVIS" (`com.elnatan.jarvis`)**.
- Evidence: mic works because it was granted to the Python identity in a prior
  session; camera fails with `OpenCV: not authorized to capture video
  (status 0)` because camera was never granted to that identity.
- The `arch -arm64` wrapper in the launcher is unnecessary — `venv/bin/python3`
  already runs as arm64 by default — and the extra exec layer further muddies
  TCC attribution.

### Non-goals

- Freezing the entire backend system (brain, memory, voice daemons, whatsapp
  node, ONNX models) into a portable app. Out of scope — high effort, not
  required to fix camera/mic.
- Migrating to the native SwiftUI shell (`JARVISApp/`). Deferred.

## Target environment

- This Mac (Apple Silicon, arm64) for the next few days.
- A new **Apple Silicon (M-series)** Mac arriving soon. The fix must be
  reproducible there via a one-command build/migration script.
- TCC grants are inherently per-machine and cannot transfer; a stable bundle
  identity means the user grants "JARVIS" **once** per machine and it sticks.

## Approach (chosen: "A")

Use **PyInstaller** (already installed in the venv) to freeze **only the
front-end** (`app/main.py`) into `JARVIS.app` with an embedded arm64 Python.
Camera/mic capture then runs inside the frozen binary, so TCC attributes to
`com.elnatan.jarvis`. The Flask backend continues to launch as a venv
subprocess, unchanged.

## Architecture

```
JARVIS.app  (frozen, signed, com.elnatan.jarvis)
└─ embedded arm64 Python + GUI/capture deps
   ├─ pywebview window (bubble + HUD)
   └─ JsApi: sounddevice (mic), cv2/ffmpeg (camera)   ← TCC = "JARVIS"
        │
        │ spawns subprocess
        ▼
   venv/bin/python3 ui/server.py   (Flask backend, UNCHANGED)
   └─ brain / memory / voice / models / tools
```

### Freeze boundary

**Inside the frozen app (hidden imports / collected):**
- `webview` (+ `webview.platforms.cocoa`)
- `AppKit`, `objc`, `Foundation` (pyobjc) — used for screen size + app icon
- `sounddevice` (+ `_sounddevice_data`, `cffi`)
- `cv2`
- `numpy`
- `scipy.io.wavfile`
- `groq`

**Outside (stays venv subprocess, not frozen):**
- `ui/server.py` (Flask) and everything it imports: `brain/`, `memory/`,
  `voice/`, prompts, models, tools.

### Required code changes to `app/main.py`

1. **`end_session` refactor.** Today `_on_closed` → `_summarize_session` imports
   `memory.memory`, `anthropic`, and `voice.speak` *inside the front-end*,
   which would drag the backend into the freeze. Replace with: on close, the
   front-end fires `POST http://127.0.0.1:8080/api/end_session`; the **backend**
   performs the Haiku session summary (moving the existing `_summarize_session`
   logic into a new Flask route in `ui/server.py`). The front-end no longer
   imports `memory`, `anthropic`, or `voice`.

2. **Frozen-aware `ROOT`.** When `getattr(sys, "frozen", False)` is true,
   `__file__`-based `ROOT` is invalid. Resolve the project home from the
   `JARVIS_HOME` environment variable, defaulting to `~/jarvis`. Use it to
   locate `venv/bin/python3` and `ui/server.py` for the backend subprocess.

3. **Skip the arch re-exec when frozen.** Gate the existing arm64 re-exec guard
   behind `not getattr(sys, "frozen", False)`. The frozen binary is already
   arm64.

4. **Backend launch command.** Keep launching Flask via
   `venv/bin/python3 ui/server.py` (drop the redundant `arch -arm64` prefix;
   the venv python is arm64 by default). Resolve the path via `JARVIS_HOME`.

### `jarvis.spec` (PyInstaller)

- `entry`: `app/main.py`
- `name`: `JARVIS`
- `windowed`/`.app` bundle mode, `target_arch='arm64'`
- `hiddenimports`: the "inside" list above
- `collect_all` / `collect_data` as needed for `sounddevice`, `cv2`, `webview`
- `datas`: `app/icon.icns`
- `BUNDLE` block with:
  - `bundle_identifier='com.elnatan.jarvis'`
  - `info_plist`: `NSCameraUsageDescription`, `NSMicrophoneUsageDescription`,
    `LSUIElement=True` (floating accessory bubble),
    `CFBundleName='JARVIS'`

### Signing & TCC

- Ad-hoc codesign the finished `.app` (deep) with an entitlements file granting
  `com.apple.security.device.camera` and
  `com.apple.security.device.audio-input`, identifier `com.elnatan.jarvis`.
- `tccutil reset Camera com.elnatan.jarvis`
- `tccutil reset Microphone com.elnatan.jarvis`
- Launch → grant the camera (and mic) prompt, which now names **"JARVIS"**.

### Build & migration scripts

- **`scripts/build_app.sh`** (this Mac + new Mac, repeatable):
  1. Verify venv + `pyinstaller` present.
  2. `pyinstaller --clean -y jarvis.spec` → `dist/JARVIS.app`.
  3. Deep codesign with entitlements + identifier.
  4. Replace `~/jarvis/JARVIS.app` with the freshly built bundle.
  5. `tccutil reset` Camera + Microphone for `com.elnatan.jarvis`.
  6. Print the "launch & grant" instruction.

- **`scripts/setup_new_mac.sh`** (new Apple Silicon Mac, bare → working):
  1. Install Homebrew deps (`ffmpeg`).
  2. Create the arm64 venv, `pip install -r requirements.txt` (+ `pyinstaller`).
  3. Call `build_app.sh`.

## Data flow

1. User launches `JARVIS.app` (frozen).
2. Frozen process sets `JARVIS_HOME` (default `~/jarvis`), spawns
   `venv/bin/python3 ui/server.py`, waits for `http://127.0.0.1:8080/api/status`.
3. pywebview opens the bubble + hidden HUD pointed at the Flask URLs.
4. User clicks the orb → JS calls `window.pywebview.api.start_recording()` →
   `JsApi` opens the mic via `sounddevice` (TCC = JARVIS) → transcribes via Groq.
5. Camera/room-scan → `JsApi.capture_frame()` via `cv2`/ffmpeg (TCC = JARVIS).
6. On close → front-end `POST /api/end_session` → backend writes the summary.

## Error handling

- Frozen app cannot locate `JARVIS_HOME`/venv/`ui/server.py` → log a clear
  fatal error to `jarvis_app.log` and exit non-zero.
- Camera: `cv2` primary, ffmpeg (homebrew) fallback retained; on total failure,
  surface a message pointing to System Settings → Privacy → Camera.
- TCC denial after grant attempt → user-facing hint + `tccutil reset` guidance.
- Backend subprocess fails to start within timeout → dump `flask.log` and exit.

## Testing & verification

- **Layer check:** rerun `test_media_layers.py` (existing) — all layers pass.
- **Identity check:** after build + launch, the camera permission prompt and the
  System Settings → Privacy entries name **"JARVIS"**, not "Python"/"Terminal".
- **Camera:** trigger a frame capture from the running frozen app; confirm a
  non-empty JPEG and `[Camera] ... succeeded` in the log.
- **Mic:** click the orb, speak, confirm transcription returns text under the
  frozen identity.
- **Backend:** bubble + HUD load; `/api/status` healthy; `end_session` writes a
  summary on close.
- **Reproducibility:** `scripts/build_app.sh` rebuilds the working `.app` from
  clean in one command.

## Risks

- PyInstaller may need iterative hidden-import / data-collection tuning for
  `sounddevice`, `cv2`, and the pywebview cocoa backend. Mitigated by the small
  freeze boundary (front-end only).
- Ad-hoc signature changes invalidate TCC grants on rebuild; the build script
  resets TCC each run so the user re-grants once after a rebuild (acceptable).
- `pyobjc` (`AppKit`) collection under PyInstaller can be finicky; if it fails,
  the screen-size/icon code is already wrapped in try/except and degrades
  gracefully.
