"""Chat history persistence — multi-session, auto-save."""
import json, time, uuid
from pathlib import Path
from config import LOG_DIR

SESSIONS_DIR = LOG_DIR / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
INDEX_FILE = SESSIONS_DIR / "index.json"


def _load_index():
    if not INDEX_FILE.exists():
        return {"sessions": [], "active": None}
    try:
        return json.loads(INDEX_FILE.read_text())
    except Exception:
        return {"sessions": [], "active": None}


def _save_index(idx):
    INDEX_FILE.write_text(json.dumps(idx, indent=2))


def new_session(title="Percakapan Baru"):
    sid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    data = {
        "id": sid,
        "title": title,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "messages": [],
    }
    (SESSIONS_DIR / f"{sid}.json").write_text(json.dumps(data, indent=2))
    idx = _load_index()
    idx["sessions"].insert(0, {"id": sid, "title": title, "updated_at": data["updated_at"], "count": 0})
    idx["active"] = sid
    _save_index(idx)
    return data


def list_sessions():
    idx = _load_index()
    return idx.get("sessions", []), idx.get("active")


def load_session(sid):
    f = SESSIONS_DIR / f"{sid}.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text())
    except Exception:
        return None


def get_active_session():
    idx = _load_index()
    sid = idx.get("active")
    if not sid:
        return new_session()
    data = load_session(sid)
    if not data:
        return new_session()
    return data


def set_active(sid):
    idx = _load_index()
    idx["active"] = sid
    _save_index(idx)


def append_message(sid, role, content, meta=None):
    data = load_session(sid)
    if not data:
        return
    msg = {"role": role, "content": content, "ts": time.time()}
    if meta:
        msg["meta"] = meta
    data["messages"].append(msg)
    data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (SESSIONS_DIR / f"{sid}.json").write_text(json.dumps(data, indent=2))

    idx = _load_index()
    for s in idx["sessions"]:
        if s["id"] == sid:
            s["updated_at"] = data["updated_at"]
            s["count"] = len(data["messages"])
            if s["title"] == "Percakapan Baru" and role == "user":
                s["title"] = content[:50]
            break
    _save_index(idx)


def update_title(sid, title):
    data = load_session(sid)
    if not data:
        return
    data["title"] = title
    (SESSIONS_DIR / f"{sid}.json").write_text(json.dumps(data, indent=2))
    idx = _load_index()
    for s in idx["sessions"]:
        if s["id"] == sid:
            s["title"] = title
            break
    _save_index(idx)


def delete_session(sid):
    f = SESSIONS_DIR / f"{sid}.json"
    if f.exists():
        f.unlink()
    idx = _load_index()
    idx["sessions"] = [s for s in idx["sessions"] if s["id"] != sid]
    if idx["active"] == sid:
        idx["active"] = idx["sessions"][0]["id"] if idx["sessions"] else None
    _save_index(idx)
    return idx["active"]


def clear_active():
    data = get_active_session()
    data["messages"] = []
    (SESSIONS_DIR / f"{data['id']}.json").write_text(json.dumps(data, indent=2))
    return data
