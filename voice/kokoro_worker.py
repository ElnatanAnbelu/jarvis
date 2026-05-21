#!/usr/bin/env python3
"""Kokoro TTS worker — called as subprocess by server.py.

Usage: kokoro_worker.py <AGENT> <output_wav_path>
       Text is read from stdin.

Voice mapping (Kokoro preset voices):
  JARVIS   -> bm_george  (British male, Paul Bettany-like)
  FRIDAY   -> bf_emma    (British female, closest to Kerry Condon's Irish lilt)
  KAREN    -> af_bella   (American female, warm like Jennifer Connelly)
  VERONICA -> af_sky     (American female, precise/clinical)
"""

import sys
import os
import numpy as np
from pathlib import Path

VOICE_DIR   = Path(__file__).parent
MODEL_PATH  = str(VOICE_DIR / "kokoro-v1.0.onnx")
VOICES_PATH = str(VOICE_DIR / "voices-v1.0.bin")
SAMPLE_RATE = 24000

VOICE_MAP = {
    "JARVIS":   "bm_george",
    "FRIDAY":   "bf_emma",
    "KAREN":    "af_bella",
    "VERONICA": "af_sky",
}


def synthesize(text: str, voice_name: str, speed: float = 1.0) -> np.ndarray:
    """Run Kokoro synthesis, patching the speed dtype bug in kokoro-onnx."""
    import onnxruntime as rt
    from kokoro_onnx import Kokoro
    from kokoro_onnx.config import MAX_PHONEME_LENGTH

    kokoro = Kokoro(MODEL_PATH, VOICES_PATH)
    voice_embed = kokoro.get_voice_style(voice_name)

    # Phonemize the text
    phonemes = kokoro.tokenizer.phonemize(text, "en-us")
    batches  = kokoro._split_phonemes(phonemes)

    audio_parts = []
    for batch in batches:
        batch = batch[:MAX_PHONEME_LENGTH]
        tokens = np.array(kokoro.tokenizer.tokenize(batch), dtype=np.int64)
        style  = np.array(voice_embed[len(tokens)], dtype=np.float32)
        t_arr  = [[0, *tokens.tolist(), 0]]

        # Fix: pass speed as float32 (kokoro-onnx 0.5 sends int32, breaking newer exports)
        inputs = {
            "input_ids": t_arr,
            "style":     style,
            "speed":     np.array([speed], dtype=np.float32),
        }
        part = kokoro.sess.run(None, inputs)[0].squeeze()
        audio_parts.append(part)

    return np.concatenate(audio_parts) if audio_parts else np.array([], dtype=np.float32)


def main():
    if len(sys.argv) < 3:
        sys.exit("Usage: kokoro_worker.py <AGENT> <output.wav>")

    agent   = sys.argv[1].upper()
    outpath = sys.argv[2]
    text    = sys.stdin.read().strip()
    if not text:
        sys.exit("No text on stdin")

    voice = VOICE_MAP.get(agent, "bm_george")

    try:
        import soundfile as sf
        audio = synthesize(text, voice)
        sf.write(outpath, audio, SAMPLE_RATE)
    except Exception as e:
        sys.exit(f"Kokoro error: {e}")


if __name__ == "__main__":
    main()
