#!/usr/bin/env arch -arm64 /Users/elnatananbelu/jarvis/venv/bin/python3
"""
Multi-layer diagnostic for mic and camera issues.
Tests each component boundary to identify exactly where the failure occurs.
"""
import sys
import os

# Set up paths exactly as the app does
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

print("\n" + "="*70)
print("JARVIS MEDIA DIAGNOSTIC — Testing each layer")
print("="*70)

# ─────────────────────────────────────────────────────────────────────────────
# LAYER 1: Python Environment & Architecture
# ─────────────────────────────────────────────────────────────────────────────
print("\n[LAYER 1] Python Environment")
print("-" * 70)
import platform
print(f"  Architecture: {platform.machine()}")
print(f"  Python: {sys.version}")
print(f"  Executable: {sys.executable}")
print(f"  Working directory: {os.getcwd()}")

if platform.machine() != "arm64":
    print("  ⚠️  WARNING: Running as x86_64, should be arm64 for venv compatibility")
else:
    print("  ✓ Running as arm64")

# ─────────────────────────────────────────────────────────────────────────────
# LAYER 2: Dependencies Import
# ─────────────────────────────────────────────────────────────────────────────
print("\n[LAYER 2] Dependencies Import")
print("-" * 70)

deps = {
    "sounddevice": None,
    "numpy": None,
    "scipy": None,
    "cv2": None,
    "groq": None,
}

for name in deps:
    try:
        if name == "cv2":
            import cv2
            deps[name] = cv2.__version__
        elif name == "sounddevice":
            import sounddevice as sd
            deps[name] = sd.__version__
        elif name == "numpy":
            import numpy as np
            deps[name] = np.__version__
        elif name == "scipy":
            import scipy
            deps[name] = scipy.__version__
        elif name == "groq":
            from groq import Groq
            deps[name] = "installed"
        print(f"  ✓ {name}: {deps[name]}")
    except Exception as e:
        print(f"  ✗ {name}: {e}")
        deps[name] = None

# ─────────────────────────────────────────────────────────────────────────────
# LAYER 3: Microphone — Device Discovery
# ─────────────────────────────────────────────────────────────────────────────
print("\n[LAYER 3] Microphone — Device Discovery")
print("-" * 70)

if deps["sounddevice"]:
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        print(f"  Found {len(devices)} audio devices:")
        for i, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                print(f"    [{i}] {dev['name']} (inputs: {dev['max_input_channels']})")

        default_in = sd.query_devices(kind='input')
        print(f"\n  Default input device: {default_in['name']}")
        print(f"  ✓ Audio device discovery successful")
    except Exception as e:
        print(f"  ✗ Device query failed: {e}")
else:
    print("  ✗ Skipping (sounddevice not available)")

# ─────────────────────────────────────────────────────────────────────────────
# LAYER 4: Microphone — Permission & Stream Test
# ─────────────────────────────────────────────────────────────────────────────
print("\n[LAYER 4] Microphone — Permission & Stream Test")
print("-" * 70)

if deps["sounddevice"]:
    try:
        import sounddevice as sd
        import time

        print("  Attempting to open microphone stream...")
        stream = sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=256)
        stream.start()
        print("  ✓ Stream opened successfully")

        time.sleep(0.5)
        stream.stop()
        stream.close()
        print("  ✓ Stream closed cleanly")
        print("  ✓ MICROPHONE PERMISSION: GRANTED")

    except Exception as e:
        err_str = str(e).lower()
        if "permission" in err_str or "denied" in err_str or "not authorized" in err_str:
            print(f"  ✗ MICROPHONE PERMISSION: DENIED")
            print(f"  Error: {e}")
            print("\n  → Fix: Go to System Settings → Privacy & Security → Microphone")
            print("         Enable for: Terminal, Python, or JARVIS.app")
        else:
            print(f"  ✗ Stream failed (not permission): {e}")
else:
    print("  ✗ Skipping (sounddevice not available)")

# ─────────────────────────────────────────────────────────────────────────────
# LAYER 5: Camera — OpenCV Test
# ─────────────────────────────────────────────────────────────────────────────
print("\n[LAYER 5] Camera — OpenCV Test")
print("-" * 70)

