"""File watcher — track file changes in the workspace."""

import threading, time
from pathlib import Path
from config import ASTRIX_ROOT

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

THROTTLE_SECONDS = 15
IGNORE_DIRS = {".git", "build", "__pycache__", "node_modules", ".kilo", "dist"}
IGNORE_EXTS = {".o", ".obj", ".bin", ".img", ".tmp", ".log", ".swp", ".bak"}
WATCH_EXTS = {".c", ".h", ".S", ".asm", ".ld", ".mk", ".py", ".sh"}

_observer = None
_recent = {}
_callbacks = []
_recent_changes = []


class _Handler(FileSystemEventHandler):
    def on_modified(self, event):
        if not event.is_directory:
            self._handle("modified", event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self._handle("created", event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self._handle("deleted", event.src_path)

    def _handle(self, action, path):
        p = Path(path)
        for part in p.parts:
            if part in IGNORE_DIRS:
                return
        if p.suffix in IGNORE_EXTS:
            return
        if p.suffix not in WATCH_EXTS and p.name not in {"Makefile", "Kconfig"}:
            return

        now = time.time()
        last = _recent.get(str(p), 0)
        if now - last < THROTTLE_SECONDS:
            return
        _recent[str(p)] = now

        try:
            rel = str(p.relative_to(ASTRIX_ROOT))
        except Exception:
            rel = str(p)

        entry = {"action": action, "path": rel, "ts": now}
        _recent_changes.append(entry)
        if len(_recent_changes) > 200:
            del _recent_changes[:-200]

        for cb in _callbacks:
            try:
                cb(action, rel, str(p))
            except Exception:
                pass


def on_change(callback):
    _callbacks.append(callback)


def start():
    global _observer
    if not HAS_WATCHDOG:
        return False, "Install: pip install watchdog --break-system-packages"
    if _observer is not None:
        return True, "Watcher udah jalan"
    if not ASTRIX_ROOT.exists():
        return False, f"ASTRIX_ROOT nggak ada"

    _observer = Observer()
    _observer.schedule(_Handler(), str(ASTRIX_ROOT), recursive=True)
    _observer.daemon = True
    _observer.start()
    return True, f"👁️ Watching {ASTRIX_ROOT}"


def stop():
    global _observer
    if _observer:
        _observer.stop()
        _observer.join(timeout=3)
        _observer = None
        return True, "Stopped"
    return False, "Nggak jalan"


def is_running():
    return _observer is not None and _observer.is_alive()


def get_recent(limit=20):
    return _recent_changes[-limit:]


def clear_recent():
    _recent_changes.clear()
