"""Model registry — merge curated (manual) + auto-synced dari OmniRoute."""
from models_curated import (
    REASONING_MODELS, is_reasoning, MODELS as _CURATED_MODELS,
)
from model_sync import load_cache as _load_sync_cache

_AUTO = _load_sync_cache()
_curated_ids = {v["id"] for v in _CURATED_MODELS.values()}
_filtered_auto = {k: v for k, v in _AUTO.items() if v["id"] not in _curated_ids}

# Curated override auto kalau bentrok
MODELS = {**_CURATED_MODELS, **_filtered_auto}


def get(name):
    return MODELS.get(name.lower())


def by_id(model_id):
    for k, v in MODELS.items():
        if v["id"] == model_id:
            return k, v
    return None, None


def all_models():
    return [{"key": k, **v} for k, v in MODELS.items()]


def default():
    return None


def find_match(model_id):
    key, _ = by_id(model_id)
    return key


def by_provider():
    groups = {}
    for k, v in MODELS.items():
        prov = v["id"].split("/", 1)[0] if "/" in v["id"] else "other"
        groups.setdefault(prov, []).append({"key": k, **v})
    return groups
