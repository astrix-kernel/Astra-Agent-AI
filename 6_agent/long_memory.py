"""Long-term memory — inget antar sesi/hari."""
import json, time
from pathlib import Path
from config import LOG_DIR

MEM_FILE = LOG_DIR / "long_memory.json"


def _load():
    if not MEM_FILE.exists():
        return {
            "preferences": [],     # preferensi user
            "decisions": [],       # keputusan desain
            "patterns": [],        # pattern kode project
            "facts": [],           # fakta tentang project
            "learnings": [],       # pelajaran dari pengalaman
        }
    try:
        return json.loads(MEM_FILE.read_text())
    except Exception:
        return {"preferences": [], "decisions": [], "patterns": [], "facts": [], "learnings": []}


def _save(m):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    MEM_FILE.write_text(json.dumps(m, indent=2, ensure_ascii=False))


def add(category, content, importance="normal"):
    m = _load()
    if category not in m:
        m[category] = []
    m[category].append({
        "content": content,
        "importance": importance,
        "ts": time.time(),
    })
    m[category] = m[category][-100:]
    _save(m)
    return True


def remember_preference(text):
    return add("preferences", text, "high")


def remember_decision(text):
    return add("decisions", text, "high")


def remember_pattern(text):
    return add("patterns", text)


def remember_fact(text):
    return add("facts", text)


def remember_learning(text):
    return add("learnings", text, "high")


def search(query, limit=10):
    """Cari di semua kategori."""
    m = _load()
    q = query.lower()
    results = []
    for cat, items in m.items():
        for item in items:
            if q in item["content"].lower():
                results.append({**item, "category": cat})
    results.sort(key=lambda x: x["ts"], reverse=True)
    return results[:limit]


def build_memory_block(max_items=15):
    """Format memory sebagai string buat inject ke prompt."""
    m = _load()
    parts = []

    imp = {"high": "⭐", "normal": ""}

    for cat, label in [
        ("preferences", "🎯 PREFERENSI USER"),
        ("decisions", "📌 KEPUTUSAN DESAIN"),
        ("patterns", "🔧 PATTERN PROJECT"),
        ("facts", "📖 FAKTA PROJECT"),
        ("learnings", "💡 PELAJARAN"),
    ]:
        items = m.get(cat, [])[-5:]  # max 5 terakhir
        if items:
            parts.append(f"## {label}")
            for item in items:
                star = imp.get(item.get("importance", "normal"), "")
                parts.append(f"  {star} {item['content']}")
            parts.append("")

    return "\n".join(parts)


def extract_and_save(user_msg, agent_response):
    """
    Auto-extract memory dari chat.
    Simple heuristic — cari kalimat yang ngasih info penting.
    """
    import re
    u = user_msg.lower()

    # Detect preferensi
    if any(k in u for k in ["gw suka", "gue suka", "aku suka", "saya suka",
                             "gw prefer", "gue prefer", "pake", "pakai",
                             "jangan pake", "jangan pakai"]):
        if len(user_msg) < 300:
            remember_preference(user_msg[:250])

    # Detect keputusan
    if any(k in u for k in ["keputusan", "gw pilih", "gue pilih", "final",
                             "tentukan", "kita pakai"]):
        if len(user_msg) < 300:
            remember_decision(user_msg[:250])


def stats():
    m = _load()
    return {k: len(v) for k, v in m.items()}
