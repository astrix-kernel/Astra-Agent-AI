"""Sync model registry dari OmniRoute /v1/models — multi-provider."""
import json
import urllib.request
from pathlib import Path
from config import LLM_URL, LLM_API_KEY, LOG_DIR

CACHE_FILE = LOG_DIR / "models_cache.json"

# Provider yang di-sync (prefix model id)
SYNC_PROVIDERS = ["nvidia", "cinf", "auto", "agy", "ds", "openrouter"]

# Filter — model ini BUKAN chat model, skip
SKIP_KEYWORDS = [
    "embed", "rerank", "nvclip", "safety", "guard",
    "detector", "parse", "retriever", "reward",
    "content-safety", "topic-control", "riva-translate",
    "ai-synthetic", "cosmos", "ising-calibration",
    "neva", "vila", "deplot", "kosmos", "fuyu",
    "palmyra-fin", "palmyra-med", "palmyra-creative",
    "arctic-embed", "nv-embed", "bge-", "e5-",
]

CODING_KEYWORDS = ["code", "coder", "dev", "qwen", "deepseek", "kimi"]
REASONING_KEYWORDS = ["reasoning", "thinking", "ultra", "nemotron", "super", "opus", "pro", "glm-5", "gpt-5"]
VISION_KEYWORDS = ["vision", "vl", "vila", "fuyu", "kosmos", "neva", "image"]


def _should_skip(model_id):
    low = model_id.lower()
    return any(k in low for k in SKIP_KEYWORDS)


def _classify(model_id):
    low = model_id.lower()
    is_coding = any(k in low for k in CODING_KEYWORDS)
    is_reason = any(k in low for k in REASONING_KEYWORDS)
    is_vision = any(k in low for k in VISION_KEYWORDS)
    if is_coding and is_reason:
        return {"speed": 2, "reasoning": 5, "coding": 5, "recommended_mode": "maximum"}
    if is_reason:
        return {"speed": 2, "reasoning": 4, "coding": 4, "recommended_mode": "medium"}
    if is_coding:
        return {"speed": 3, "reasoning": 3, "coding": 4, "recommended_mode": "medium"}
    if is_vision:
        return {"speed": 4, "reasoning": 3, "coding": 3, "recommended_mode": "medium"}
    return {"speed": 4, "reasoning": 3, "coding": 3, "recommended_mode": "minimum"}


def _short_key(model_id):
    """Bikin key pendek unik dari model id."""
    parts = model_id.split("/")
    if parts[0] == "nvidia":
        name = parts[-1]
        return f"nv-{name}"[:45]
    elif parts[0] == "cinf":
        name = "/".join(parts[1:])
        return f"cf-{name.replace('/', '-')}"[:45]
    elif parts[0] == "auto":
        name = "-".join(parts[1:])
        return f"auto-{name}"[:45]
    elif parts[0] == "agy":
        name = "/".join(parts[1:])
        return f"agy-{name.replace('/', '-')}"[:45]
    elif parts[0] == "ds":
        name = "/".join(parts[1:])
        return f"ds-{name.replace('/', '-')}"[:45]
    return model_id.replace("/", "-")[:45]


def _make_label(model_id):
    name = model_id.split("/")[-1]
    return name.replace("-", " ").replace("_", " ").replace(".", " ").title()[:50]


def _pick_icon(model_id):
    low = model_id.lower()
    if "opus" in low: return "👑"
    if "sonnet" in low: return "🎭"
    if "haiku" in low: return "🌸"
    if "gemini" in low: return "✨"
    if "gpt-5" in low: return "🤖"
    if "glm" in low: return "🀄"
    if "deepseek" in low: return "🐋"
    if "grok" in low: return "⚡"
    if "kimi" in low: return "🌙"
    if "minimax" in low: return "🎯"
    if "nemotron" in low: return "🔥"
    if "aion" in low: return "🌟"
    if "claude" in low: return "🎭"
    return "🎯"


def sync_from_omniroute(timeout=30):
    url = LLM_URL.replace("/chat/completions", "/models")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {LLM_API_KEY}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())

    models = {}
    for m in data.get("data", []):
        mid = m.get("id", "")
        # Skip kalau bukan provider yang di-sync
        if not any(mid.startswith(f"{p}/") for p in SYNC_PROVIDERS):
            continue
        if _should_skip(mid):
            continue
        key = _short_key(mid)
        base = key
        i = 2
        while key in models:
            key = f"{base}-{i}"
            i += 1
        stats = _classify(mid)
        models[key] = {
            "id": mid,
            "label": _make_label(mid),
            "icon": _pick_icon(mid),
            "desc": f"Auto-imported: {mid}",
            "use_case": "General purpose (auto-synced)",
            **stats,
        }
    return models


def save_cache(models):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(models, indent=2))


def load_cache():
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text())
    except Exception:
        return {}


def sync_and_save():
    try:
        models = sync_from_omniroute()
        if models:
            save_cache(models)
        return len(models), None
    except Exception as e:
        return 0, str(e)


if __name__ == "__main__":
    n, err = sync_and_save()
    print(f"❌ {err}" if err else f"✅ Synced {n} models")
