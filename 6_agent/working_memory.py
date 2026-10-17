"""Working memory — inget konteks sesi aktif."""
import json, time
from pathlib import Path
from config import LOG_DIR

FILE = LOG_DIR / "working_memory.json"
MAX_ENTRIES = 20


def _load():
    if not FILE.exists():
        return []
    try:
        return json.loads(FILE.read_text())
    except Exception:
        return []


def _save(data):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def add_topic(topic, detail, importance="normal"):
    """Catat topik yang lagi dibahas."""
    data = _load()
    data.append({
        "topic": topic[:200],
        "detail": detail[:500],
        "importance": importance,
        "ts": time.time(),
    })
    data = data[-MAX_ENTRIES:]
    _save(data)


def extract_from_turn(user_msg, agent_response):
    """Auto-extract topik dari turn."""
    u = user_msg.lower()

    # Detect topik project
    topics = []
    if "vtx" in u or "vtx_engine" in u:
        topics.append(("vtx_engine", user_msg[:200], "high"))
    if "driver" in u:
        topics.append(("driver", user_msg[:200], "normal"))
    if "kernel" in u:
        topics.append(("kernel", user_msg[:200], "normal"))
    if "audio" in u:
        topics.append(("audio", user_msg[:200], "normal"))
    if "render" in u or "graphics" in u:
        topics.append(("render", user_msg[:200], "high"))
    if "error" in u or "bug" in u or "panic" in u:
        topics.append(("debug", user_msg[:200], "high"))

    # Cuma tambah kalau ada topik
    if not topics and len(user_msg) > 20:
        # Fallback: simpan sebagai "chat" topik
        topics.append(("chat", user_msg[:200], "low"))

    for t in topics:
        add_topic(*t)


def build_working_block(max_items=8):
    """Format working memory buat prompt."""
    data = _load()
    if not data:
        return ""

    # Ambil 8 terakhir, dedupe by topic
    seen = set()
    recent = []
    for item in reversed(data):
        if item["topic"] not in seen:
            seen.add(item["topic"])
            recent.append(item)
        if len(recent) >= max_items:
            break

    if not recent:
        return ""

    lines = ["## 💭 KONTEKS SESI SEKARANG"]
    for item in reversed(recent):
        lines.append(f"  • **{item['topic']}**: {item['detail'][:120]}")
    lines.append("")
    return "\n".join(lines)


def clear():
    _save([])
