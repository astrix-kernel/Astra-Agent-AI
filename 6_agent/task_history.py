"""Simpen history task yang udah dikerjain."""
import json, time
from pathlib import Path
from config import LOG_DIR

HIST_FILE = LOG_DIR / "task_history.json"


def load():
    if HIST_FILE.exists():
        try:
            return json.loads(HIST_FILE.read_text())
        except Exception:
            pass
    return {"tasks": [], "current_session": None}


def save(d):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    HIST_FILE.write_text(json.dumps(d, indent=2))


def start_task(desc):
    """Tandai mulai task baru."""
    d = load()
    d["current_session"] = {
        "desc": desc,
        "started": time.time(),
        "files_touched": [],
        "status": "in_progress",
    }
    save(d)


def log_file_change(path, action="edit"):
    """Log file yang diubah."""
    d = load()
    if d.get("current_session"):
        d["current_session"]["files_touched"].append({
            "path": str(path),
            "action": action,
            "time": time.time(),
        })
        save(d)


def finish_task(summary=""):
    """Tandai task selesai."""
    d = load()
    if d.get("current_session"):
        d["current_session"]["status"] = "done"
        d["current_session"]["finished"] = time.time()
        d["current_session"]["summary"] = summary
        d["tasks"].append(d["current_session"])
        d["tasks"] = d["tasks"][-30:]  # keep 30 terakhir
        d["current_session"] = None
        save(d)


def recent_summary(n=5):
    """Ringkas task terakhir buat prompt."""
    d = load()
    tasks = d.get("tasks", [])[-n:]
    if not tasks:
        return ""
    parts = ["## TASK YANG UDAH KELAR (konteks)"]
    for t in tasks:
        files = len(t.get("files_touched", []))
        parts.append(f"- {t.get('desc', '?')[:60]} ({files} file)")
    if d.get("current_session"):
        cs = d["current_session"]
        parts.append(f"\\n## SEDANG DIKERJAIN\\n- {cs.get('desc', '?')[:80]}")
    return "\\n".join(parts)
