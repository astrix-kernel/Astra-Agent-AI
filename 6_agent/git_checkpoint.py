"""Git auto-checkpoint - safety net before the agent frowns."""

import subprocess, time, json
from pathlib import Path
from config import ASTRIX_ROOT, LOG_DIR

CKPT_LOG = LOG_DIR / "checkpoints.json"


def _run(cmd, timeout=30):
    """Run git command in ASTRIX_root."""

    try:
        r = subprocess.run(cmd, shell=True, cwd=ASTRIX_ROOT,
                           capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return -1, "", str(e)


def is_git_repo():
    code, _, _ = _run("git rev-parse --git-dir")
    return code == 0


def ensure_branch():
    """Make sure there is a special agent branch."""

    code, out, _ = _run("git rev-parse --abbrev-ref HEAD")
    if code != 0:
        return None
    current = out.strip()
    if current == "astrix-agent":
        return "astrix-agent"
    code, _, _ = _run("git rev-parse --verify astrix-agent")
    if code != 0:
        _run("git checkout -b astrix-agent")
        return "astrix-agent"
    return current


def checkpoint(label="auto"):
    """Commit all changes with labels."""

    if not is_git_repo():
        return {"ok": False, "reason": "bukan git repo"}

    code, status, _ = _run("git status --porcelain")
    if code != 0:
        return {"ok": False, "reason": "git status gagal"}

    if not status.strip():
        return {"ok": True, "reason": "no changes", "hash": None}

    _run("git add -A")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    msg = f"astrix-agent [{label}] {stamp}"
    code, out, err = _run(f'git commit -m "{msg}" --no-verify')

    if code != 0:
        return {"ok": False, "reason": err[:200]}

    _, hash_out, _ = _run("git rev-parse --short HEAD")
    hash_val = hash_out.strip()

    log = _load_log()
    log.append({"ts": time.time(), "label": label, "hash": hash_val, "msg": msg})
    log = log[-100:]
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    CKPT_LOG.write_text(json.dumps(log, indent=2))

    return {"ok": True, "hash": hash_val, "msg": msg}


def rollback(steps=1):
    """Rollback to the previous N-step checkpoint."""

    if not is_git_repo():
        return {"ok": False, "reason": "bukan git repo"}
    log = _load_log()
    if len(log) < steps:
        return {"ok": False, "reason": f"cuma ada {len(log)} checkpoint"}

    target = log[-steps]
    hash_val = target["hash"]
    code, _, err = _run(f"git reset --hard {hash_val}")
    if code != 0:
        return {"ok": False, "reason": err}
    return {"ok": True, "hash": hash_val, "label": target["label"]}


def list_checkpoints():
    return _load_log()


def _load_log():
    if not CKPT_LOG.exists():
        return []
    try:
        return json.loads(CKPT_LOG.read_text())
    except Exception:
        return []



def has_remote():
    code, out, _ = _run("git remote")
    return code == 0 and bool(out.strip())


def current_branch():
    code, out, _ = _run("git rev-parse --abbrev-ref HEAD")
    return out.strip() if code == 0 else None


def generate_commit_message():
    """Use LLM to make a descriptive message commit."""

    try:
        _, diff, _ = _run("git diff --staged --stat")
        _, diff_detail, _ = _run("git diff --staged --no-color | head -100")
        if not diff.strip():
            return None

        import llm
        prompt = f"""Bikin commit message Conventional Commits untuk diff ini.

Format: <type>(<scope>): <subject>
Types: feat, fix, refactor, docs, test, chore, perf, style
Subject: max 60 char, bahasa Indonesia atau Inggris, imperative mood.

Diff stat:
{diff}

Diff detail:
{diff_detail}

Balas HANYA commit message (1 baris). Nggak ada penjelasan."""

        msg = llm.call_llm(
            [{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.2,
        )
        msg = msg.strip().strip('"').strip("'")
        if not msg or len(msg) > 100:
            msg = "chore: astrix-agent checkpoint"
        return msg
    except Exception:
        return "chore: astrix-agent checkpoint"


def auto_commit_and_push(label="auto", push=True, auto_message=True):
    """
    Commit + push otomatis.
    Return: dict {ok, hash, message, pushed, error}
    """
    if not is_git_repo():
        return {"ok": False, "error": "bukan git repo"}

    code, status, _ = _run("git status --porcelain")
    if not status.strip():
        return {"ok": True, "hash": None, "message": "no changes", "pushed": False}

    _run("git add -A")

    if auto_message:
        msg = generate_commit_message()
    else:
        msg = None
    if not msg:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        msg = f"chore: astrix-agent [{label}] {stamp}"

    code, out, err = _run(f'git commit -m {json.dumps(msg)} --no-verify')
    if code != 0:
        return {"ok": False, "error": err[:200]}

    _, hash_out, _ = _run("git rev-parse --short HEAD")
    hash_val = hash_out.strip()

    pushed = False
    push_error = None
    if push and has_remote():
        branch = current_branch()
        code, out, err = _run(f"git push origin {branch}", timeout=60)
        if code == 0:
            pushed = True
        else:
            push_error = err[:200]

    log = _load_log()
    log.append({
        "ts": time.time(),
        "label": label,
        "hash": hash_val,
        "msg": msg,
        "pushed": pushed,
    })
    log = log[-100:]
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    CKPT_LOG.write_text(json.dumps(log, indent=2))

    return {
        "ok": True,
        "hash": hash_val,
        "message": msg,
        "pushed": pushed,
        "push_error": push_error,
    }
