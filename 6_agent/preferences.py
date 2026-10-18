"""User Preferences — persist preferensi antar sesi."""
import json
from pathlib import Path

PREF_DIR = Path.home() / ".astra-agent"
PREF_DIR.mkdir(parents=True, exist_ok=True)
PREF_FILE = PREF_DIR / "preferences.json"

DEFAULTS = {
    "language": "id",
    "prefer_build_system": "auto",       # auto | makefile | cmake | cargo | npm
    "naming_convention": "snake_case",    # snake_case | camelCase | kebab
    "test_command": "auto",               # auto | custom string
    "auto_git_checkpoint": True,
    "max_retries_per_task": 6,
    "cost_limit_usd": 1.0,                # warn kalau lewat
    "notifications_enabled": True,
    "notification_channel": "browser",    # browser | telegram | discord | none
    "notify_on": ["task_complete", "run_complete", "budget_warn"],
    "use_evidence_based": True,
    "compile_as_you_go": True,
    "explain_verbosity": "normal",        # short | normal | detailed
}


def _load_raw():
    if not PREF_FILE.exists():
        return {}
    try:
        return json.loads(PREF_FILE.read_text())
    except Exception:
        return {}


def load():
    """Load preferences, merge dengan defaults."""
    user = _load_raw()
    merged = dict(DEFAULTS)
    merged.update(user)
    return merged


def save(prefs):
    """Save preferences (merge, tidak replace)."""
    current = _load_raw()
    current.update(prefs)
    PREF_FILE.write_text(json.dumps(current, indent=2, ensure_ascii=False))
    return load()


def update(key, value):
    """Update single preference."""
    return save({key: value})


def reset():
    """Reset ke default."""
    if PREF_FILE.exists():
        PREF_FILE.unlink()
    return load()


def to_prompt_block():
    """Format preferences untuk dimasukkan ke prompt LLM."""
    p = load()
    lines = ["[USER PREFERENCES — dari sesi sebelumnya, WAJIB IKUTI]"]
    if p.get("naming_convention"):
        lines.append(f"- Naming convention: {p['naming_convention']}")
    if p.get("prefer_build_system") and p["prefer_build_system"] != "auto":
        lines.append(f"- Build system: {p['prefer_build_system']}")
    if p.get("test_command") and p["test_command"] != "auto":
        lines.append(f"- Test command: {p['test_command']}")
    if p.get("use_evidence_based"):
        lines.append("- WAJIB evidence-based (verify header dulu sebelum nulis code)")
    if p.get("compile_as_you_go"):
        lines.append("- Build setiap 1-2 file, bukan di akhir")
    if p.get("language"):
        lines.append(f"- Bahasa laporan: {p['language']}")
    return "\n".join(lines)


print("[PREFERENCES] loaded")
