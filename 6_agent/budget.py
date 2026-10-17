"""Budget mode — atur konsumsi Nemotron 3 Ultra."""

MODES = {
    "minimum": {
        "icon": "🌱",
        "label": "Hemat",
        "desc": "Hemat token & waktu. Buat task kecil, chat singkat.",
        # LLM
        "temperature": 0.05,
        "max_tokens_chat": 1024,
        "max_tokens_executor": 2048,
        "max_tokens_planner": 3072,
        # Agent
        "max_agent_steps": 15,
        "max_agent_tasks_session": 10,
        "executor_max_steps": 20,
        "planner_max_tasks": 15,
        "task_pause_seconds": 2,
        "build_jobs": 2,
        "memory_window": 5,
        # Retry
        "retry_503_max_wait": 30,
        "retry_503_initial": 5,
    },
    "medium": {
        "icon": "⚖️",
        "label": "Sedang",
        "desc": "Balanced. Cocok buat kerja sehari-hari.",
        "temperature": 0.1,
        "max_tokens_chat": 4096,
        "max_tokens_executor": 8192,
        "max_tokens_planner": 8192,
        "max_agent_steps": 30,
        "max_agent_tasks_session": 50,
        "executor_max_steps": 40,
        "planner_max_tasks": 25,
        "task_pause_seconds": 1,
        "build_jobs": 4,
        "memory_window": 10,
        "retry_503_max_wait": 60,
        "retry_503_initial": 3,
    },
    "maximum": {
        "icon": "🔥",
        "label": "Gahar",
        "desc": "Boros token & waktu. Buat goal besar, task kompleks.",
        "temperature": 0.2,
        "max_tokens_chat": 16384,
        "max_tokens_executor": 32768,
        "max_tokens_planner": 16384,
        "max_agent_steps": 60,
        "max_agent_tasks_session": 200,
        "executor_max_steps": 80,
        "planner_max_tasks": 40,
        "task_pause_seconds": 0,
        "build_jobs": 8,
        "memory_window": 20,
        "retry_503_max_wait": 90,
        "retry_503_initial": 3,
    },
}


def get_mode(name):
    return MODES.get(name.lower(), MODES["medium"])


def all_modes():
    return [{"id": k, **{kk: vv for kk, vv in v.items() if kk in ("icon", "label", "desc")}}
            for k, v in MODES.items()]
