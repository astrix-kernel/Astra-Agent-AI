"""Configuration — load from .env file (do not hardcode API key!)."""

import os
from pathlib import Path

_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith('#'):
            continue
        if '=' in _line:
            _key, _val = _line.split('=', 1)
            os.environ.setdefault(_key.strip(), _val.strip())


# === WORKSPACE (mutable, bisa diubah per-request) ===
SELF_ROOT = Path(__file__).parent.parent.resolve()
ASTRIX_ROOT = SELF_ROOT
WORKSPACE = Path(os.getenv("ASTRIX_WORKSPACE", str(SELF_ROOT))).resolve()

def set_workspace(new_path: str):
    """Set workspace ke folder tertentu. Return True kalau sukses."""
    global WORKSPACE
    if not new_path:
        return False
    try:
        p = Path(new_path).resolve()
        if p.is_dir():
            WORKSPACE = p
            print(f"[WORKSPACE] Set to: {WORKSPACE}", flush=True)
            return True
    except Exception as e:
        print(f"[WORKSPACE] Failed: {e}", flush=True)
    return False

LOG_DIR = Path(os.getenv("ASTRIX_LOG_DIR", str(Path(__file__).parent.parent / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)

LLM_URL = os.getenv("LLM_URL", "http://localhost:20128/v1/chat/completions")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", None)
# Model fallback kalau user gak set LLM_MODEL. Empty string = provider default.
DEFAULT_MODEL = os.getenv("ASTRIX_DEFAULT_MODEL", "") 



PORT = int(os.getenv("ASTRIX_PORT", "8765"))
HOST = os.getenv("ASTRIX_HOST", "0.0.0.0")



SELF_ROOT = Path(__file__).parent.parent
SELF_EDIT_WHITELIST = [
    "6_agent/",
    "web/static/",
    "web/server.py",
]

if not LLM_API_KEY:
    print("⚠️  WARNING: LLM_API_KEY kosong. Copy .env.example ke .env dan isi API key.")

from pathlib import Path
TRASH_DIR = ASTRIX_ROOT / '.trash'

import os
from pathlib import Path

# === LLM request limits ===
MAX_TOKENS_PER_RESPONSE = 4096

LOG_FILE = Path(os.environ.get("ASTRIX_WORKSPACE", ".")) / "agent.log"
ALLOWED_COMMANDS = {"ls", "cat", "grep", "make", "python3", "python", "git", "mkdir", "rm", "mv", "cp", "echo", "pwd", "find", "sed", "awk", "touch", "npm", "node", "gcc", "g++", "ping", "curl", "wget", "tree", "head", "tail", "wc", "ps", "top", "df", "free", "uname", "chmod", "chown", "tar", "zip", "unzip", "xdg-open"}
SELF_ROOT = Path(__file__).parent.parent
SELF_EDIT_WHITELIST = ["6_agent/", "web/"]
SELF_EDIT_BLOCK = [".env", "config.py"]
MAX_FILE_READ_BYTES = 100000
MAX_TOOL_RESULT_CHARS = 5000
WRITABLE_EXT = {".c", ".h", ".py", ".txt", ".md", ".json", ".yaml", ".yml", ".sh", ".html", ".css", ".js", ".ts", ".toml", ".ini", ".cfg", ".make", ".mk", ".S", ".s", ".asm", ".cpp", ".hpp", ".cc", ".hh", ".ld", ".lds", ".rs", ".go", ".java", ".rb", ".php", ".lua", ".vue", ".tsx", ".jsx", ".m", ".mm", ".xml", ".csv"}
WRITABLE_NAMES = {"Makefile", "Dockerfile", "Kconfig"}
VERIFY_COMPILER = {
    ".py": ["python3", "-m", "py_compile"],
    ".c": ["gcc", "-fsyntax-only"],
    ".h": ["gcc", "-fsyntax-only"],
    ".cpp": ["g++", "-fsyntax-only"]
}

# Timeout request buat planner (detik)
REQUEST_TIMEOUT = 300

REQUEST_TIMEOUT = 300


# === Agent Task Limits ===
MAX_TASKS_DEFAULT = 40  # safety cap, AI decides actual count
MAX_RETRIES_PER_TASK = 6  # beneran retry 6x dengan reflection
MAX_TOTAL_ATTEMPTS = None  # auto: max_tasks * 3
