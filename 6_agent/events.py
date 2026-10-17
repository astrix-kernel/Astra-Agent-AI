"""Event bus — broadcast event internal ke listener (server, dll)."""
import time

_listeners = []
_activity_log = []
_totals = {"added": 0, "removed": 0}


def emit(event_type, data):
    data["event"] = event_type
    data["ts"] = time.time()
    _activity_log.append(data)
    if len(_activity_log) > 2000:
        del _activity_log[:-2000]
    # Update totals kalau file change
    if event_type == "file_change":
        _totals["added"] += data.get("added", 0)
        _totals["removed"] += data.get("removed", 0)
    for cb in _listeners:
        try:
            cb(event_type, data)
        except Exception:
            pass


def on_event(cb):
    _listeners.append(cb)


def get_activity(since=0):
    return [e for e in _activity_log if e.get("ts", 0) > since and e.get("event") == "file_change"]


def get_totals():
    return dict(_totals)


def reset():
    _activity_log.clear()
    _totals["added"] = 0
    _totals["removed"] = 0
