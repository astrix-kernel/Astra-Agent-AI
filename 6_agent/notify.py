"""Desktop notification + sound."""
import subprocess, shutil, os


def _has(cmd):
    return shutil.which(cmd) is not None


def desktop_notify(title, body, urgency="normal"):
    """Kirim notifikasi desktop."""
    if _has("notify-send"):
        try:
            subprocess.Popen(
                ["notify-send", "-u", urgency, "-a", "Astrix Agent",
                 "-i", "utilities-terminal", title, body],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            pass
    return False


def play_sound(kind="done"):
    """Play sound — fallback ke berbagai player."""
    # Cari file sound
    sound_dir = os.path.expanduser("~/.astrix-agent/sounds")
    os.makedirs(sound_dir, exist_ok=True)
    sound_file = os.path.join(sound_dir, f"{kind}.oga")

    # Kalau file nggak ada, pakai system sound
    if not os.path.exists(sound_file):
        for candidate in [
            "/usr/share/sounds/freedesktop/stereo/complete.oga",
            "/usr/share/sounds/freedesktop/stereo/message.oga",
            "/usr/share/sounds/freedesktop/stereo/bell.oga",
        ]:
            if os.path.exists(candidate):
                sound_file = candidate
                break

    if not os.path.exists(sound_file):
        return False

    # Coba berbagai player
    for player in ["paplay", "pw-play", "aplay", "mpv", "ffplay"]:
        if _has(player):
            try:
                cmd = [player, sound_file]
                if player == "ffplay":
                    cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", sound_file]
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception:
                continue
    return False


def notify_done(title, body=""):
    """Task/goal selesai."""
    desktop_notify(f"✅ {title}", body or "Task selesai", "normal")
    play_sound("done")


def notify_error(title, body=""):
    """Ada error yang butuh perhatian."""
    desktop_notify(f"⚠️ {title}", body or "Butuh review", "critical")
    play_sound("error")


def notify_blocked(title, body=""):
    """Agent blocked, butuh keputusan user."""
    desktop_notify(f"🛑 {title}", body or "Agent butuh keputusan lu", "critical")
    play_sound("error")
