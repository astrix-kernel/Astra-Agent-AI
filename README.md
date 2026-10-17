# Astro AI Agent

Local-first AI agent with browser automation, multi-agent orchestration, and long-term memory. Runs 100% on your machine — no cloud, no telemetry.

## Features

- **1492+ models** are available via OmniRoute multi-provider routing; the specific number of models you receive may vary depending on the providers you use, such as 9router or OpenRouter.
- **Browser automation** — open, click, type, screenshot (Playwright)
- **Multi-agent** — Planner + Executor with file write & command execution
- **Long-term memory** — SQLite-based fact storage
- **Workspace manager** — pick project folder, auto-detect project type
- **11-tab settings** with auto-save + 5 quick modes
- **Bilingual UI** — Indonesian & English
- **Stop button** — abort mid-stream
- **Image vision** — supported with vision-capable models
- **100% local** — no telemetry, no cloud sync

## Requirements

- Python 3.10+
- Linux/Archlinux
- OmniRoute or any OpenAI-compatible API
- Playwright
- 8GB+ RAM recommended

## Quick Start

### 1. Clone

    git clone https://github.com/astrix-kernel/astro-agent.git
    cd astro-agent

### 2. Install dependencies

    pip install -r requirements.txt
    playwright install chromium

### 3. Configure

    cp .env.example .env
    nano .env

Fill in `LLM_URL` and `LLM_API_KEY`.

### 4. Run

    python3 web/server.py

Open http://localhost:8765 in your browser.

## Configuration

*Note: The environment variables below still use the `ASTRIX_` prefix in the codebase.*

| Variable | Default | Description |
|---|---|---|
| LLM_URL | http://localhost:20128/v1/chat/completions | API endpoint |
| LLM_API_KEY | (required) | API key |
| ASTRIX_WORKSPACE | ~/ | Default project folder |
| ASTRIX_PORT | 8765 | Server port |
| ASTRIX_HOST | 0.0.0.0 | Server host |
| ASTRIX_LOG_DIR | ./logs/ | Log directory |

## Usage Examples

**Browser automation:**
    Open https://wikipedia.org/wiki/Linux and summarize the first 200 words

**Click & navigate:**
    Open https://example.com then click 'a'

**Multi-agent write file:**
    Create file /tmp/notes.txt with content: Hello world

**Multi-agent run command:**
    Run "ls -la" in /tmp and report files

**Long-term memory:**
    My name is Arsa, I'm working on a Python project

## Architecture

    astro-agent/
    ├── 6_agent/           # Agent logic
    │   ├── chat.py        # Chat orchestration
    │   ├── multi_agent.py # Planner + Executor
    │   ├── memory.py      # SQLite memory
    │   ├── browser_agent.py # Playwright
    │   ├── tools.py       # Tool registry
    │   └── config.py      # Config loader
    ├── web/
    │   ├── server.py      # FastAPI backend
    │   └── static/        # Frontend
    ├── requirements.txt
    ├── .env.example
    └── README.md

> **Note:** separate project. The agent uses OmniRoute for LLM routing and
> does not require local models.

## Troubleshooting

### `error: externally-managed-environment` (PEP 668)
If you are using a modern Linux distribution (like Arch Linux, Ubuntu 23.04+, or Fedora) and encounter this error when running `pip install -r requirements.txt`, it means your OS is protecting its system Python packages.

**Solution:** Always use a Python Virtual Environment (`.venv`).

```bash
# 1. Create the virtual environment
python -m venv .venv

# 2. Activate it (Linux / macOS)
source .venv/bin/activate
# (For Windows: .venv\Scripts\activate)

# 3. Install the dependencies
pip install -r requirements.txt
