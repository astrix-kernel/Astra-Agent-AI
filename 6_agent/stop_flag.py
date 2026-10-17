"""Global stop flag — buat cancel chat yang lagi jalan."""
import threading

_lock = threading.Lock()
_stop_flags = {} 
_current = {"sid": None}

def set_current(sid):
    with _lock:
        _current["sid"] = sid
        _stop_flags[sid] = False

def request_stop(sid=None):
    with _lock:
        target = sid or _current["sid"]
        if target:
            _stop_flags[target] = True
            return True
        return False

def is_stopped(sid=None):
    with _lock:
        target = sid or _current["sid"]
        return _stop_flags.get(target, False) if target else False

def clear(sid=None):
    with _lock:
        target = sid or _current["sid"]
        if target:
            _stop_flags.pop(target, None)
