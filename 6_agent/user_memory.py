"""Remember the facts about the user — so it's like a friend who really knows."""

import json, time
from pathlib import Path
from config import LOG_DIR

MEM_FILE = LOG_DIR / "user_memory.json"


def load():
    if MEM_FILE.exists():
        try:
            return json.loads(MEM_FILE.read_text())
        except Exception:
            pass
    return {"facts": [], "last_seen": 0, "mood_history": [], "streak_days": 0}


def save(d):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    d["last_seen"] = time.time()
    MEM_FILE.write_text(json.dumps(d, indent=2))


def add_fact(fact):
    """Simplify new facts about users."""

    d = load()
    fact = fact.strip()
    if not fact or len(fact) < 5 or len(fact) > 200:
        return
    if fact in d["facts"]:
        return
    d["facts"].append(fact)
    # Keep max 50 facts
    d["facts"] = d["facts"][-50:]
    save(d)


def remember_facts(user_msg, agent_response):
    """Extract facts from conversations using pattern matching."""

    msg = user_msg.lower()

    # Factual pattern
    patterns = [
        ("lagi ", lambda m: m.split("lagi", 1)[1].strip()[:100] if "lagi" in m else None),
        ("gw suka", lambda m: m.split("gw suka", 1)[1].strip()[:100] if "gw suka" in m else None),
        ("gw benci", lambda m: m.split("gw benci", 1)[1].strip()[:100] if "gw benci" in m else None),
        ("gw kerja", lambda m: m.split("gw kerja", 1)[1].strip()[:100] if "gw kerja" in m else None),
        ("gw tinggal", lambda m: m.split("gw tinggal", 1)[1].strip()[:100] if "gw tinggal" in m else None),
    ]
    for _, fn in patterns:
        try:
            fact = fn(msg)
            if fact and len(fact) > 5:
                add_fact(f"User {msg[:80]}")
                break
        except Exception:
            pass

    # Simpen streak daily
    d = load()
    last = d.get("last_seen", 0)
    now = time.time()
    if last > 0 and (now - last) > 86400 and (now - last) < 172800:
        d["streak_days"] = d.get("streak_days", 0) + 1
    save(d)


def memory_prompt():
    """Create a prompt block containing user facts."""

    d = load()
    facts = d.get("facts", [])
    streak = d.get("streak_days", 0)

    if not facts and streak == 0:
        return ""

    parts = ["## YANG LO INGET TENTANG USER"]
    if streak > 0:
        parts.append(f"- Kalian udah ngobrol {streak + 1} hari berturut-turut")
    for f in facts[-5:]:  # Max last 5 facts
        parts.append(f"- {f}")
    parts.append("Sebutin fakta ini sesekali biar kayak temen yang beneran inget.")
    return "\n".join(parts)


def greeting_extra():
    """Extra greeting if the user returns after a long time."""

    d = load()
    last = d.get("last_seen", 0)
    now = time.time()
    gap = now - last

    if last == 0:
        return ""
    if gap > 7 * 86400:
        return f"eh lo balik! 🥺 udah {int(gap/86400)} hari gak ketemu. gimana kabar?"
    if gap > 86400:
        return f"eh lo balik 😊 kemaren ngilang ya. gimana?"
    return ""
