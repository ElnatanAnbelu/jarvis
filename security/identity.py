"""Identity lock — JARVIS only acts for Elnatan.

On open/wake, JARVIS tries to recognize him by face + voice (local, free). If
biometrics are unavailable or fail, it falls back to a PIN or Telegram approval.
A successful auth opens a trusted session (TTL-bounded); the gate can require a
trusted session before real actions when 'locked' mode is on.

Face/voice are best-effort and degrade gracefully: with no camera/model/enrollment
they return False so the PIN/Telegram fallback takes over — never a hard failure.
PIN is stored salted-hashed in jarvis.db meta (never plaintext).
"""
import hashlib
import hmac
import os
import secrets
import time

from memory import memory

_SESSION_TTL = int(os.environ.get("JARVIS_SESSION_TTL", "3600"))  # trusted-session seconds


# ── PIN (salted hash, never plaintext) ────────────────────────────────────────
def set_pin(pin: str) -> str:
    if not pin or len(str(pin)) < 4:
        return "PIN must be at least 4 digits, sir."
    salt = secrets.token_hex(8)
    digest = hashlib.sha256((salt + str(pin)).encode()).hexdigest()
    memory.set_flag("identity_pin", f"{salt}${digest}")
    return "PIN set."


def has_pin() -> bool:
    return "$" in str(memory.get_flag("identity_pin", ""))


def verify_pin(pin: str) -> bool:
    stored = str(memory.get_flag("identity_pin", ""))
    if "$" not in stored:
        return False
    salt, digest = stored.split("$", 1)
    candidate = hashlib.sha256((salt + str(pin or "")).encode()).hexdigest()
    return hmac.compare_digest(candidate, digest)


# ── biometrics (best-effort; graceful when unavailable) ────────────────────────
def _enroll_dir():
    import pathlib
    d = pathlib.Path.home() / ".alfred" / "enroll"
    d.mkdir(parents=True, exist_ok=True)
    return d


def enroll_face(image_bgr) -> str:
    """Store sir's reference face (a cv2 BGR frame). If face_recognition (dlib) is
    installed, also store a strong 128-d encoding for real matching; otherwise the
    image is kept for when that lib is added. Sets the enrolled flag."""
    try:
        import cv2
        path = str(_enroll_dir() / "face_ref.png")
        cv2.imwrite(path, image_bgr)
        memory.set_flag("face_enrolled", True)
        memory.set_flag("face_ref_path", path)
        try:
            import face_recognition, numpy as np
            rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            encs = face_recognition.face_encodings(rgb)
            if encs:
                np.save(str(_enroll_dir() / "face_enc.npy"), encs[0])
                memory.set_flag("face_encoding_ready", True)
        except Exception:
            pass
        return "Face enrolled."
    except Exception as e:
        return f"Face enrollment failed: {e}"


def enroll_voice(sample_paths) -> str:
    """Store sir's reference voice samples (paths under the enroll dir). Sets the flag.
    Strong speaker verification activates when an embedding lib (resemblyzer) is present;
    the samples also feed the cloned voice."""
    try:
        paths = [str(p) for p in (sample_paths or [])]
        memory.set_flag("voice_enrolled", True)
        memory.set_flag("voice_ref_count", len(paths))
        # If the speaker-embedding stack is present, compute and store a reference
        # embedding now so verify_voice() can do a real match. Best-effort: if the
        # lib/samples aren't usable we still mark enrolled (samples feed the clone)
        # and verify_voice() degrades gracefully to PIN/face.
        try:
            import numpy as np
            from resemblyzer import VoiceEncoder, preprocess_wav
            enc = VoiceEncoder()
            embs = []
            for p in paths:
                try:
                    embs.append(enc.embed_utterance(preprocess_wav(p)))
                except Exception:
                    continue
            if embs:
                ref = np.mean(np.stack(embs), axis=0)
                np.save(str(_enroll_dir() / "voice_emb.npy"), ref)
                memory.set_flag("voice_embedding_ready", True)
        except Exception:
            pass
        return "Voice enrolled."
    except Exception as e:
        return f"Voice enrollment failed: {e}"


