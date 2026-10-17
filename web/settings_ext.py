"""Settings backend — usage tracker, profiles, export, permissions."""
import json, time
from pathlib import Path
from datetime import datetime, timedelta

LOG_DIR = Path.home() / "astrix-ai" / "logs"
USAGE_FILE = LOG_DIR / "usage.json"
PROFILES_FILE = LOG_DIR / "profiles.json"
MEMORY_FILE = LOG_DIR / "memory.json"


def _load(path, default):
    try:
        return json.loads(path.read_text()) if path.exists() else default
    except Exception:
        return default


def _save(path, data):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def record_usage(prompt=0, completion=0, model="", cost=0.0):
    """Catat pemakaian token."""
    data = _load(USAGE_FILE, {"days": {}, "totals": {}})
    d = _today()
    if d not in data["days"]:
        data["days"][d] = {"prompt": 0, "completion": 0, "cost": 0.0, "requests": 0}
    data["days"][d]["prompt"] += prompt
    data["days"][d]["completion"] += completion
    data["days"][d]["cost"] += cost
    data["days"][d]["requests"] += 1
    t = data["totals"]
    t["prompt"] = t.get("prompt", 0) + prompt
    t["completion"] = t.get("completion", 0) + completion
    t["cost"] = t.get("cost", 0.0) + cost
    t["requests"] = t.get("requests", 0) + 1
    _save(USAGE_FILE, data)


def register_endpoints(app, DBG):
    """Daftar semua endpoint setting. Dipanggil dari server.py."""
    
    @app.get("/api/usage")
    async def get_usage():
        data = _load(USAGE_FILE, {"days": {}, "totals": {}})
        week = []
        for i in range(6, -1, -1):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            row = data["days"].get(d, {"prompt": 0, "completion": 0, "cost": 0.0, "requests": 0})
            week.append({"date": d, **row})
        return {"totals": data.get("totals", {}), "week": week, "today": data["days"].get(_today(), {})}
    
    @app.post("/api/usage/reset")
    async def reset_usage():
        _save(USAGE_FILE, {"days": {}, "totals": {}})
        return {"ok": True}
    
    @app.get("/api/profiles")
    async def list_profiles():
        return _load(PROFILES_FILE, {})
    
    @app.post("/api/profiles")
    async def save_profile(req: dict):
        name = req.get("name", "").strip()
        if not name:
            return {"error": "nama kosong"}
        config = req.get("config", {})
        data = _load(PROFILES_FILE, {})
        data[name] = {"config": config, "created": time.time()}
        _save(PROFILES_FILE, data)
        return {"ok": True, "name": name}
    
    @app.delete("/api/profiles/{name}")
    async def delete_profile(name: str):
        data = _load(PROFILES_FILE, {})
        data.pop(name, None)
        _save(PROFILES_FILE, data)
        return {"ok": True}
    
    @app.get("/api/config/export")
    async def export_config():
        return {"ok": True, "note": "Use frontend to export localStorage"}
    
    @app.get("/api/memory")
    async def get_memory():
        return _load(MEMORY_FILE, {"facts": []})
    
    @app.delete("/api/memory/{key}")
    async def delete_memory(key: str):
        data = _load(MEMORY_FILE, {"facts": []})
        data["facts"] = [f for f in data.get("facts", []) if f.get("key") != key]
        _save(MEMORY_FILE, data)
        return {"ok": True}
    
    DBG("[SETTINGS-EXT] endpoints registered")


