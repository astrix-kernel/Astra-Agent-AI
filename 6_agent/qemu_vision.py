"""QEMU Vision — launch QEMU, screenshot, analyze visual."""

import os, subprocess, time, signal, shutil, socket
from pathlib import Path
import numpy as np

QEMU_SOCKET = "/tmp/astrix-qemu-monitor.sock"
QEMU_PID = Path.home() / ".astrix-agent/qemu.pid"
QEMU_LOG = Path.home() / ".astrix-agent/qemu-agent.log"
SHOTS = Path.home() / ".astrix-agent/screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)


def _has(cmd):
    return shutil.which(cmd) is not None


def _qemu_bin():
    for b in ["qemu-system-x86_64", "qemu-system-x86_64-gtk"]:
        if _has(b):
            return b
    return None


def is_installed():
    return _qemu_bin() is not None


def is_running():
    if not QEMU_PID.exists():
        return False
    try:
        pid = int(QEMU_PID.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError, OSError):
        return False


def launch(disk_image, ram="512", boot_timeout=15, extra=None):
    if is_running():
        return True, "QEMU udah jalan"
    binary = _qemu_bin()
    if not binary:
        return False, "QEMU nggak keinstall"

    disk = Path(disk_image)
    if not disk.exists():
        from config import ASTRIX_ROOT
        disk = ASTRIX_ROOT / disk_image
        if not disk.exists():
            return False, f"Disk image nggak ada: {disk_image}"

    try:
        os.unlink(QEMU_SOCKET)
    except FileNotFoundError:
        pass

    cmd = [
        binary,
        "-drive", f"file={disk},format=raw,if=virtio",
        "-m", ram, "-display", "none", "-vga", "std",
        "-monitor", f"unix:{QEMU_SOCKET},server,nowait",
        "-serial", f"file:{QEMU_LOG}",
        "-daemonize", "-pidfile", str(QEMU_PID),
    ]
    if extra:
        cmd.extend(extra)

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return False, f"QEMU gagal: {r.stderr[:200]}"
        for _ in range(50):
            if os.path.exists(QEMU_SOCKET):
                break
            time.sleep(0.1)
        return True, "QEMU started"
    except Exception as e:
        return False, str(e)


def stop():
    """Stop QEMU — try pid, pgrep, and pkill."""

    killed = False

    if QEMU_PID.exists():
        try:
            pid = int(QEMU_PID.read_text().strip())
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(1)
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                killed = True
            except ProcessLookupError:
                pass
            QEMU_PID.unlink()
        except Exception:
            pass

    if not killed:
        for pattern in ["qemu-system-x86_64", "qemu-system"]:
            r = subprocess.run(["pgrep", "-f", pattern],
                             capture_output=True, text=True)
            if r.stdout.strip():
                subprocess.run(["pkill", "-9", "-f", pattern])
                time.sleep(1)
                killed = True
                break

    return (True, "QEMU stopped") if killed else (False, "QEMU sudah mati")




def _send_monitor(cmd_str):
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect(QEMU_SOCKET)
        time.sleep(0.2)
        try:
            s.recv(4096)
        except socket.timeout:
            pass
        s.sendall((cmd_str + "\n").encode())
        time.sleep(0.5)
        try:
            data = s.recv(4096)
        except socket.timeout:
            data = b""
        s.close()
        return True, data.decode(errors="replace")
    except Exception as e:
        return False, str(e)


def screenshot(name=None):
    if not is_running():
        return None, {"error": "QEMU nggak jalan"}

    name = name or time.strftime("qemu-%H%M%S")
    ppm = SHOTS / f"{name}.ppm"
    png = SHOTS / f"{name}.png"

    ok, resp = _send_monitor(f"screendump {ppm}")
    if not ok:
        return None, {"error": f"Monitor: {resp}"}

    for _ in range(30):
        if ppm.exists() and ppm.stat().st_size > 1000:
            break
        time.sleep(0.2)

    if not ppm.exists():
        return None, {"error": "PPM nggak muncul"}

    if _has("convert"):
        subprocess.run(["convert", str(ppm), str(png)], capture_output=True, timeout=10)
    elif _has("ffmpeg"):
        subprocess.run(["ffmpeg", "-i", str(ppm), "-y", str(png)], capture_output=True, timeout=10)

    return str(png if png.exists() else ppm), {
        "ppm": str(ppm), "png": str(png) if png.exists() else None,
        "size": ppm.stat().st_size,
    }


