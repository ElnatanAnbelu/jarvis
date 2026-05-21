import sounddevice as sd
import numpy as np
import whisper
import tempfile
import scipy.io.wavfile as wav
import sys

_model = None

def load_model():
    global _model
    if _model is None:
        print("Loading voice model (one-time setup)...")
        _model = whisper.load_model("base")
        print("Voice model ready.")
    return _model

def listen(duration: int = 5, sample_rate: int = 16000) -> str:
    """Record audio and transcribe it. Returns the transcribed text."""
    print(f"Listening... (speak now, {duration}s)")
    audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='float32')
    sd.wait()
    print("Processing...")

    audio_np = np.squeeze(audio)
    model = load_model()
    result = model.transcribe(audio_np, language="en", fp16=False)
    text = result["text"].strip()
    return text

def listen_until_silence(sample_rate: int = 16000, silence_threshold: float = 0.01, max_seconds: int = 15) -> str:
    """Record until silence is detected, then transcribe."""
    print("Listening... (speak, then pause)")
    chunk_size = int(sample_rate * 0.5)
    chunks = []
    silent_chunks = 0
    max_silent = 3
    recording = False

    with sd.InputStream(samplerate=sample_rate, channels=1, dtype='float32') as stream:
        while len(chunks) < max_seconds * 2:
            chunk, _ = stream.read(chunk_size)
            rms = np.sqrt(np.mean(chunk**2))

            if rms > silence_threshold:
                recording = True
                silent_chunks = 0
                chunks.append(chunk)
            elif recording:
                chunks.append(chunk)
                silent_chunks += 1
                if silent_chunks >= max_silent:
                    break

    if not chunks:
        return ""

    audio_np = np.squeeze(np.concatenate(chunks))
    model = load_model()
    result = model.transcribe(audio_np, language="en", fp16=False)
    return result["text"].strip()


if __name__ == "__main__":
    text = listen_until_silence()
    print(f"You said: {text}")
