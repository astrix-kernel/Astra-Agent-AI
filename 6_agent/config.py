"""Configuration — load dari .env file (jangan hardcode API key!)."""
import os
from pathlib import Path

# Load .env file
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith('#'):
            continue
        if '=' in _line:
            _key, _val = _line.split('=', 1)
            os.environ.setdefault(_key.strip(), _val.strip())

# === LOG DIR ===
LOG_DIR = Path(os.getenv("ASTRIX_LOG_DIR", str(Path(__file__).parent.parent / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)

# === LLM CONFIG ===
LLM_URL = os.getenv("LLM_URL", "http://localhost:20128/v1/chat/completions")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = None  # dynamic via runtime.get_model_id()

# === WORKSPACE ===
WORKSPACE = os.getenv("ASTRIX_WORKSPACE", str(Path.home()))

# === SERVER ===
PORT = int(os.getenv("ASTRIX_PORT", "8765"))
HOST = os.getenv("ASTRIX_HOST", "0.0.0.0")

# === ASTRIX ROOT (workspace root) ===
ASTRIX_ROOT = Path(os.getenv("ASTRIX_ROOT", str(Path.home())))

# === SELF EDIT (existing) ===
SELF_ROOT = Path(__file__).parent.parent
SELF_EDIT_WHITELIST = [
    "6_agent/",
    "web/static/",
    "web/server.py",
]

if not LLM_API_KEY:
    print("⚠️  WARNING: LLM_API_KEY kosong. Copy .env.example ke .env dan isi API key.")
