"""Smart Context Builder — auto-find relevant files for the task."""

import re
from pathlib import Path
from config import ASTRIX_ROOT


STOP_WORDS = {"yang", "untuk", "dengan", "atau", "dan", "di", "ke", "dari",
              "bikin", "buat", "task", "file", "the", "a", "an", "to", "for",
              "with", "and", "or", "from", "buat", "bikin", "baca", "tulis",
              "update", "fix", "perbaiki", "tambah", "ganti", "ubah", "hapus"}


def _keywords(text):
    """Extract important keywords from the task description."""

    words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]{2,}', text.lower())
    kws = set()
    for w in words:
        if w not in STOP_WORDS and len(w) >= 3:
            kws.add(w)
    for m in re.findall(r'[\w/]+\.(c|h|s|asm|ld|mk)', text):
        kws.add(m)
    return kws


def find_relevant_files(task_desc, max_files=5, max_chars_per_file=3000):
    """
    Cari file yang relevan dengan task.
    Strategi: keyword matching di nama file + isi file.
    """
    kws = _keywords(task_desc)
    if not kws:
        return []

    root = ASTRIX_ROOT
    scored = [] 

    valid_ext = {".c", ".h", ".S", ".s", ".asm", ".ld", ".lds", ".mk"}
    valid_names = {"Makefile", "Kconfig", "Kbuild"}

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in valid_ext and p.name not in valid_names:
            continue
        if any(skip in str(p) for skip in [".git", "build/", "__pycache__", ".kilo", ".bak", ".backup-", ".old"]):
            continue

        name_lower = p.name.lower()
        score = 0
        for kw in kws:
            if kw in name_lower:
                score += 5
            if kw in str(p.relative_to(root)).lower():
                score += 2

        if score == 0:
            try:
                if p.stat().st_size > 100_000:
                    continue
                content = p.read_text(errors="ignore")[:5000].lower()
                for kw in kws:
                    if kw in content:
                        score += 1
            except Exception:
                continue

        if score > 0:
            scored.append((score, p))

    scored.sort(reverse=True)
    top = scored[:max_files]

    result = []
    for score, p in top:
        try:
            content = p.read_text(errors="ignore")
            if len(content) > max_chars_per_file:
                content = content[:max_chars_per_file] + f"\n... [{len(content)-max_chars_per_file} char lagi]"
            rel = str(p.relative_to(ASTRIX_ROOT))
            result.append({"path": rel, "score": score, "content": content})
        except Exception:
            continue

    return result


def build_context_block(task_desc, max_files=5):
    """The context return string is ready to be injected into the prompt."""

    files = find_relevant_files(task_desc, max_files=max_files)
    if not files:
        return ""

    lines = ["=== FILE RELEVAN (dari pencarian otomatis) ===\n"]
    for f in files:
        lines.append(f"\n--- {f['path']} (score: {f['score']}) ---\n")
        lines.append(f["content"])
        lines.append("\n")
    return "".join(lines)


def get_project_tree(max_depth=2, max_files_per_dir=15):
    """Summary of the project structure."""

    root = ASTRIX_ROOT
    lines = []

    def walk(path, depth):
        if depth > max_depth:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        except Exception:
            return
        count = 0
        for e in entries:
            if e.name.startswith(".") or e.name in ("build", "__pycache__", "node_modules"):
                continue
            count += 1
            if count > max_files_per_dir:
                lines.append(f"{'  ' * depth}... ({len(entries)-count+1} lagi)")
                break
            rel = e.relative_to(root)
            if e.is_dir():
                lines.append(f"{'  ' * depth}📁 {e.name}/")
                walk(e, depth + 1)
            else:
                lines.append(f"{'  ' * depth}📄 {rel}")

    walk(root, 0)
    return "\n".join(lines[:200]) 
