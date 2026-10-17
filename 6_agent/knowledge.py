"""Persistent knowledge base — the lessons learned from each task."""

import json, time
from pathlib import Path
from config import LOG_DIR

KB_FILE = LOG_DIR / "knowledge.json"


def _load():
    if not KB_FILE.exists():
        return {
            "patterns": [],      
            "gotchas": [],       
            "conventions": [],   
            "files_map": {},     
        }
    try:
        return json.loads(KB_FILE.read_text())
    except Exception:
        return {"patterns": [], "gotchas": [], "conventions": [], "files_map": {}}


def _save(kb):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    KB_FILE.write_text(json.dumps(kb, indent=2, ensure_ascii=False))


def add_pattern(desc, code_snippet=""):
    kb = _load()
    kb["patterns"].append({"desc": desc, "code": code_snippet[:500], "ts": time.time()})
    kb["patterns"] = kb["patterns"][-50:]
    _save(kb)


def add_gotcha(desc):
    kb = _load()
    kb["gotchas"].append({"desc": desc, "ts": time.time()})
    kb["gotchas"] = kb["gotchas"][-30:]
    _save(kb)


def add_convention(desc):
    kb = _load()
    kb["conventions"].append({"desc": desc, "ts": time.time()})
    kb["conventions"] = kb["conventions"][-30:]
    _save(kb)


def update_file_map(path, notes):
    kb = _load()
    kb["files_map"][path] = {"notes": notes[:500], "ts": time.time()}
    _save(kb)


def build_knowledge_block(max_items=8):
    """Return string context from the knowledge base."""

    kb = _load()
    parts = []

    if kb["conventions"]:
        parts.append("=== KONVENSI PROJECT ===")
        for c in kb["conventions"][-max_items:]:
            parts.append(f"  • {c['desc']}")
        parts.append("")

    if kb["gotchas"]:
        parts.append("=== GOTCHAS (hal yang SERING bikin error) ===")
        for g in kb["gotchas"][-max_items:]:
            parts.append(f"  ⚠ {g['desc']}")
        parts.append("")

    if kb["patterns"]:
        parts.append("=== POLA KODE YANG DIKENAL ===")
        for p in kb["patterns"][-max_items:]:
            parts.append(f"  • {p['desc']}")
        parts.append("")

    if kb["files_map"]:
        parts.append("=== PETA FILE PENTING ===")
        for path, info in list(kb["files_map"].items())[-10:]:
            parts.append(f"  📄 {path}: {info['notes'][:120]}")
        parts.append("")

    return "\n".join(parts)
