"""Configuration — load from .env file (do not hardcode API key!)."""

import os
from pathlib import Path
from contextlib import contextmanager
from contextvars import ContextVar

_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith('#'):
            continue
        if '=' in _line:
            _key, _val = _line.split('=', 1)
            os.environ.setdefault(_key.strip(), _val.strip())


# === WORKSPACE: default + konteks lokal per request ===
SELF_ROOT = Path(__file__).parent.parent.resolve()
ASTRIX_ROOT = SELF_ROOT
# Default to the current OS user's home when no workspace is configured.
# ASTRIX_WORKSPACE remains an optional explicit override.
_DEFAULT_WORKSPACE = Path(
    os.getenv("ASTRIX_WORKSPACE") or str(Path.home())
).expanduser().resolve()

# Kompatibilitas kode lama. Operasi request sebaiknya memakai get_workspace().
WORKSPACE = _DEFAULT_WORKSPACE
_WORKSPACE_CONTEXT = ContextVar("astrix_workspace", default=None)


def get_workspace() -> Path:
    """Ambil workspace yang aktif dalam konteks saat ini."""
    return _WORKSPACE_CONTEXT.get() or _DEFAULT_WORKSPACE


def get_allowed_workspace_roots():
    """Root tepercaya untuk pilihan workspace.

    Jika ASTRIX_ALLOWED_WORKSPACE_ROOTS ditentukan, hanya root
    eksplisit tersebut yang diizinkan. Tanpa konfigurasi itu,
    instalasi lokal memakai home pengguna dan default workspace.
    """
    configured = os.getenv("ASTRIX_ALLOWED_WORKSPACE_ROOTS", "").strip()

    if configured:
        candidates = [
            Path(item).expanduser()
            for item in configured.split(os.pathsep)
            if item.strip()
        ]
    else:
        candidates = [Path.home(), _DEFAULT_WORKSPACE]

    roots = []
    seen = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            if resolved.is_dir() and resolved not in seen:
                roots.append(resolved)
                seen.add(resolved)
        except (OSError, RuntimeError):
            continue

    return tuple(roots)

def is_workspace_path_allowed(path) -> bool:
    """Periksa apakah path berada di dalam salah satu root tepercaya."""
    try:
        candidate = Path(path).expanduser().resolve()
        for root in get_allowed_workspace_roots():
            if candidate == root or root in candidate.parents:
                return True
    except (OSError, RuntimeError, ValueError):
        return False
    return False


def resolve_workspace_path(path) -> Path:
    """Validasi workspace: harus berupa direktori di root tepercaya."""
    if path is None or not str(path).strip():
        raise ValueError("Workspace path kosong.")

    try:
        candidate = Path(path).expanduser().resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError(f"Workspace path tidak valid: {exc}") from exc

    if not candidate.is_dir():
        raise ValueError(f"Workspace bukan direktori yang ada: {candidate}")

    if not is_workspace_path_allowed(candidate):
        raise PermissionError(
            f"Workspace di luar root yang diizinkan: {candidate}"
        )

    return candidate


@contextmanager
def workspace_context(new_path=None):
    """Aktifkan workspace sementara, lalu pulihkan konteks."""
    selected = resolve_workspace_path(
        get_workspace() if new_path is None else new_path
    )

    token = _WORKSPACE_CONTEXT.set(selected)
    try:
        yield selected
    finally:
        _WORKSPACE_CONTEXT.reset(token)


def set_workspace(new_path: str):
    """Setter kompatibilitas dalam konteks eksekusi saat ini."""
    if not new_path:
        return False
    try:
        selected = resolve_workspace_path(new_path)
        _WORKSPACE_CONTEXT.set(selected)
        return True
    except (OSError, RuntimeError, ValueError, PermissionError):
        return False

def workspace_scoped(function):
    """Isolasi workspace untuk satu pemanggilan fungsi."""
    from functools import wraps
    from inspect import signature

    sig = signature(function)

    @wraps(function)
    def wrapped(*args, **kwargs):
        bound = sig.bind_partial(*args, **kwargs)
        selected = bound.arguments.get("workspace")
        with workspace_context(selected):
            return function(*args, **kwargs)

    return wrapped

LOG_DIR = Path(os.getenv("ASTRIX_LOG_DIR", str(Path(__file__).parent.parent / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)

LLM_URL = os.getenv("LLM_URL", "http://localhost:20128/v1/chat/completions")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", None)
# Model fallback kalau user gak set LLM_MODEL. Empty string = provider default.
DEFAULT_MODEL = os.getenv("ASTRIX_DEFAULT_MODEL", "") 



PORT = int(os.getenv("ASTRIX_PORT", "8765"))
HOST = os.getenv("ASTRIX_HOST", "0.0.0.0")




if not LLM_API_KEY:
    print("⚠️  WARNING: LLM_API_KEY kosong. Copy .env.example ke .env dan isi API key.")

from pathlib import Path
TRASH_DIR = ASTRIX_ROOT / '.trash'

import os
from pathlib import Path

# === LLM request limits ===
MAX_TOKENS_PER_RESPONSE = 4096

LOG_FILE = Path(os.getenv("ASTRIX_LOG_FILE", str(LOG_DIR / "agent.log"))).expanduser().resolve()
ALLOWED_COMMANDS = {"ls", "cat", "grep", "make", "python3", "python", "git", "mkdir", "rm", "mv", "cp", "echo", "pwd", "find", "sed", "awk", "touch", "npm", "node", "gcc", "g++", "ping", "curl", "wget", "tree", "head", "tail", "wc", "ps", "top", "df", "free", "uname", "chmod", "chown", "tar", "zip", "unzip", "xdg-open"}
SELF_EDIT_WHITELIST = ["6_agent/", "web/static/", "web/server.py"]
SELF_EDIT_BLOCK = [".env", "config.py"]
MAX_FILE_READ_BYTES = 100000
MAX_TOOL_RESULT_CHARS = 5000
WRITABLE_EXT = {".c", ".h", ".py", ".txt", ".md", ".json", ".yaml", ".yml", ".sh", ".html", ".css", ".js", ".ts", ".toml", ".ini", ".cfg", ".make", ".mk", ".S", ".s", ".asm", ".cpp", ".hpp", ".cc", ".hh", ".ld", ".lds", ".rs", ".go", ".zig", ".java", ".rb", ".php", ".lua", ".vue", ".tsx", ".jsx", ".m", ".mm", ".xml", ".csv"}
WRITABLE_NAMES = {"Makefile", "Dockerfile", "Kconfig"}
VERIFY_COMPILER = {
    ".py": ["python3", "-m", "py_compile"],
    ".c": ["gcc", "-fsyntax-only"],
    ".h": ["gcc", "-fsyntax-only"],
    ".cpp": ["g++", "-fsyntax-only"],
    ".cc": ["g++", "-fsyntax-only"],
    ".hpp": ["g++", "-fsyntax-only"],
    ".hh": ["g++", "-fsyntax-only"]
}

# Timeout request buat planner (detik)
REQUEST_TIMEOUT = 300

REQUEST_TIMEOUT = 300


# === Agent Task Limits ===
MAX_TASKS_DEFAULT = 40  # safety cap, AI decides actual count
MAX_RETRIES_PER_TASK = 6  # beneran retry 6x dengan reflection
MAX_TOTAL_ATTEMPTS = None  # auto: max_tasks * 3
