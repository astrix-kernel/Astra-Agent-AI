"""Auto-checkpoint git-commit every N edit so it can rollback."""

import subprocess, time
from pathlib import Path

from config import ASTRIX_ROOT
_counter = {"count": 0, "last_commit": 0}
CHECKPOINT_EVERY = 5 
MIN_INTERVAL = 120   


def _git(*args):
    try:
        r = subprocess.run(["git"] + list(args),
                           cwd=str(ASTRIX_ROOT),
                           capture_output=True, text=True, timeout=30)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, "", str(e)


def checkpoint(label="auto"):
    """Make a git checkpoint if there are changes."""

    code, out, err = _git("status", "--porcelain")
    if code != 0:
        return None
    if not out.strip():
        return None 

    _git("add", "-A")
    msg = f"[{label}] auto checkpoint {time.strftime('%H:%M:%S')}"
    code, out, err = _git("commit", "-m", msg, "--no-verify")
    if code != 0:
        return None

    code, out, err = _git("rev-parse", "--short", "HEAD")
    commit_hash = out.strip() if code == 0 else "?"
    print(f"  💾 Checkpoint: {commit_hash} ({msg})", flush=True)
    _counter["last_commit"] = time.time()
    return {"hash": commit_hash, "msg": msg}


def maybe_checkpoint():
    """Auto-checkpoint if you have enough edits."""

    _counter["count"] += 1
    now = time.time()
    if (_counter["count"] >= CHECKPOINT_EVERY and
        now - _counter["last_commit"] > MIN_INTERVAL):
        _counter["count"] = 0
        return checkpoint("auto")
    return None


def reset_counter():
    _counter["count"] = 0
