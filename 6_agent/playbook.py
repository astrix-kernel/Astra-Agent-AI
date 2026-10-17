"""Playbook — resep task yang sering dikerjain."""
import json, time
from pathlib import Path
from config import LOG_DIR

FILE = LOG_DIR / "playbooks.json"


DEFAULT_PLAYBOOKS = {
    "bikin_driver": {
        "trigger": ["driver baru", "bikin driver", "new driver", "buat driver"],
        "steps": [
            "Baca driver existing sebagai referensi (kernel/driver/*.c)",
            "Bikin header di include/driver/<name>.h dengan include guard",
            "Definisikan struct + function prototypes",
            "Bikin source kernel/driver/<name>.c dengan implementasi",
            "Daftarkan di Makefile (obj-y + path)",
            "Tambah config di Kconfig",
            "Build: make build -j4",
            "Fix error, build lagi",
            "Test: launch QEMU, cek log",
        ],
    },
    "debug_panic": {
        "trigger": ["kernel panic", "panic", "crash", "triple fault"],
        "steps": [
            "Baca log panic — cari RIP, error code, stack trace",
            "Kalau ada, ambil QEMU screenshot dengan serial log",
            "Baca fungsi di sekitar RIP",
            "Cek hipotesis: null deref / invalid addr / hw not ready",
            "Test hipotesis pakai gdb / print debug / read code",
            "Konfirmasi penyebab, fix, build, test ulang",
        ],
    },
    "refactor_file": {
        "trigger": ["refactor", "pecah file", "split file", "modular"],
        "steps": [
            "Baca seluruh file existing",
            "Identifikasi bagian yang bisa dipisah (struct, fungsi, dll)",
            "Bikin file baru per topik",
            "Pindah kode, pastikan include bener",
            "Update #include di file lain yang butuh",
            "Build, fix error",
            "Test end-to-end",
        ],
    },
    "bikin_ui": {
        "trigger": ["ui system", "bikin ui", "window manager", "gui"],
        "steps": [
            "Desain API dulu: struct widget, function signatures",
            "Bikin include/ui/ui.h dengan API dasar",
            "Implementasi minimal: init, draw, event handler",
            "Integrasi dengan framebuffer existing",
            "Test: bikin window kosong, render di QEMU",
            "Iterasi: tambah widget (button, text)",
        ],
    },
    "tambah_fitur": {
        "trigger": ["tambah fitur", "add feature", "implementasi"],
        "steps": [
            "Baca file/modul terkait",
            "Bikin header/interface dulu kalau perlu",
            "Implementasi satu per satu fungsi",
            "Build setiap habis tambah fungsi",
            "Test dengan skenario real",
        ],
    },
}


def _load():
    if not FILE.exists():
        data = dict(DEFAULT_PLAYBOOKS)
        _save(data)
        return data
    try:
        return json.loads(FILE.read_text())
    except Exception:
        return dict(DEFAULT_PLAYBOOKS)


def _save(data):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def match_playbook(user_msg):
    """Cari playbook yang cocok dengan task."""
    m = user_msg.lower()
    data = _load()
    best = None
    best_score = 0
    for name, pb in data.items():
        score = sum(1 for t in pb.get("trigger", []) if t in m)
        if score > best_score:
            best_score = score
            best = name
    return best if best_score > 0 else None


def get_playbook(name):
    return _load().get(name)


def format_playbook(name):
    """Format playbook jadi teks untuk prompt."""
    pb = get_playbook(name)
    if not pb:
        return ""
    lines = [f"## 📖 PLAYBOOK: {name.replace('_', ' ').title()}"]
    for i, step in enumerate(pb.get("steps", []), 1):
        lines.append(f"  {i}. {step}")
    return "\n".join(lines)


def build_playbook_block(user_msg):
    """Cari playbook cocok + format."""
    name = match_playbook(user_msg)
    if not name:
        return ""
    return format_playbook(name)


def add_playbook(name, trigger, steps):
    """Tambah playbook baru."""
    data = _load()
    data[name] = {"trigger": trigger, "steps": steps}
    _save(data)
    return True


def auto_learn_from_success(goal, task_log):
    """
    Auto-learn playbook dari task yang sukses.
    Dipanggil di akhir goal yang selesai.
    """
    name = match_playbook(goal)
    if not name:
        return False
    return True 