def analyze(ppm_path):
    try:
        with open(ppm_path, "rb") as f:
            magic = f.readline().strip()
            if magic != b"P6":
                return {"error": f"Bukan P6: {magic}"}
            line = f.readline()
            while line.startswith(b"#"):
                line = f.readline()
            w, h = map(int, line.split())
            f.readline()
            data = f.read()

        img = np.frombuffer(data, dtype=np.uint8).reshape((h, w, 3))
        cy, cx = h // 2, w // 2
        center = img[max(0,cy-100):cy+100, max(0,cx-150):cx+150] if h > 200 and w > 300 else img
        flat = center.reshape(-1, 3)

        bins = (flat // 32).astype(np.int32)
        idx = bins[:, 0] * 64 + bins[:, 1] * 8 + bins[:, 2]
        vals, counts = np.unique(idx, return_counts=True)
        top = vals[np.argmax(counts)]
        dr, dg, db = (top // 64) * 32 + 16, ((top % 64) // 8) * 32 + 16, (top % 8) * 32 + 16

        var = float(np.var(flat))
        mean_rgb = [float(flat[:, 0].mean()), float(flat[:, 1].mean()), float(flat[:, 2].mean())]
        is_black = sum(mean_rgb) / 3 < 5
        is_white = sum(mean_rgb) / 3 > 250

        result = {
            "resolution": f"{w}x{h}",
            "mean_rgb": [round(x, 1) for x in mean_rgb],
            "dominant_rgb": [dr, dg, db],
            "variance": round(var, 1),
            "unique_colors_approx": int(len(vals)),
            "is_black_screen": is_black,
            "is_white_screen": is_white,
        }

        if is_black:
            result["description"] = "Layar HITAM — framebuffer belum init / kernel crash"
        elif is_white:
            result["description"] = "Layar PUTIH — framebuffer salah setup"
        elif var < 100:
            result["description"] = f"Layar SOLID RGB({dr},{dg},{db}) — nggak ada render"
        elif var < 1000:
            result["description"] = "Layar sedikit variasi — render minimal"
        else:
            result["description"] = f"Layar AKTIF ({len(vals)} warna) — rendering jalan"
        return result
    except Exception as e:
        return {"error": str(e)}


def ocr(png_path):
    if not _has("tesseract") or not png_path:
        return None
    try:
        r = subprocess.run(["tesseract", png_path, "stdout", "-l", "eng"],
                           capture_output=True, text=True, timeout=30)
        t = r.stdout.strip()
        return t if t else None
    except Exception:
        return None


def full_report(disk_image=None, auto_launch=True, boot_wait=10):
    if auto_launch and not is_running() and disk_image:
        ok, msg = launch(disk_image)
        if not ok:
            return {"error": msg}
        time.sleep(boot_wait)

    if not is_running():
        return {"error": "QEMU nggak jalan"}

    path, meta = screenshot()
    if not path:
        return {"error": meta.get("error", "unknown")}

    analysis = analyze(meta.get("ppm", path))
    text = ocr(meta.get("png"))

    return {
        "screenshot_path": path,
        "png_path": meta.get("png"),
        "analysis": analysis,
        "ocr_text": text,
    }


def format_report(report):
    if "error" in report:
        return f"❌ {report['error']}"
    a = report.get("analysis", {})
    lines = [
        f"📸 Screenshot: `{report.get('png_path') or report.get('screenshot_path')}`",
        f"🖥️  Resolusi: {a.get('resolution', '?')}",
        f"🎨 Warna dominan: RGB{tuple(a.get('dominant_rgb', []))}",
        f"📊 Variance: {a.get('variance', '?')} | Warna unik: {a.get('unique_colors_approx', '?')}",
        f"🔍 {a.get('description', '?')}",
    ]
    if report.get("ocr_text"):
        lines.append(f"\n📝 Teks di layar:\n{report['ocr_text'][:500]}")
    return "\n".join(lines)
