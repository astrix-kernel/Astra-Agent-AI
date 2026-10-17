"""Registry model — NVIDIA + Agy (Antigravity) providers."""


REASONING_MODELS = {
    "nemotron-ultra", "nemotron-super", "nemotron-lightning", "nemotron-nano",
    "kimi-k3", "deepseek-pro", "gpt-oss-120b", "gpt-oss-120b-medium",
    "claude-opus-thinking", "claude-sonnet-thinking",
    "gemini-3.8-high", "gemini-3.8-tiered",
}


def is_reasoning(key):
    return key in REASONING_MODELS


MODELS = {
    "nemotron-ultra": {
        "id": "nvidia/nvidia/nemotron-3-ultra-550b-a55b",
        "label": "Nemotron 3 Ultra 550B",
        "icon": "🔥",
        "desc": "Raksasa. Reasoning + coding paling kuat. Lambat.",
        "speed": 1, "reasoning": 5, "coding": 5,
        "use_case": "Goal besar, arsitektur, task kompleks",
        "recommended_mode": "maximum",
    },
    "nemotron-super": {
        "id": "nvidia/nvidia/nemotron-3-super-120b-a12b",
        "label": "Nemotron 3 Super 120B",
        "icon": "⚡",
        "desc": "Seimbang. Kuat, lebih cepat dari Ultra.",
        "speed": 3, "reasoning": 4, "coding": 4,
        "use_case": "Daily driver, balance speed+quality",
        "recommended_mode": "medium",
    },
    "nemotron-nano": {
        "id": "nvidia/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "label": "Nemotron 3 Nano Omni 30B",
        "icon": "🧠",
        "desc": "Kecil tapi reasoning. Fokus logika.",
        "speed": 4, "reasoning": 4, "coding": 3,
        "use_case": "Analisis, debug, logika",
        "recommended_mode": "medium",
    },
    "kimi-k3": {
        "id": "nvidia/moonshotai/kimi-k3",
        "label": "Kimi K3",
        "icon": "🌙",
        "desc": "Kuat coding + long context.",
        "speed": 2, "reasoning": 5, "coding": 5,
        "use_case": "Coding berat, refactor besar",
        "recommended_mode": "maximum",
    },
    "deepseek-pro": {
        "id": "nvidia/deepseek-ai/deepseek-v4-pro-0813",
        "label": "DeepSeek V4 Pro",
        "icon": "🐋",
        "desc": "Coding top-tier. Reasoning kuat.",
        "speed": 3, "reasoning": 5, "coding": 5,
        "use_case": "Coding kompleks, algoritma",
        "recommended_mode": "maximum",
    },
    "laguna-xs": {
        "id": "nvidia/poolside/laguna-xs-2.1",
        "label": "Laguna XS 2.1",
        "icon": "🏄",
        "desc": "Model ringan, cepat. Buat chat & autocomplete.",
        "speed": 5, "reasoning": 2, "coding": 3,
        "use_case": "Chat cepat, autocomplete",
        "recommended_mode": "minimum",
    },
    "gemma-4": {
        "id": "nvidia/google/gemma-4-31b-it",
        "label": "Gemma 4 31B (NVIDIA)",
        "icon": "💎",
        "desc": "Google model via NVIDIA. Penjelasan bagus.",
        "speed": 4, "reasoning": 3, "coding": 3,
        "use_case": "Dokumentasi, penjelasan",
        "recommended_mode": "minimum",
    },

    "claude-opus-thinking": {
        "id": "agy/claude-opus-4-6-thinking",
        "label": "Claude Opus 4.6 (Thinking)",
        "icon": "👑",
        "desc": "TOP-TIER. Claude Opus dengan thinking mode. Paling pinter, paling lambat.",
        "speed": 1, "reasoning": 5, "coding": 5,
        "use_case": "Masalah paling susah, arsitektur kompleks",
        "recommended_mode": "maximum",
    },
    "claude-sonnet-thinking": {
        "id": "agy/claude-sonnet-4-6",
        "label": "Claude Sonnet 4.6 (Thinking)",
        "icon": "🎭",
        "desc": "Claude Sonnet. Balance kualitas + kecepatan.",
        "speed": 3, "reasoning": 5, "coding": 5,
        "use_case": "Coding harian berkualitas, reasoning",
        "recommended_mode": "medium",
    },
    "gemini-3.8-high": {
        "id": "agy/gemini-3.8-flash-high",
        "label": "Gemini 3.8 Flash (High)",
        "icon": "✨",
        "desc": "Gemini terbaru, thinking high effort.",
        "speed": 3, "reasoning": 5, "coding": 4,
        "use_case": "Coding kompleks, reasoning tinggi",
        "recommended_mode": "medium",
    },
    "gemini-3.8-medium": {
        "id": "agy/gemini-3.8-flash-medium",
        "label": "Gemini 3.8 Flash (Medium)",
        "icon": "🌟",
        "desc": "Gemini 3.8 balanced. Cepat + pinter.",
        "speed": 4, "reasoning": 4, "coding": 4,
        "use_case": "Daily driver terbaik",
        "recommended_mode": "medium",
    },
    "gemini-3.8-low": {
        "id": "agy/gemini-3.8-flash-low",
        "label": "Gemini 3.8 Flash (Low)",
        "icon": "💫",
        "desc": "Gemini cepat, thinking minimal.",
        "speed": 5, "reasoning": 3, "coding": 3,
        "use_case": "Chat cepat, task simple",
        "recommended_mode": "minimum",
    },
    "gemini-3.8-tiered": {
        "id": "agy/gemini-3.8-flash-tiered",
        "label": "Gemini 3.8 Flash (Tiered)",
        "icon": "🎚️",
        "desc": "Gemini auto-tier. Adaptif effort.",
        "speed": 4, "reasoning": 4, "coding": 4,
        "use_case": "Serba bisa, adaptive",
        "recommended_mode": "medium",
    },
    "gemini-3-flash": {
        "id": "agy/gemini-3-flash",
        "label": "Gemini 3 Flash",
        "icon": "🌈",
        "desc": "Gemini 3 stabil. Cepat.",
        "speed": 5, "reasoning": 3, "coding": 3,
        "use_case": "Chat, task ringan",
        "recommended_mode": "minimum",
    },
    "gemini-3.5-lite": {
        "id": "agy/gemini-3.5-flash-lite",
        "label": "Gemini 3.5 Flash Lite",
        "icon": "🪶",
        "desc": "Gemini paling ringan. Super cepat.",
        "speed": 5, "reasoning": 2, "coding": 2,
        "use_case": "Chat super cepat, autocomplete",
        "recommended_mode": "minimum",
    },
    "gemini-3.1-lite": {
        "id": "agy/gemini-3.1-flash-lite",
        "label": "Gemini 3.1 Flash Lite",
        "icon": "🌾",
        "desc": "Gemini lite. Untuk task sangat ringan.",
        "speed": 5, "reasoning": 2, "coding": 2,
        "use_case": "Chat ringan, test",
        "recommended_mode": "minimum",
    },
    "gemini-3.1-image": {
        "id": "agy/gemini-3.1-flash-image",
        "label": "Gemini 3.1 Flash Image",
        "icon": "🖼️",
        "desc": "Gemini dengan kemampuan vision/image.",
        "speed": 4, "reasoning": 3, "coding": 3,
        "use_case": "Analisis gambar, screenshot, vision",
        "recommended_mode": "medium",
    },
    "gpt-oss-120b-medium": {
        "id": "agy/gpt-oss-120b-medium",
        "label": "GPT-OSS 120B (Medium)",
        "icon": "🤖",
        "desc": "GPT open-source via Agy. Generalis kuat.",
        "speed": 3, "reasoning": 4, "coding": 4,
        "use_case": "General purpose",
        "recommended_mode": "medium",
    },
    "cgpt-codex": {
        "id": "agy/cgpt-codex/extra-high",
        "label": "Codex (Extra High)",
        "icon": "💻",
        "desc": "Codex dengan effort extra-high. Coding specialist.",
        "speed": 2, "reasoning": 5, "coding": 5,
        "use_case": "Coding kompleks, refactor besar",
        "recommended_mode": "maximum",
    },
}


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
    """Group by provider for UI."""

    groups = {"nvidia": [], "agy": []}
    for k, v in MODELS.items():
        if v["id"].startswith("nvidia/"):
            groups["nvidia"].append({"key": k, **v})
        elif v["id"].startswith("agy/"):
            groups["agy"].append({"key": k, **v})
        else:
            groups.setdefault("other", []).append({"key": k, **v})
    return groups
