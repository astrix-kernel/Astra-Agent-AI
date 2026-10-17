"""Speed optimizations — auto router, fast mode, cache."""
import time, hashlib, json
from pathlib import Path

# Cache file content (biar nggak baca disk berulang)
_file_cache = {}
_cache_ttl = 60  # detik


def cached_read(path, read_fn):
    """Cache file read selama 60 detik."""
    key = str(path)
    now = time.time()
    if key in _file_cache:
        content, ts = _file_cache[key]
        if now - ts < _cache_ttl:
            return content
    content = read_fn(path)
    _file_cache[key] = (content, now)
    return content


def clear_cache():
    _file_cache.clear()


# ============ AUTO MODEL ROUTER ============
def route_model(task_desc, focus="chat"):
    """
    Pilih model otomatis berdasarkan task.
    Return: (model_key, reason)
    """
    # Auto-route DIMATIKAN — selalu hormatin pilihan user di UI
    return None, "auto-route disabled (user pilih manual)"




# ============ FAST MODE ============
_fast_mode = False


def is_fast():
    return _fast_mode


def set_fast(on):
    global _fast_mode
    _fast_mode = bool(on)
    return _fast_mode
