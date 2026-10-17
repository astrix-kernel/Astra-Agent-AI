"""Long-term memory via SQLite — stores facts from conversations."""
import sqlite3, re, time
from pathlib import Path

DB_PATH = Path.home() / "astrix-ai" / "logs" / "memory.db"


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.execute("""CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT, key TEXT, value TEXT,
        created_at REAL, updated_at REAL
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_key ON memories(key)")
    c.commit()
    return c


def save_fact(category, key, value):
    c = _conn()
    now = time.time()
    row = c.execute("SELECT id FROM memories WHERE category=? AND key=?", (category, key)).fetchone()
    if row:
        c.execute("UPDATE memories SET value=?, updated_at=? WHERE id=?", (value, now, row[0]))
    else:
        c.execute("INSERT INTO memories (category,key,value,created_at,updated_at) VALUES (?,?,?,?,?)",
                  (category, key, value, now, now))
    c.commit()
    c.close()
    return f"✅ [{category}] {key}"


def search(query, limit=5):
    c = _conn()
    words = [w for w in re.findall(r'\w+', query.lower()) if len(w) > 2][:5]
    if not words:
        rows = c.execute("SELECT category,key,value FROM memories ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    else:
        conds = " OR ".join(["LOWER(key) LIKE ? OR LOWER(value) LIKE ?"] * len(words))
        params = []
        for w in words:
            params += [f"%{w}%", f"%{w}%"]
        rows = c.execute(f"SELECT category,key,value FROM memories WHERE {conds} ORDER BY updated_at DESC LIMIT ?",
                         (*params, limit)).fetchall()
    c.close()
    return rows


def get_context(query=""):
    rows = search(query, 5)
    if not rows:
        return ""
    lines = ["[MEMORY — facts from past chats]"]
    for cat, k, v in rows:
        lines.append(f"- [{cat}] {k}: {v}")
    return "\n".join(lines)


def extract_from_message(text):
    """Extract facts from user message using heuristics."""
    facts = []
    # Name
    m = re.search(r"(?:nama (?:gue|aku|saya)|my name is|i'm|i am)\s+([A-Z][a-zA-Z]{2,15})", text, re.I)
    if m: facts.append(("identity", "name", m.group(1)))
    # Project
    m = re.search(r"(?:project|proyek)\s+(?:gue|aku|saya|my)?\s*(?:namanya|named|called)?\s*([A-Z][a-zA-Z0-9._-]{2,30})", text, re.I)
    if m: facts.append(("project", "current", m.group(1)))
    # Likes/dislikes
    m = re.search(r"(?:gue|aku|saya|i)\s+(?:suka|like)\s+([a-zA-Z0-9 ]{3,40})", text, re.I)
    if m: facts.append(("preference", "like", m.group(1).strip()[:40]))
    # Save all
    saved = []
    for cat, k, v in facts:
        save_fact(cat, k, v)
        saved.append(f"[{cat}] {k}={v}")
    return saved


def list_all(limit=100):
    c = _conn()
    rows = c.execute("SELECT category,key,value,datetime(updated_at,'unixepoch','localtime') FROM memories ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    c.close()
    return rows


def delete_fact(category, key):
    c = _conn()
    c.execute("DELETE FROM memories WHERE category=? AND key=?", (category, key))
    c.commit()
    c.close()
    return True


def clear_all():
    c = _conn()
    c.execute("DELETE FROM memories")
    c.commit()
    c.close()
    return True
