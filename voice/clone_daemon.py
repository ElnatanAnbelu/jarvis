#!/usr/bin/env python3
"""Voice cloning daemon — uses Chatterbox TTS with MCU character reference audio.

Keeps model loaded in memory, serves requests via Unix socket.
Clones Paul Bettany (JARVIS), Kerry Condon (FRIDAY), Jennifer Connelly (KAREN).
VERONICA falls back to Kokoro bm_lewis (no MCU reference exists).

Protocol: length-prefixed JSON request → length-prefixed WAV response.
"""

import sys
import os
import socket
import json
import struct
import threading
import io
from pathlib import Path

SOCKET_PATH = str(Path(__file__).parent / "clone.sock")
SAMPLES_DIR = Path(__file__).parent / "samples"

REFERENCE_AUDIO = {
    "JARVIS":   str(SAMPLES_DIR / "jarvis_ref.wav"),
    "FRIDAY":   str(SAMPLES_DIR / "friday_ref.wav"),
    "KAREN":    str(SAMPLES_DIR / "karen_ref.wav"),
    "VERONICA": str(SAMPLES_DIR / "friday_ref.wav"),  # fallback: use Friday ref
}

REFERENCE_TEXT = {
    "JARVIS":   (SAMPLES_DIR / "jarvis_ref_text.txt").read_text().strip() if (SAMPLES_DIR / "jarvis_ref_text.txt").exists() else "",
    "FRIDAY":   (SAMPLES_DIR / "friday_ref_text.txt").read_text().strip() if (SAMPLES_DIR / "friday_ref_text.txt").exists() else "",
    "KAREN":    (SAMPLES_DIR / "karen_ref_text.txt").read_text().strip() if (SAMPLES_DIR / "karen_ref_text.txt").exists() else "",
    "VERONICA": (SAMPLES_DIR / "friday_ref_text.txt").read_text().strip() if (SAMPLES_DIR / "friday_ref_text.txt").exists() else "",
}


CKPT_DIR = Path.home() / ".cache/huggingface/hub/models--ResembleAI--chatterbox/snapshots/ef85ce7bef2f3f1a74d0d837d379d2fcb68203cd"


def load_model():
    """Load Chatterbox model. Detects MPS (Apple Silicon) automatically."""
    import perth
    import torch
    from chatterbox.tts import ChatterboxTTS

    # PerthImplicitWatermarker is None on Apple Silicon — use dummy instead
    perth.PerthImplicitWatermarker = perth.DummyWatermarker

    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"

    print(f"Loading Chatterbox on {device}...", flush=True)
    model = ChatterboxTTS.from_local(str(CKPT_DIR), device=device)

    print("Chatterbox ready.", flush=True)
    return model


def synthesize(model, text: str, agent: str) -> bytes:
    """Clone the agent's voice and synthesize text. Returns WAV bytes."""
    import torchaudio, io as _io

    ref_audio = REFERENCE_AUDIO.get(agent, REFERENCE_AUDIO["JARVIS"])
    if not os.path.exists(ref_audio):
        raise FileNotFoundError(f"Reference audio not found: {ref_audio}")

    wav = model.generate(text, audio_prompt_path=ref_audio)
    buf = _io.BytesIO()
    torchaudio.save(buf, wav, model.sr, format="wav")
    return buf.getvalue()


def handle_client(conn, model):
    try:
        raw_len = conn.recv(4)
        if not raw_len or len(raw_len) < 4:
            return
        msg_len = struct.unpack(">I", raw_len)[0]
        data = b""
        while len(data) < msg_len:
            chunk = conn.recv(min(4096, msg_len - len(data)))
            if not chunk:
                break
            data += chunk
        req = json.loads(data.decode())
        text  = req.get("text", "").strip()
        agent = req.get("agent", "JARVIS").upper()

        if not text:
            conn.sendall(struct.pack(">I", 0))
            return

        wav = synthesize(model, text, agent)
        conn.sendall(struct.pack(">I", len(wav)) + wav)
    except Exception as e:
        print(f"Error: {e}", flush=True)
        try:
            conn.sendall(struct.pack(">I", 0))
        except Exception:
            pass
    finally:
        conn.close()


def main():
    print("Loading Chatterbox voice cloning model...", flush=True)
    model = load_model()

    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o666)
    server.listen(5)
    print(f"Clone daemon listening on {SOCKET_PATH}", flush=True)

    while True:
        conn, _ = server.accept()
        threading.Thread(target=handle_client, args=(conn, model), daemon=True).start()


if __name__ == "__main__":
    main()
