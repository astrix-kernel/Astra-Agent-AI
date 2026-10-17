"""State management untuk Astrix Agent — persistent across sessions."""
import json, time
from pathlib import Path
from config import LOG_DIR

STATE_FILE = LOG_DIR / "state.json"
PROGRESS_FILE = LOG_DIR / "progress.md"


def load_state():
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return None


def save_state(state):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    STATE_FILE.write_text(json.dumps(state, indent=2))


def clear_state():
    if STATE_FILE.exists():
        STATE_FILE.unlink()


def append_progress(text):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, "a") as f:
        f.write(f"\n## [{time.strftime('%Y-%m-%d %H:%M:%S')}]\n{text}\n")


def create_state(goal, tasks):
    return {
        "goal": goal,
        "tasks": tasks,          # [{"id": 1, "desc": "...", "status": "pending", "result": ""}]
        "current_idx": 0,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_steps": 0,
        "sessions": 1,
    }


def get_current_task(state):
    idx = state["current_idx"]
    if idx >= len(state["tasks"]):
        return None
    return state["tasks"][idx]


def mark_done(state, result=""):
    idx = state["current_idx"]
    if idx < len(state["tasks"]):
        state["tasks"][idx]["status"] = "done"
        state["tasks"][idx]["result"] = result[:500]
        state["current_idx"] = idx + 1


def mark_failed(state, error=""):
    idx = state["current_idx"]
    if idx < len(state["tasks"]):
        state["tasks"][idx]["status"] = "failed"
        state["tasks"][idx]["result"] = error[:500]


def add_task(state, desc, priority="normal"):
    """Tambah task baru (dari agent sendiri kalau nemu sesuatu)."""
    new_id = max([t["id"] for t in state["tasks"]], default=0) + 1
    new_task = {"id": new_id, "desc": desc, "status": "pending",
                "result": "", "priority": priority, "added_during_run": True}
    # Insert sebelum task terakhir yang belum dijalankan
    state["tasks"].append(new_task)
    return new_task


def is_complete(state):
    return all(t["status"] == "done" for t in state["tasks"])


def summarize(state):
    done = sum(1 for t in state["tasks"] if t["status"] == "done")
    failed = sum(1 for t in state["tasks"] if t["status"] == "failed")
    pending = sum(1 for t in state["tasks"] if t["status"] == "pending")
    return {
        "total": len(state["tasks"]),
        "done": done,
        "failed": failed,
        "pending": pending,
        "current": state["current_idx"] + 1,
    }