def verify_face() -> bool:
    """STRONG local face match — real recognition via face_recognition (dlib) against the
    enrolled 128-d encoding. If that lib isn't installed we DON'T fake it from mere face
    presence (that would false-accept anyone) — we return False so the PIN/Telegram
    fallback takes over. Never a hard failure."""
    try:
        if not memory.get_flag("face_encoding_ready", False):
            return False
        import os
        enc_path = str(_enroll_dir() / "face_enc.npy")
        if not os.path.exists(enc_path):
            return False
        import time
        import cv2, numpy as np, face_recognition
        cap = cv2.VideoCapture(0)
        for _ in range(20):                       # WARM UP — first frames are black
            cap.read()
            time.sleep(0.05)
        live = None
        for _ in range(60):                       # up to ~3s to get a well-lit face
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            if float(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean()) < 15:
                time.sleep(0.03)
                continue
            encs = face_recognition.face_encodings(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if encs:
                live = encs[0]
                break
            time.sleep(0.03)
        cap.release()
        if live is None:
            return False
        ref = np.load(enc_path)
        return bool(face_recognition.compare_faces([ref], live, tolerance=0.5)[0])
    except Exception:
        return False


_VOICE_MATCH_THRESHOLD = float(os.environ.get("JARVIS_VOICE_MATCH_THRESHOLD", "0.75"))


def _voice_capture_seconds() -> float:
    return float(os.environ.get("JARVIS_VOICE_CAPTURE_SEC", "3"))


def verify_voice() -> bool:
    """STRONG local speaker verification — real speaker-embedding match (resemblyzer's
    VoiceEncoder) of a fresh mic sample against the enrolled reference embedding.

    Honest degradation (never a silent placeholder, never a hard failure):
      * resemblyzer / sounddevice not installed, or no enrolled reference  → log WHY and
        return False so PIN/face carry identity.
      * lib present + enrollment ready → capture ~3s of mic audio, embed it, and accept
        only if cosine similarity to the reference clears the threshold.

    Enrollment stores the reference embedding at <enroll>/voice_emb.npy (written by
    enroll_voice when the lib is available)."""
    import pathlib

    def _log(msg, **kw):
        try:
            from obs.log import log_event
            log_event("identity.verify_voice", level="info", detail=msg, **kw)
        except Exception:
            pass

    if not memory.get_flag("voice_enrolled", False):
        _log("no enrolled voice — falling back to PIN/face", available=False)
        return False

    emb_path = _enroll_dir() / "voice_emb.npy"
    if not emb_path.exists():
        _log("voice enrolled but no reference embedding — install resemblyzer and "
             "re-enroll to enable speaker match; falling back", available=False)
        return False

    try:
        import numpy as np
        from resemblyzer import VoiceEncoder
        import sounddevice as sd
    except Exception as e:  # lib genuinely unavailable — be explicit, don't pretend
        _log(f"speaker-embedding stack unavailable ({type(e).__name__}: {e}) — "
             f"falling back to PIN/face", available=False)
        return False

    try:
        ref = np.load(str(emb_path))
        sr = 16000
        seconds = _voice_capture_seconds()
        audio = sd.rec(int(seconds * sr), samplerate=sr, channels=1, dtype="float32")
        sd.wait()
        wav = np.asarray(audio, dtype="float32").flatten()
        if wav.size == 0 or float(np.abs(wav).mean()) < 1e-4:
            _log("captured silence — cannot verify speaker; falling back", available=True)
            return False
        live = VoiceEncoder().embed_utterance(wav)
        ref = ref / (np.linalg.norm(ref) or 1.0)
        live = live / (np.linalg.norm(live) or 1.0)
        sim = float(np.dot(ref, live))
        ok = sim >= _VOICE_MATCH_THRESHOLD
        _log(f"speaker similarity {sim:.3f} (threshold {_VOICE_MATCH_THRESHOLD:.2f})",
             available=True, matched=ok)
        return ok
    except Exception as e:
        _log(f"speaker verification errored ({type(e).__name__}: {e}) — falling back",
             available=True)
        return False


def biometrics_ready() -> bool:
    return bool(memory.get_flag("face_enrolled", False) or memory.get_flag("voice_enrolled", False))


# ── trusted session ───────────────────────────────────────────────────────────
def mark_trusted() -> None:
    memory.set_flag("trusted_until", str(int(time.time()) + _SESSION_TTL))


def is_trusted() -> bool:
    try:
        return int(str(memory.get_flag("trusted_until", "0"))) > int(time.time())
    except Exception:
        return False


def lock() -> str:
    memory.set_flag("trusted_until", "0")
    return "🔒 Locked, sir. I'll need to confirm it's you."


# ── the entry point ────────────────────────────────────────────────────────────
def authenticate(pin: str = None) -> dict:
    """Try biometric (face AND voice), else PIN. Opens a trusted session on success.
    Returns {ok, method}."""
    if verify_face() and verify_voice():
        mark_trusted()
        return {"ok": True, "method": "biometric"}
    if pin is not None and verify_pin(pin):
        mark_trusted()
        return {"ok": True, "method": "pin"}
    return {"ok": False, "method": None}
