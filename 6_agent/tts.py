"""Text-to-Speech pakai Piper — offline, cepat."""
import os, subprocess, shutil, tempfile
from pathlib import Path

VOICE_DIR = Path.home() / ".astrix-agent/voices"
DEFAULT_VOICE = VOICE_DIR / "en_US-amy-medium.onnx"
OUTPUT_WAV = Path.home() / ".astrix-agent/tts_last.wav"


def _has(cmd):
    return shutil.which(cmd) is not None


def _speak_with(cmd, wav):
    """Play WAV pakai player yang tersedia."""
    try:
        if cmd == "paplay":
            subprocess.run(["paplay", wav], check=True, timeout=30,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif cmd == "pw-play":
            subprocess.run(["pw-play", wav], check=True, timeout=30,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif cmd == "aplay":
            subprocess.run(["aplay", "-q", wav], check=True, timeout=30,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif cmd == "ffplay":
            subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", wav],
                          check=True, timeout=30,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def synthesize(text, voice=None, output=None):
    """
    Generate WAV dari text pakai Piper.
    Return: path ke WAV, atau None kalau gagal.
    """
    if not text or not text.strip():
        return None

    voice_path = Path(voice) if voice else DEFAULT_VOICE
    if not voice_path.exists():
        print(f"  ⚠️  Voice model nggak ada: {voice_path}")
        print(f"     Download dari: huggingface.co/rhasspy/piper-voices")
        return None

    out_path = Path(output) if output else OUTPUT_WAV
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Piper via CLI
    try:
        proc = subprocess.run(
            ["piper", "-m", str(voice_path), "-f", str(out_path)],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=60,
        )
        if proc.returncode != 0:
            print(f"  ⚠️  Piper error: {proc.stderr.decode()[:200]}")
            return None
        return str(out_path)
    except FileNotFoundError:
        print("  ⚠️  Piper CLI nggak ketemu. Install: pip install piper-tts")
        return None
    except Exception as e:
        print(f"  ⚠️  TTS error: {e}")
        return None


def speak(text, voice=None):
    """Synthesize + play. Fallback ke espeak-ng kalau Piper nggak ready."""
    # Coba Piper dulu
    if DEFAULT_VOICE.exists() and DEFAULT_VOICE.stat().st_size > 10000000 and _has("piper"):
        wav = synthesize(text, voice=voice)
        if wav:
            for player in ["pw-play", "paplay", "ffplay", "aplay"]:
                if _has(player):
                    if _speak_with(player, wav):
                        return True

    # Fallback: espeak-ng (robot, tapi selalu jalan)
    if _has("espeak-ng"):
        try:
            subprocess.run(
                ["espeak-ng", "-v", "id", "-s", "160", "-p", "55", text],
                check=True, timeout=60,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return True
        except Exception as e:
            print(f"  ⚠️  espeak-ng error: {e}")

    return False


def is_available():
    """Cek apakah TTS siap dipakai."""
    if not DEFAULT_VOICE.exists():
        return False
    if not _has("piper"):
        return False
    return True
