"""Error learning — catat & pelajari error yang terjadi."""
import json, time, hashlib
from pathlib import Path
from config import LOG_DIR

FILE = LOG_DIR / "error_patterns.json"


def _load():
    if not FILE.exists():
        return {}
    try:
        return json.loads(FILE.read_text())
    except Exception:
        return {}


def _save(data):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _key(tool, args, error):
    sig = f"{tool}:{json.dumps(args, sort_keys=True, default=str)[:200]}:{error[:100]}"
    return hashlib.md5(sig.encode()).hexdigest()[:16]


def record(tool, args, error, context="", solution=""):
    """Catat error + solusinya (kalau ada)."""
    data = _load()
    key = _key(tool, args, error)

    if key in data:
        data[key]["count"] += 1
        data[key]["last_seen"] = time.time()
        if solution:
            data[key]["solution"] = solution
    else:
        data[key] = {
            "tool": tool,
            "error": error[:300],
            "args_preview": str(args)[:200],
            "context": context[:200],
            "solution": solution[:300],
            "count": 1,
            "first_seen": time.time(),
            "last_seen": time.time(),
        }
    _save(data)


def find_similar(tool, args, error):
    """Cari error yang mirip dengan yang sekarang."""
    data = _load()
    key = _key(tool, args, error)
    return data.get(key)


def get_avoidance_hints(tool=None, limit=10):
    """Ambil error pattern yang sering muncul."""
    data = _load()
    items = list(data.values())

    if tool:
        items = [x for x in items if x["tool"] == tool]

    items.sort(key=lambda x: (x["count"], x["last_seen"]), reverse=True)
    return items[:limit]


def build_hints_block(tool=None, limit=8):
    """Format error pattern jadi hint untuk prompt."""
    items = get_avoidance_hints(tool=tool, limit=limit)
    if not items:
        return ""

    lines = ["## ⚠️ HINDARI ERROR BERULANG"]
    for item in items:
        lines.append(f"- **{item['tool']}**: {item['error'][:150]}")
        if item.get("solution"):
            lines.append(f"  → Solusi: {item['solution'][:150]}")
        lines.append(f"  (Kejadian {item['count']}x)")
    lines.append("")
    return "\n".join(lines)


def stats():
    data = _load()
    return {
        "total_patterns": len(data),
        "total_occurrences": sum(x["count"] for x in data.values()),
    }