if deps["cv2"]:
    try:
        import cv2
        import time

        print("  Attempting to open camera with AVFoundation backend...")
        cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)

        if not cap.isOpened():
            print("  ⚠️  AVFoundation failed, trying default backend...")
            cap.release()
            cap = cv2.VideoCapture(0)

        if cap.isOpened():
            print("  ✓ Camera opened successfully")

            # Try to capture a frame
            for attempt in range(5):
                ret, frame = cap.read()
                if ret and frame is not None:
                    h, w = frame.shape[:2]
                    print(f"  ✓ Captured frame: {w}x{h}")
                    print("  ✓ CAMERA PERMISSION: GRANTED (OpenCV)")
                    break
                time.sleep(0.1)
            else:
                print("  ✗ Camera opened but no frames captured")

            cap.release()
        else:
            print("  ✗ Camera failed to open")
            print("\n  → Fix: Go to System Settings → Privacy & Security → Camera")
            print("         Enable for: Terminal, Python, or JARVIS.app")

    except Exception as e:
        print(f"  ✗ OpenCV camera test failed: {e}")
else:
    print("  ✗ Skipping (OpenCV not available)")

# ─────────────────────────────────────────────────────────────────────────────
# LAYER 6: Camera — ffmpeg/AVFoundation Test
# ─────────────────────────────────────────────────────────────────────────────
print("\n[LAYER 6] Camera — ffmpeg/AVFoundation Test")
print("-" * 70)

import subprocess
import tempfile

FFMPEG = "/opt/homebrew/bin/ffmpeg"
if not os.path.exists(FFMPEG):
    FFMPEG = "ffmpeg"

print(f"  Using ffmpeg: {FFMPEG}")

try:
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        tmp_path = f.name

    print("  Attempting to capture single frame...")
    result = subprocess.run(
        [FFMPEG,
         "-f", "avfoundation",
         "-video_size", "640x480",
         "-framerate", "15",
         "-i", "0",
         "-frames:v", "1",
         "-f", "image2",
         "-y", tmp_path],
        capture_output=True,
        timeout=8
    )

    if result.returncode == 0 and os.path.getsize(tmp_path) > 0:
        size = os.path.getsize(tmp_path)
        print(f"  ✓ Captured frame: {size} bytes")
        print("  ✓ CAMERA PERMISSION: GRANTED (ffmpeg)")
    else:
        print(f"  ✗ ffmpeg failed (exit code {result.returncode})")
        stderr = result.stderr.decode(errors='ignore')
        if "not authorized" in stderr.lower() or "permission" in stderr.lower():
            print("  ✗ CAMERA PERMISSION: DENIED")
        print(f"\n  Error output:\n{stderr[:500]}")

    try:
        os.unlink(tmp_path)
    except:
        pass

except Exception as e:
    print(f"  ✗ ffmpeg test failed: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# LAYER 7: Groq API Key (for Whisper transcription)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[LAYER 7] Groq API Key")
print("-" * 70)

groq_key = os.environ.get("GROQ_API_KEY", "").strip()
if not groq_key:
    env_path = os.path.join(ROOT, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("GROQ_API_KEY="):
                    groq_key = line.split("=", 1)[1].strip()
                    break

if groq_key:
    masked = groq_key[:8] + "..." + groq_key[-4:] if len(groq_key) > 12 else "***"
    print(f"  ✓ GROQ_API_KEY found: {masked}")
else:
    print("  ✗ GROQ_API_KEY not found")
    print("     → Microphone will capture audio but transcription will fail")

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("DIAGNOSTIC SUMMARY")
print("="*70)

issues = []

if platform.machine() != "arm64":
    issues.append("❌ Architecture mismatch (running x86_64, venv is arm64)")

for name, version in deps.items():
    if version is None:
        issues.append(f"❌ Missing dependency: {name}")

if not groq_key:
    issues.append("⚠️  GROQ_API_KEY not configured (transcription will fail)")

if issues:
    print("\nIssues found:")
    for issue in issues:
        print(f"  {issue}")
else:
    print("\n✓ All layers passed!")
    print("\nIf mic/camera still don't work in the app:")
    print("  1. Check System Settings → Privacy & Security")
    print("  2. Ensure permissions are granted for the correct app")
    print("  3. Restart the JARVIS app completely")

print("="*70 + "\n")
