"""Runtime mode state-global, shared by all modules."""

import json
from pathlib import Path
from config import LOG_DIR
from budget import get_mode

_MODE_FILE = LOG_DIR / "mode.json"
_current = None


def _load():
    global _current
    if _MODE_FILE.exists():
        try:
            _current = json.loads(_MODE_FILE.read_text()).get("mode", "medium")
        except Exception:
            _current = "medium"
    else:
        _current = "medium"
    return _current


def _save():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _MODE_FILE.write_text(json.dumps({"mode": _current}))


def get():
    if _current is None:
        _load()
    return _current


def set_mode(name):
    global _current
    name = name.lower()
    if name not in ("minimum", "medium", "maximum"):
        raise ValueError(f"Mode '{name}' nggak valid. Pilih: minimum, medium, maximum")
    _current = name
    _save()
    return name


def cfg():
    """Return config dict for active mode."""

    return get_mode(get())


# = = = = = = = = = = = management model = = = = = = = = = = = =
_MODEL_FILE = LOG_DIR / "model.json"
_current_model = None


def _load_model():
    global _current_model
    if _MODEL_FILE.exists():
        try:
            _current_model = json.loads(_MODEL_FILE.read_text()).get("model")
        except Exception:
            _current_model = None
    else:
        _current_model = None
    return _current_model


def _save_model():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _MODEL_FILE.write_text(json.dumps({"model": _current_model}))


def get_model_key():
    """Return short key (ex: 'nemotron-ultra')."""

    if _current_model is None:
        _load_model()
    return _current_model


def set_model(key):
    global _current_model
    from models import MODELS
    key = key.lower()
    if key not in MODELS:
        raise ValueError(f"Model '{key}' nggak ada. Pilih: {', '.join(MODELS.keys())}")
    _current_model = key
    _save_model()
    return key


def get_model():
    """Return full model info dict. Raise if not already selected."""

    from models import MODELS
    key = get_model_key()
    if key is None or key not in MODELS:
        raise RuntimeError("Belum pilih model. Pilih dulu di dropdown model UI Astrix.")
    return MODELS[key]


def get_model_id():
    """Return full model ID for API call."""

    return get_model()["id"]
