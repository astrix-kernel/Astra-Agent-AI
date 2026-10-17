"""Voice input-record mic + transcribe using faster-whisper."""

import os, wave, time, threading
import numpy as np
import sounddevice as sd
from pathlib import Path
from config import LOG_DIR


# Config. 
SAMPLE_RATE = 16000
CHANNELS = 1
MODEL_SIZE = "base"       # tiny, base, small, medium (base = balance)
LANGUAGE = "id"           # Indonesian; change to None for auto-detect
DEVICE = None             # None = default device; change to int to select device

_whisper_model = None
_recording = False
_audio_buffer = []
_stream = None


def _load_model():
    """Load the model once, reuse it continuously."""

    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        print(f"  🎤 Load Whisper '{MODEL_SIZE}' (sekali aja)...", flush=True)
        _whisper_model = WhisperModel(
            MODEL_SIZE,
            device="cpu",
            compute_type="int8",  # save RAM, fast on CPU
        )
        print(f"  ✅ Whisper ready", flush=True)
    return _whisper_model


def start_recording():
    """Start recording from the mic. Return True if successful."""

    global _recording, _audio_buffer, _stream

    if _recording:
        return False

    _audio_buffer = []
    _recording = True

    def callback(indata, frames, time_info, status):
        if _recording:
            _audio_buffer.append(indata.copy())

    try:
        _stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            callback=callback,
            device=DEVICE,
        )
        _stream.start()
        return True
    except Exception as e:
        _recording = False
        raise RuntimeError(f"Mic error: {e}")


def stop_recording(save_to=None):
    """Stop record, save WAV. Return path or None."""

    global _recording, _stream

    if not _recording:
        return None

    _recording = False

    if _stream:
        try:
            _stream.stop()
            _stream.close()
        except Exception:
            pass
        _stream = None

    if not _audio_buffer:
        return None

    # Join buffer
    audio = np.concatenate(_audio_buffer, axis=0).flatten()

    # Minimum check duration (0.3s)
    if len(audio) < SAMPLE_RATE * 0.3:
        return None

    # Normalize
    peak = np.abs(audio).max()
    if peak > 0:
        audio = audio / peak * 0.95

    # Save WAV
    if save_to is None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        save_to = LOG_DIR / "voice_last.wav"

    audio_int16 = (audio * 32767).astype(np.int16)
    with wave.open(str(save_to), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())

    return str(save_to)


def transcribe(audio_path):
    """Transcribe WAV to text — use a soundfile (a bug PyAV bypass)."""

    import soundfile as sf
    import numpy as np
    model = _load_model()

    audio, sr = sf.read(audio_path, dtype="float32")
    if sr != SAMPLE_RATE:
        ratio = SAMPLE_RATE / sr
        new_len = int(len(audio) * ratio)
        audio = np.interp(
            np.linspace(0, len(audio), new_len),
            np.arange(len(audio)),
            audio,
        ).astype("float32")

    segments, info = model.transcribe(
        audio,
        language=LANGUAGE,
        beam_size=1,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )
    text = "".join(s.text for s in segments).strip()
    return text


def is_recording():
    return _recording


# = = = = = = = = = = = high-level: one-shot = = = = = = = = = = = =
def record_and_transcribe(duration=None, silence_timeout=2.0):
    """
    Rekam sampai silence atau max duration, langsung transcribe.
    Return: text atau None.
    """
    import time as _t

    if not start_recording():
        return None

    if duration:
        _t.sleep(duration)

    wav = stop_recording()
    if not wav:
        return None

    return transcribe(wav)


# = = = = = = = = = = = TERMINAL MODE (interactive) = = = = = = = = = = = = =
def voice_cli():
    """Record via press Enter to start, Enter again to stop."""

    print("  🎤 Tekan Enter buat MULAI rekam...")
    input()
    print("  🔴 RECORDING... (Enter buat stop)")
    start_recording()

    stop_thread = threading.Thread(target=lambda: input())
    stop_thread.daemon = True
    stop_thread.start()

    # Wait for user Enter
    while stop_thread.is_alive():
        stop_thread.join(timeout=0.1)

    wav = stop_recording()
    if not wav:
        print("  ⚠️  Nggak ada audio ke-rekam")
        return None

    print("  🧠 Transcribing...")
    t0 = time.time()
    text = transcribe(wav)
    print(f"  ✅ ({time.time()-t0:.1f}s)")

    return text



# = = = = = = = = = = auto-stop on silence = = = = = = = = = = =
def record_until_silence(silence_duration=1.5, max_duration=30.0,
                        silence_threshold=0.05):
    """
    Rekam sampai user diem selama silence_duration detik.
    Return: text hasil transcribe, atau None.
    """
    import time as _t

    if not start_recording():
        return None

    t0 = _t.time()
    silence_start = None
    print("  🎤 Listening... (diem 2 detik buat auto-stop)")

    while True:
        _t.sleep(0.1)
        elapsed = _t.time() - t0

        # Max duration
        if elapsed > max_duration:
            print("  ⏱️  Max duration reached")
            break

        # Check last buffer volume
        if _audio_buffer:
            recent = _audio_buffer[-10:] if len(_audio_buffer) >= 10 else _audio_buffer
            import numpy as np
            try:
                rms = float(np.sqrt(np.mean(np.concatenate(recent) ** 2)))
            except Exception:
                rms = 0

            if rms < silence_threshold:
                if silence_start is None:
                    silence_start = _t.time()
                elif _t.time() - silence_start > silence_duration:
                    print("  🔇 Silence detected, stop")
                    break
            else:
                silence_start = None  # reset if there is another sound

    wav = stop_recording()
    if not wav:
        return None

    print("  🧠 Transcribing...")
    return transcribe(wav)


def voice_auto():
    """One-shot: click → say → auto-stop → return text."""

    return record_until_silence()
