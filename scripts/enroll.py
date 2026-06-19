#!/usr/bin/env python3
"""Alfred enrollment — YOU run this on your Mac:

    ./venv/bin/python scripts/enroll.py

It tests your mic, then captures your face and voice references LOCALLY
(~/.alfred/enroll). Nothing leaves the machine. Grant Camera + Microphone when macOS
asks. (PIN, credentials, and people are in the other wizard: scripts/setup.py.)
"""
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

SR = 16000


def _enroll_dir():
    d = Path.home() / ".alfred" / "enroll"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _record(seconds: float, prompt: str):
    import sounddevice as sd
    try:
        input(f"  {prompt} — press Enter, then speak for {int(seconds)}s ")
    except (EOFError, KeyboardInterrupt):
        return None
    print("  ● recording…", flush=True)
    audio = sd.rec(int(seconds * SR), samplerate=SR, channels=1, dtype="int16")
    sd.wait()
    print("  ✓ done")
    return audio.flatten()


def mic_test() -> bool:
    print("\n── 1. Mic test ─────────────────────────────")
    try:
        import soundfile as sf
        audio = _record(4, "Say anything to Alfred")
        if audio is None:
            return False
        wav = str(_enroll_dir() / "_mictest.wav")
        sf.write(wav, audio, SR)
        from voice import local_stt
        text = local_stt.transcribe(wav)
        if text:
            print(f"  Alfred heard: “{text}”  — your mic works, sir.")
            return True
        print("  Heard nothing — check System Settings → Privacy → Microphone (allow Python/Terminal).")
        return False
    except Exception as e:
        print(f"  mic test failed: {e}")
        return False


def enroll_face() -> bool:
    print("\n── 2. Face enrollment ──────────────────────")
    try:
        import cv2
        try:
            input("  Look at your camera in good light — press Enter, hold still ")
        except (EOFError, KeyboardInterrupt):
            return False
        cap = cv2.VideoCapture(0)
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        best = None
        for _ in range(90):                       # ~3s of frames
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if len(cascade.detectMultiScale(gray, 1.1, 5)):
                best = frame
                break
            time.sleep(0.03)
        cap.release()
        if best is None:
            print("  No face detected — try better lighting, or allow Camera access, then re-run.")
            return False
        from security import identity
        print("  " + identity.enroll_face(best))
        if not memory_flag("face_encoding_ready"):
            print("  (Captured. For STRONG face recognition, install face_recognition — "
                  "I can set that up on your go; PIN secures you meanwhile.)")
        return True
    except Exception as e:
        print(f"  face enrollment failed: {e}")
        return False


def enroll_voice() -> bool:
    print("\n── 3. Voice enrollment ─────────────────────")
    try:
        import soundfile as sf
        phrases = ["Alfred, this is Elnatan.", "Good morning, Alfred.", "It's me, sir."]
        paths = []
        for i, ph in enumerate(phrases, 1):
            audio = _record(3, f"Read aloud: “{ph}”")
            if audio is None:
                break
            p = str(_enroll_dir() / f"voice_ref_{i}.wav")
            sf.write(p, audio, SR)
            paths.append(p)
        if not paths:
            return False
        from security import identity
        print("  " + identity.enroll_voice(paths))
        print("  (Samples kept for the cloned voice + strong speaker verification when its "
              "model is added; PIN/face secure you meanwhile.)")
        return True
    except Exception as e:
        print(f"  voice enrollment failed: {e}")
        return False


def memory_flag(key) -> bool:
    try:
        from memory import memory
        return bool(memory.get_flag(key, False))
    except Exception:
        return False


def main():
    print("=" * 52)
    print("  ALFRED — enrollment  (mic · face · voice)")
    print("  Local-only. Nothing leaves your Mac.")
    print("=" * 52)
    mic_test()
    enroll_face()
    enroll_voice()
    print("\n  Done, sir. (PIN + credentials + people: ./venv/bin/python scripts/setup.py)\n")


if __name__ == "__main__":
    main()
