#!/usr/bin/env python3
"""Kokoro TTS daemon — keeps model loaded in memory, serves requests via Unix socket.

Run once at startup. server.py sends requests to this daemon for instant TTS.
"""

import sys
import os
import socket
import json
import struct
import threading
import numpy as np
from pathlib import Path

SOCKET_PATH = str(Path(__file__).parent / "kokoro.sock")
VOICE_DIR   = Path(__file__).parent
MODEL_PATH  = str(VOICE_DIR / "kokoro-v1.0.onnx")
VOICES_PATH = str(VOICE_DIR / "voices-v1.0.bin")
SAMPLE_RATE = 24000
MAX_PHONEME = 510

VOICE_MAP = {
    "JARVIS":   "bm_george",
    "FRIDAY":   "bf_emma",
    "KAREN":    "af_bella",
    "VERONICA": "af_sky",
}


def load_kokoro():
    from kokoro_onnx import Kokoro
    return Kokoro(MODEL_PATH, VOICES_PATH)


def synthesize(kokoro, text: str, voice_name: str, speed: float = 1.0) -> bytes:
    import soundfile as sf
    import io

    voice_embed = kokoro.get_voice_style(voice_name)
    phonemes = kokoro.tokenizer.phonemize(text, "en-us")
    batches = kokoro._split_phonemes(phonemes)
    audio_parts = []
    for batch in batches:
        batch = batch[:MAX_PHONEME]
        tokens = np.array(kokoro.tokenizer.tokenize(batch), dtype=np.int64)
        style  = np.array(voice_embed[len(tokens)], dtype=np.float32)
        t_arr  = [[0, *tokens.tolist(), 0]]
        inputs = {
            "input_ids": t_arr,
            "style":     style,
            "speed":     np.array([speed], dtype=np.float32),
        }
        part = kokoro.sess.run(None, inputs)[0].squeeze()
        audio_parts.append(part)
    audio = np.concatenate(audio_parts) if audio_parts else np.zeros(1, dtype=np.float32)
    buf = io.BytesIO()
    sf.write(buf, audio, SAMPLE_RATE, format="WAV")
    return buf.getvalue()


def handle_client(conn, kokoro):
    try:
        # Read 4-byte length prefix, then JSON request
        raw_len = conn.recv(4)
        if not raw_len:
            return
        msg_len = struct.unpack(">I", raw_len)[0]
        data = b""
        while len(data) < msg_len:
            chunk = conn.recv(min(4096, msg_len - len(data)))
            if not chunk:
                break
            data += chunk
        req = json.loads(data.decode())
        text  = req.get("text", "")
        agent = req.get("agent", "JARVIS").upper()
        speed = float(req.get("speed", 1.0))
        voice = VOICE_MAP.get(agent, "bm_george")

        wav = synthesize(kokoro, text, voice, speed)
        # Send 4-byte length + WAV bytes
        conn.sendall(struct.pack(">I", len(wav)) + wav)
    except Exception as e:
        err = json.dumps({"error": str(e)}).encode()
        try:
            conn.sendall(struct.pack(">I", 0) + err)
        except Exception:
            pass
    finally:
        conn.close()


def main():
    if not (os.path.exists(MODEL_PATH) and os.path.exists(VOICES_PATH)):
        print("ERROR: Model files not found", file=sys.stderr)
        sys.exit(1)

    print("Loading Kokoro model...", flush=True)
    kokoro = load_kokoro()
    print("Kokoro ready.", flush=True)

    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o666)
    server.listen(10)
    print(f"Listening on {SOCKET_PATH}", flush=True)

    while True:
        conn, _ = server.accept()
        threading.Thread(target=handle_client, args=(conn, kokoro), daemon=True).start()


if __name__ == "__main__":
    main()
