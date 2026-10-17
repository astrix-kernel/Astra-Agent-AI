"""Configuration — load from .env file (do not hardcode API key!)."""

import os
from pathlib import Path

# Load .env files
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith('#'):
            continue
        if '=' in _line:
            _key, _val = _line.split('=', 1)
            os.environ.setdefault(_key.strip(), _val.strip())

# = = = log dir = = =
LOG_DIR = Path(os.getenv("ASTRIX_LOG_DIR", str(Path(__file__).parent.parent / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)

# = = = llm config = = =
LLM_URL = os.getenv("LLM_URL", "http://localhost:20128/v1/chat/completions")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = None  # dynamic via runtime.get_model_id ()

# = = = workspace = = =
WORKSPACE = os.getenv("ASTRIX_WORKSPACE", str(Path.home()))

# Server 
PORT = int(os.getenv("ASTRIX_PORT", "8765"))
HOST = os.getenv("ASTRIX_HOST", "0.0.0.0")

# = = = ASTRIX ROOT (workspace root) = = =
ASTRIX_ROOT = Path(os.getenv("ASTRIX_ROOT", str(Path.home())))

# = = = SELF EDIT (existing) = = =
SELF_ROOT = Path(__file__).parent.parent
SELF_EDIT_WHITELIST = [
    "6_agent/",
    "web/static/",
    "web/server.py",
]

if not LLM_API_KEY:
    print("⚠️  WARNING: LLM_API_KEY kosong. Copy .env.example ke .env dan isi API key.")

# Deleted file storage folder
from pathlib import Path
TRASH_DIR = ASTRIX_ROOT / '.trash'

# = = = auto-added missing config = = =
import os
from pathlib import Path

LOG_FILE = Path(os.environ.get("ASTRIX_WORKSPACE", ".")) / "agent.log"
ALLOWED_COMMANDS = {"ls", "cat", "grep", "make", "python3", "python", "git", "mkdir", "rm", "mv", "cp", "echo", "pwd", "find", "sed", "awk", "touch", "npm", "node", "gcc", "g++"}
SELF_ROOT = Path(__file__).parent.parent
SELF_EDIT_WHITELIST = ["6_agent/", "web/"]
SELF_EDIT_BLOCK = [".env", "config.py"]
MAX_FILE_READ_BYTES = 100000
MAX_TOOL_RESULT_CHARS = 5000
WRITABLE_EXT = {".c", ".h", ".py", ".txt", ".md", ".json", ".yaml", ".yml", ".sh", ".html", ".css", ".js", ".ts", ".toml", ".ini", ".cfg", ".make", ".mk", ".S", ".asm", ".cpp"}
WRITABLE_NAMES = {"Makefile", "Dockerfile", "Kconfig"}
VERIFY_COMPILER = {
    ".py": ["python3", "-m", "py_compile"],
    ".c": ["gcc", "-fsyntax-only"],
    ".h": ["gcc", "-fsyntax-only"],
    ".cpp": ["g++", "-fsyntax-only"]
}
