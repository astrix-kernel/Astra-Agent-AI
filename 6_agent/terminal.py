"""Terminal command runner untuk Web UI."""
import subprocess, shlex, time
from pathlib import Path
from config import ASTRIX_ROOT, ALLOWED_COMMANDS


def is_allowed(cmd_str):
    """Cek command allowed."""
    try:
        parts = shlex.split(cmd_str)
        if not parts:
            return False, "kosong"
        base = Path(parts[0]).name
        if base not in ALLOWED_COMMANDS:
            return False, f"'{base}' nggak di whitelist"
        return True, "ok"
    except Exception as e:
        return False, str(e)


def run(cmd_str, timeout=60):
    """
    Jalankan command, return dict:
    {ok, exit_code, stdout, stderr, duration}
    """
    if not cmd_str.strip():
        return {"ok": False, "error": "kosong"}

    allowed, msg = is_allowed(cmd_str)
    if not allowed:
        return {"ok": False, "error": f"Command diblokir: {msg}"}

    t0 = time.time()
    try:
        r = subprocess.run(
            cmd_str, shell=True, cwd=ASTRIX_ROOT,
            capture_output=True, text=True, timeout=timeout,
        )
        return {
            "ok": r.returncode == 0,
            "exit_code": r.returncode,
            "stdout": r.stdout[-8000:],
            "stderr": r.stderr[-4000:],
            "duration": round(time.time() - t0, 2),
            "cmd": cmd_str,
            "cwd": str(ASTRIX_ROOT),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Timeout {timeout}s", "duration": timeout}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def format_result(r):
    """Format jadi output rapi."""
    if "error" in r:
        return f"❌ {r['error']}"
    out = [f"$ {r['cmd']}"]
    out.append(f"  (exit {r['exit_code']}, {r['duration']}s)")
    if r["stdout"].strip():
        out.append("\n" + r["stdout"].rstrip())
    if r["stderr"].strip():
        out.append("\n[stderr]\n" + r["stderr"].rstrip())
    return "\n".join(out)
