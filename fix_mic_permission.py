#!/usr/bin/env python3
"""
Standalone script to aggressively request macOS Microphone permission
for the JARVIS project.

Run this with:
  ./venv/bin/python3 fix_mic_permission.py

Keep System Settings > Privacy & Security > Microphone open while running.
This will keep trying to open the mic until you grant permission.
"""

import sounddevice as sd
import time
import sys

print("=== JARVIS Microphone Permission Fixer ===")
print("Keep System Settings → Privacy & Security → Microphone open.")
print("This will repeatedly try to access the mic to force the permission prompt.")
print("When the popup appears, click 'OK' to allow.")
print()

for attempt in range(1, 8):
    print(f"Attempt {attempt}/7 - Opening microphone...")
    try:
        stream = sd.InputStream(
            samplerate=16000,
            channels=1,
            dtype='int16',
            blocksize=1024
        )
        stream.start()
        # Keep it open for a while to make sure the system registers the request
        time.sleep(2.5)
        stream.stop()
        stream.close()
        print("  → Microphone opened successfully (permission likely granted).")
        print("\nDone! You should now see an entry in the Microphone list.")
        print("If it's still not there, try clicking the mic button inside the JARVIS app.")
        sys.exit(0)
    except Exception as e:
        msg = str(e).lower()
        if "permission" in msg or "denied" in msg or "not authorized" in msg:
            print("  → Permission denied or not yet granted. Popup should have appeared.")
            print("    Please click 'OK' in the permission dialog if you see one.")
        else:
            print(f"  → Error: {e}")
        if attempt < 7:
            print("  Waiting before next attempt...\n")
            time.sleep(1.5)

print("\nStill not working?")
print("Manual steps:")
print("1. In System Settings > Privacy & Security > Microphone, look for 'Terminal' or 'Python'")
print("2. Turn it on manually.")
print("3. Restart your JARVIS app.")