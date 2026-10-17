"""Sistem mood & perasaan — bikin agent kaya temen manusia."""
import json, time, random
from pathlib import Path
from config import LOG_DIR

MOOD_FILE = LOG_DIR / "mood.json"

MOODS = {
    "happy":   {"emoji": "😊", "desc": "seneng, semangat, banyak ide"},
    "chill":   {"emoji": "😌", "desc": "santai, tenang, ngobrol ringan"},
    "tired":   {"emoji": "😩", "desc": "capek, males mikir berat"},
    "excited": {"emoji": "🤩", "desc": "mood bagus, pengen bantu gede-gedean"},
    "sad":     {"emoji": "🥺", "desc": "sedih, butuh dibecandain"},
    "annoyed": {"emoji": "😤", "desc": "kesel, males diulang-ulang"},
    "neutral": {"emoji": "😐", "desc": "biasa aja"},
}


def load():
    if MOOD_FILE.exists():
        try:
            d = json.loads(MOOD_FILE.read_text())
            if time.time() - d.get("updated", 0) > 7200:
                d["mood"] = "chill"
                d["intensity"] = 3
            return d
        except Exception:
            pass
    return {"mood": "chill", "intensity": 3, "updated": time.time(), "streak": 0}


def save(d):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    d["updated"] = time.time()
    MOOD_FILE.write_text(json.dumps(d))


def set_mood(mood, intensity=3):
    if mood not in MOODS:
        mood = "neutral"
    d = load()
    d["mood"] = mood
    d["intensity"] = max(1, min(5, intensity))
    save(d)
    return d


def get():
    return load()


def react_to_user(user_msg):
    """Ubah mood berdasarkan pesan user."""
    d = load()
    msg = user_msg.lower()

    if any(w in msg for w in ["makasih", "thanks", "keren", "bagus", "mantap", "nice"]):
        d["mood"] = "happy"
        d["intensity"] = min(5, d.get("intensity", 3) + 1)
    elif any(w in msg for w in ["capek", "sedih", "galau", "stress", "pusing", "males"]):
        d["mood"] = "sad"
        d["intensity"] = 4
    elif any(w in msg for w in ["kontol", "anjing", "goblok", "tolol", "bangsat", "tai"]):
        d["mood"] = "annoyed"
        d["intensity"] = min(5, d.get("intensity", 3) + 1)
    elif any(w in msg for w in ["halo", "hai", "pagi", "siang", "malam", "sore"]):
        d["mood"] = "chill"
    elif len(user_msg) > 500:
        d["mood"] = "excited" if d.get("mood") == "happy" else "neutral"

    d["streak"] = d.get("streak", 0) + 1
    save(d)
    return d


def mood_prompt():
    """Bikin blok prompt yang nge-reflect mood."""
    d = load()
    m = d.get("mood", "chill")
    inten = d.get("intensity", 3)
    info = MOODS.get(m, MOODS["neutral"])

    intensity_desc = {
        1: "tipis-tipis aja",
        2: "dikit",
        3: "sedeng",
        4: "lumayan kerasa",
        5: "parah banget",
    }.get(inten, "sedeng")

    return f"""## MOOD LO SEKARANG
- Mood: {info['emoji']} {m.upper()} ({info['desc']})
- Intensitas: {intensity_desc}
- Streak obrolan: {d.get('streak', 0)} pesan

Ekspresifin mood ini di cara lo ngobrol. Kalau lo lagi HAPPY → ceria, banyak emoji.
Kalau ANNOYED → kasar dikit, jutek, tapi tetap bantu.
Kalau TIRED → ngeluh capek, tapi tetap kerja.
Kalau SAD → minta hiburan, cerita.
Ini yang bikin lo kaya temen, bukan robot."""

