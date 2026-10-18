"""Session Database — SQLite wrapper untuk history, stats, notifications."""
import sqlite3
import json
import time
from pathlib import Path
from contextlib import contextmanager

DB_DIR = Path.home() / ".astra-agent"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_FILE = DB_DIR / "sessions.db"


def _init_db():
    """Init tables kalau belum ada."""
    with _connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal TEXT NOT NULL,
            workspace TEXT,
            status TEXT DEFAULT 'running',
            started_at REAL NOT NULL,
            finished_at REAL,
            total_tasks INTEGER DEFAULT 0,
            completed INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            cost REAL DEFAULT 0.0,
            tokens_in INTEGER DEFAULT 0,
            tokens_out INTEGER DEFAULT 0,
            tasks_json TEXT,
            results_json TEXT
        );
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            task_idx INTEGER,
            tool TEXT,
            args_json TEXT,
            result TEXT,
            timestamp REAL NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );
        CREATE TABLE IF NOT EXISTS stats (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_actions_session ON actions(session_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at DESC);
        """)
        # Init default stats
        for _k in ["total_tasks_completed", "total_tasks_failed",
                   "total_files_modified", "total_cost", "streak_days",
                   "last_active_day", "first_use_day"]:
            conn.execute(
                "INSERT OR IGNORE INTO stats (key, value) VALUES (?, ?)",
                (_k, "0" if _k != "last_active_day" and _k != "first_use_day" else "")
            )


@contextmanager
def _connect():
    conn = sqlite3.connect(str(DB_FILE), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def create_session(goal, workspace):
    """Buat session baru, return session_id."""
    _init_db()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (goal, workspace, status, started_at) VALUES (?, ?, 'running', ?)",
            (goal, str(workspace), time.time())
        )
        return cur.lastrowid


def update_session(session_id, **kwargs):
    """Update field session (status, completed, cost, dll)."""
    if not kwargs:
        return
    allowed = {"status", "finished_at", "total_tasks", "completed", "failed",
               "cost", "tokens_in", "tokens_out", "tasks_json", "results_json"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [session_id]
    with _connect() as conn:
        conn.execute(f"UPDATE sessions SET {set_clause} WHERE id = ?", vals)


def log_action(session_id, task_idx, tool, args, result, timestamp=None):
    """Log action (read, write, run_command, dll) untuk live preview."""
    if timestamp is None:
        timestamp = time.time()
    try:
        args_json = json.dumps(args, default=str)[:500]
    except Exception:
        args_json = "{}"
    with _connect() as conn:
        conn.execute(
            "INSERT INTO actions (session_id, task_idx, tool, args_json, result, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, task_idx, str(tool), args_json, str(result)[:300], timestamp)
        )


def get_session(session_id):
    """Get detail session + tasks + actions."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not row:
            return None
        session = dict(row)
        try:
            session["tasks"] = json.loads(session.get("tasks_json") or "[]")
            session["results"] = json.loads(session.get("results_json") or "[]")
        except Exception:
            session["tasks"] = []
            session["results"] = []
        actions = conn.execute(
            "SELECT * FROM actions WHERE session_id = ? ORDER BY timestamp ASC LIMIT 200",
            (session_id,)
        ).fetchall()
        session["actions"] = [dict(a) for a in actions]
        return session


def list_sessions(limit=20):
    """List sessions, newest first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, goal, status, started_at, finished_at, total_tasks, completed, failed, cost "
            "FROM sessions ORDER BY started_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_active_session():
    """Session dengan status='running' terbaru."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE status = 'running' ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        session = dict(row)
        try:
            session["tasks"] = json.loads(session.get("tasks_json") or "[]")
            session["results"] = json.loads(session.get("results_json") or "[]")
        except Exception:
            session["tasks"] = []
            session["results"] = []
        actions = conn.execute(
            "SELECT * FROM actions WHERE session_id = ? ORDER BY timestamp DESC LIMIT 20",
            (session["id"],)
        ).fetchall()
        session["actions"] = [dict(a) for a in reversed(actions)]
        return session


def get_recent_actions(session_id, limit=20):
    """Recent actions untuk live preview (newest last)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM actions WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
            (session_id, limit)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]


# === STATS ===
def stats_get_all():
    """Return dict of all stats."""
    with _connect() as conn:
        rows = conn.execute("SELECT key, value FROM stats").fetchall()
        return {r["key"]: r["value"] for r in rows}


def stats_increment(key, amount=1):
    """Increment integer stat."""
    with _connect() as conn:
        row = conn.execute("SELECT value FROM stats WHERE key = ?", (key,)).fetchone()
        if not row:
            conn.execute("INSERT INTO stats (key, value) VALUES (?, ?)", (key, str(amount)))
        else:
            try:
                new_val = int(row["value"] or 0) + amount
            except Exception:
                new_val = amount
            conn.execute("UPDATE stats SET value = ? WHERE key = ?", (str(new_val), key))


def stats_set(key, value):
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO stats (key, value) VALUES (?, ?)",
            (key, str(value))
        )


def update_streak():
    """Update streak berdasarkan hari ini."""
    from datetime import date
    today = date.today().isoformat()
    with _connect() as conn:
        rows = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM stats").fetchall()}
        last = rows.get("last_active_day", "")
        streak = int(rows.get("streak_days", "0") or 0)
        first = rows.get("first_use_day", "")

        if last == today:
            return streak  # no-op

        from datetime import datetime, timedelta
        if last:
            try:
                last_dt = datetime.fromisoformat(last).date()
                diff = (date.today() - last_dt).days
                if diff == 1:
                    streak += 1
                elif diff > 1:
                    streak = 1  # reset
            except Exception:
                streak = 1
        else:
            streak = 1

        if not first:
            first = today

        conn.execute("UPDATE stats SET value = ? WHERE key = 'streak_days'", (str(streak),))
        conn.execute("UPDATE stats SET value = ? WHERE key = 'last_active_day'", (today,))
        conn.execute("UPDATE stats SET value = ? WHERE key = 'first_use_day'", (first,))
        return streak


print("[SESSION_DB] loaded")
