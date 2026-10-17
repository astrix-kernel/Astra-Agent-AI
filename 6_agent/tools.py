import difflib as _difflib
import os
import re
from web_tools import web_search, browse_url
"""Tools agent — baca/tulis/edit/hapus + verifikasi + rollback."""
import shutil, subprocess, time
from pathlib import Path
from config import (
    ASTRIX_ROOT, TRASH_DIR, LOG_FILE, ALLOWED_COMMANDS,
    SELF_ROOT, SELF_EDIT_WHITELIST, SELF_EDIT_BLOCK,
    MAX_FILE_READ_BYTES, MAX_TOOL_RESULT_CHARS,
    WRITABLE_EXT, WRITABLE_NAMES, VERIFY_COMPILER,
)

def _emit(event_type, payload):
    """Event emitter untuk broadcast file change (opsional)."""
    try:
        import sys
        from pathlib import Path as _P
        web_dir = _P(__file__).parent.parent / "web"
        if str(web_dir) not in sys.path:
            sys.path.insert(0, str(web_dir))
        from server import broadcast
        broadcast({"kind": event_type, **payload}, event_type)
    except Exception:
        pass  # Gak ada server, skip aja


def log(msg):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

def safe_path(path):
    """Pastikan path ada di dalam ASTRIX_ROOT."""
    if not path:
        path = "."
    if path.startswith("/") or path.startswith("~"):
        raise PermissionError(f"Path absolut tidak diizinkan: {path}")
    full = (ASTRIX_ROOT / path).resolve()
    try:
        full.relative_to(ASTRIX_ROOT.resolve())
    except ValueError:
        raise PermissionError(f"Path keluar sandbox: {path}")
    return full

def _verify_syntax(path_obj):
    ext = path_obj.suffix
    if ext not in VERIFY_COMPILER:
        return True, "no verifier"
    cmd = VERIFY_COMPILER[ext] + [str(path_obj)]
    try:
        r = subprocess.run(cmd, cwd=ASTRIX_ROOT, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return True, "syntax OK"
        return False, (r.stderr or r.stdout)[:500]
    except subprocess.TimeoutExpired:
        return False, "verifikasi timeout"

# ============ TOOLS ============
# Semua pakai parameter `path` biar match dengan output LLM.

def list_dir(path="."):
    p = safe_path(path)
    if not p.is_dir():
        return f"ERROR: {path} bukan folder"
    lines = []
    for child in sorted(p.iterdir()):
        if child.name.startswith("."):
            continue
        # Skip backup folders
        if any(pat in child.name for pat in [".bak", ".backup-", ".old", ".corrupted", ".recovered"]):
            continue
        if child.is_dir():
            lines.append(f"  [dir]  {child.name}/")
        else:
            lines.append(f"  [file] {child.stat().st_size:>8}  {child.name}")
    return f"Isi {path}:\n" + "\n".join(lines) if lines else f"{path} kosong"

def read_file(path, offset=0, limit=0):
    """Baca file, optional offset & limit (lines)."""
    p = safe_path(path)
    if not p.is_file():
        return f"ERROR: {path} bukan file"
    size = p.stat().st_size
    if size > MAX_FILE_READ_BYTES:
        content = p.read_bytes()[:MAX_FILE_READ_BYTES].decode("utf-8", errors="replace")
        content += f"\n... [file {size} byte, kepotong di {MAX_FILE_READ_BYTES}]"
    else:
        content = p.read_text(errors="replace")
    
    if offset > 0 or limit > 0:
        lines = content.split("\n")
        total = len(lines)
        start = max(0, offset)
        end = total if limit == 0 else min(total, start + limit)
        sliced = lines[start:end]
        header = f"[Lines {start+1}-{end} of {total}]\n"
        return header + "\n".join(sliced)
    
    _mark_read(path); return content



def create_file(path, content):
    p = safe_path(path)
    if p.exists():
        # Kalau file sudah ada dan content > 0, izinkan overwrite (agent sering butuh ini)
        if content and len(content) > 50:
            p.write_text(content)
            log(f"OVERWRITE {path} ({len(content)}b)")
            return f"OK: {path} di-overwrite ({len(content)} bytes)"
        return f"ERROR: {path} sudah ada dan content kosong. Pakai replace_text atau write_file."
    if p.suffix not in WRITABLE_EXT and p.name not in WRITABLE_NAMES:
        return f"ERROR: extension {p.suffix} dilarang"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    log(f"CREATE {path} ({len(content)}b)")
    ok, msg = _verify_syntax(p)
    if not ok:
        p.unlink()
        log(f"ROLLBACK CREATE {path}: {msg}")
        return f"ERROR: syntax gagal, file dihapus.\n{msg}"
    return f"OK: {path} dibuat ({len(content)}b), {msg}"

def write_file(path, content):
    p = safe_path(path)
    old = p.read_text(errors="replace") if p.exists() else None
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    log(f"WRITE {path} ({len(content)}b)")
    ok, msg = _verify_syntax(p)
    if not ok:
        if old is None:
            p.unlink()
        else:
            p.write_text(old)
        log(f"ROLLBACK WRITE {path}: {msg}")
        return f"ERROR: syntax gagal, rollback.\n{msg}"
    return f"OK: {path} ditulis ({len(content)}b), {msg}"

def replace_text(path, old_text, new_text):
    p = safe_path(path)
    if not p.is_file():
        return f"ERROR: {path} tidak ada"
    current = p.read_text(errors="replace")
    n = current.count(old_text)
    if n == 0:
        return f"ERROR: teks tidak ada di {path}. Baca ulang file."
    if n > 1:
        return f"ERROR: teks muncul {n}x di {path}. Perlu konteks unik."
    new_content = current.replace(old_text, new_text, 1)
    p.write_text(new_content)
    log(f"REPLACE {path}")
    ok, msg = _verify_syntax(p)
    if not ok:
        p.write_text(current)
        log(f"ROLLBACK REPLACE {path}: {msg}")
        return f"ERROR: syntax gagal, rollback.\n{msg}"
    return f"OK: {path} diubah, {msg}"

def delete_file(path):
    p = safe_path(path)
    if not p.is_file():
        return f"ERROR: {path} tidak ada"
    TRASH_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    trashed = TRASH_DIR / f"{stamp}_{p.name}"
    shutil.move(str(p), str(trashed))
    log(f"DELETE {path} -> {trashed}")
    return f"OK: {path} dipindah ke trash"

def grep(pattern, path=".", max_hits=25):
    """Cari pattern (regex) di file/folder. Return: file:line: content."""
    import re as _re
    try:
        p = Path(path) if Path(path).is_absolute() else ASTRIX_ROOT / path
        if not p.exists():
            return f"ERROR: Path gak ada: {path}"

        try:
            regex = _re.compile(pattern)
        except _re.error as e:
            return f"ERROR regex '{pattern}': {e}"

        # Kumpulin file target
        files = []
        if p.is_file():
            files = [p]
        else:
            SKIP = {".git", "__pycache__", "node_modules", "build", "dist", "target", ".kilo", ".vscode"}
            for root, dirs, fnames in os.walk(p):
                dirs[:] = [d for d in dirs if d not in SKIP]
                for fn in fnames:
                    if fn.endswith((".c", ".h", ".S", ".asm", ".mk", ".py", ".sh", ".md", ".txt", ".json", ".toml", ".yaml", ".yml", "Makefile", "Kconfig")):
                        files.append(Path(root) / fn)

        hits = []
        for f in files[:500]:  # max 500 file
            try:
                for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if regex.search(line):
                        rel = f.relative_to(ASTRIX_ROOT) if (ASTRIX_ROOT) in f.parents else f
                        hits.append(f"{rel}:{i}: {line.strip()[:200]}")
                        if len(hits) >= max_hits:
                            break
            except Exception:
                pass
            if len(hits) >= max_hits:
                break

        if not hits:
            return f"Tidak ketemu pattern '{pattern}' di {path}"
        return "\n".join(hits)
    except Exception as e:
        return f"ERROR grep: {e}"



def run_command(cmd):
    parts = cmd.split()
    if not parts:
        return "ERROR: command kosong"
    if parts[0] not in ALLOWED_COMMANDS:
        return f"ERROR: '{parts[0]}' tidak diizinkan"
    try:
        r = subprocess.run(cmd, shell=True, cwd=ASTRIX_ROOT,
                           capture_output=True, text=True, timeout=60)
        return f"exit={r.returncode}\n{(r.stdout+r.stderr)[:MAX_TOOL_RESULT_CHARS]}"
    except subprocess.TimeoutExpired:
        return "ERROR: timeout 60s"


def build_project(target="build", jobs=4, timeout=180):
    """Jalankan make <target> -j<jobs>, return status + output ringkas."""
    cmd = f"make {target} -j{jobs}"
    try:
        r = subprocess.run(cmd, shell=True, cwd=ASTRIX_ROOT,
                           capture_output=True, text=True, timeout=timeout)
        out = (r.stdout + r.stderr)

        # Cari error line
        errors = [l for l in out.split("\n") if "error:" in l.lower() or "fatal error" in l.lower()]
        warnings = [l for l in out.split("\n") if "warning:" in l.lower()]

        # Cek hasil
        status = "SUCCESS" if r.returncode == 0 else "FAILED"

        # Cek BOOTX64.EFI
        boot_path = ASTRIX_ROOT / "BOOTX64.EFI"
        efi_exists = boot_path.exists()
        efi_size = boot_path.stat().st_size if efi_exists else 0

        summary = f"""BUILD {status} (exit={r.returncode})
Command: {cmd}
Errors: {len(errors)}, Warnings: {len(warnings)}
BOOTX64.EFI: {'ADA ' + str(efi_size) + ' bytes' if efi_exists else 'TIDAK ADA'}"""

        if errors:
            summary += "\n\n=== ERRORS (max 10) ===\n" + "\n".join(errors[:10])
        if warnings and len(warnings) <= 5:
            summary += "\n\n=== WARNINGS ===\n" + "\n".join(warnings[:5])

        # Tail output kalau sukses
        if r.returncode == 0:
            tail = "\n".join(out.split("\n")[-10:])
            summary += f"\n\n=== TAIL OUTPUT ===\n{tail}"

        return summary[:MAX_TOOL_RESULT_CHARS]
    except subprocess.TimeoutExpired:
        return f"BUILD TIMEOUT setelah {timeout}s"
    except Exception as e:
        return f"BUILD ERROR: {e}"



def run_tests_tool():
    """Jalanin test suite project."""
    from test_runner import run_tests, format_report
    result = run_tests()
    return format_report(result)


def detect_tests_tool():
    """Cek apakah project punya test."""
    from test_runner import detect_test_command
    cmd, desc = detect_test_command()
    if cmd:
        return f"Ada test: {cmd} ({desc})"
    return "Nggak ada test command terdeteksi"



# ============ TOOLS BARU — File manipulation ============

def append_to_file(path, content):
    """Nambah content ke AKHIR file."""
    p = safe_path(path)
    if not p.exists():
        return f"ERROR: {path} nggak ada (pakai create_file)"
    if p.suffix not in WRITABLE_EXT and p.name not in WRITABLE_NAMES:
        return f"ERROR: extension {p.suffix} dilarang"
    old = p.read_text(errors="replace")
    new = old + content
    p.write_text(new)
    log(f"APPEND {path} ({len(content)}b)")
    ok, msg = _verify_syntax(p)
    if not ok:
        p.write_text(old)  # rollback
        log(f"ROLLBACK APPEND {path}: {msg}")
        return f"ERROR: syntax gagal, rollback.\n{msg}"
    return f"OK: append {len(content)}b ke {path}, {msg}"


def insert_at_line(path, line_num, content):
    """Insert content di line_num (1-indexed)."""
    p = safe_path(path)
    if not p.is_file():
        return f"ERROR: {path} nggak ada"
    old = p.read_text(errors="replace")
    lines = old.split("\n")
    if line_num < 1 or line_num > len(lines) + 1:
        return f"ERROR: line_num harus 1-{len(lines) + 1}, dikasih {line_num}"
    # Insert content (bisa multiple lines)
    new_lines = content.split("\n")
    lines[line_num - 1:line_num - 1] = new_lines
    new = "\n".join(lines)
    p.write_text(new)
    log(f"INSERT {path}@line{line_num}")
    ok, msg = _verify_syntax(p)
    if not ok:
        p.write_text(old)
        log(f"ROLLBACK INSERT {path}: {msg}")
        return f"ERROR: syntax gagal, rollback.\n{msg}"
    return f"OK: insert {len(new_lines)} baris di line {line_num}, {msg}"


def delete_lines(path, start_line, end_line=None):
    """Hapus baris start_line..end_line (1-indexed, inclusive)."""
    p = safe_path(path)
    if not p.is_file():
        return f"ERROR: {path} nggak ada"
    old = p.read_text(errors="replace")
    lines = old.split("\n")
    end_line = end_line or start_line
    if start_line < 1 or end_line > len(lines) or start_line > end_line:
        return f"ERROR: range salah. File punya {len(lines)} baris"
    del lines[start_line - 1:end_line]
    new = "\n".join(lines)
    p.write_text(new)
    log(f"DELETE_LINES {path} {start_line}-{end_line}")
    ok, msg = _verify_syntax(p)
    if not ok:
        p.write_text(old)
        log(f"ROLLBACK DELETE_LINES {path}: {msg}")
        return f"ERROR: syntax gagal, rollback.\n{msg}"
    return f"OK: hapus baris {start_line}-{end_line} ({end_line - start_line + 1} baris), {msg}"


def create_directory(path):
    """Bikin folder baru (bisa nested)."""
    p = safe_path(path)
    if p.exists() and p.is_dir():
        return f"OK: {path} udah ada"
    if p.exists():
        return f"ERROR: {path} udah ada tapi itu file"
    p.mkdir(parents=True, exist_ok=True)
    log(f"MKDIR {path}")
    return f"OK: folder {path} dibuat"


def rename_file(old_path, new_path):
    """Rename / pindah file."""
    import shutil
    src = safe_path(old_path)
    dst = safe_path(new_path)
    if not src.is_file():
        return f"ERROR: {old_path} nggak ada"
    if dst.exists():
        return f"ERROR: {new_path} udah ada"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    log(f"RENAME {old_path} -> {new_path}")
    return f"OK: {old_path} → {new_path}"


def read_lines(path, start=1, end=None, default_span=200):
    """Baca range baris. Format output: [LINES X-Y of N] + numbered lines."""
    try:
        p = Path(path) if Path(path).is_absolute() else ASTRIX_ROOT / path
        if not p.exists():
            return f"ERROR: File gak ada: {path}"
        try:
            _mark_read(path)
        except Exception:
            pass

        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        total = len(lines)

        try:
            start = max(1, int(start) if start else 1)
        except Exception:
            start = 1

        if end is None:
            end = start + default_span - 1
        try:
            end = int(end)
        except Exception:
            end = start + default_span - 1

        if end <= start:
            end = start + default_span - 1
        end = min(end, total)

        selected = lines[start-1:end]
        header = f"[LINES {start}-{end} of {total}]\n"
        numbered = "\n".join(f"{start+i:>5}: {l}" for i, l in enumerate(selected))
        return header + numbered
    except Exception as e:
        return f"ERROR read_lines: {e}"



def _diff_count(old, new):
    old_l = (old or "").splitlines()
    new_l = (new or "").splitlines()
    d = list(_difflib.unified_diff(old_l, new_l, lineterm=""))
    a = sum(1 for l in d if l.startswith("+") and not l.startswith("+++"))
    r = sum(1 for l in d if l.startswith("-") and not l.startswith("---"))
    return a, r


_create_orig = create_file
_write_orig = write_file
_replace_orig = replace_text
_delete_orig = delete_file


def create_file(path, content):
    r = _create_orig(path, content)
    if r.startswith("OK"):
        a, _ = _diff_count("", content)
        _emit("file_change", {"path": str(path), "action": "create", "added": a, "removed": 0})
    return r


def write_file(path, content):
    try:
        pp = safe_path(path)
        old = pp.read_text(errors="replace") if pp.exists() else ""
    except Exception:
        old = ""
    r = _write_orig(path, content)
    if r.startswith("OK"):
        a, d = _diff_count(old, content)
        _emit("file_change", {"path": str(path), "action": "write", "added": a, "removed": d})
    return r


def replace_text(path, old_text, new_text):
    r = _replace_orig(path, old_text, new_text)
    if r.startswith("OK"):
        a, d = _diff_count(old_text, new_text)
        _emit("file_change", {"path": str(path), "action": "replace", "added": a, "removed": d})
    return r


def delete_file(path):
    try:
        pp = safe_path(path)
        old = pp.read_text(errors="replace") if pp.is_file() else ""
    except Exception:
        old = ""
    r = _delete_orig(path)
    if r.startswith("OK"):
        lines = len(old.splitlines())
        _emit("file_change", {"path": str(path), "action": "delete", "added": 0, "removed": lines})
    return r


# ============ TOOLS REGISTRY ============
# === SELF-EDIT TOOLS (agent edit dirinya sendiri) ===

def _check_self_path(path):
    """Validasi path self-edit: harus di whitelist, bukan di block."""
    from config import SELF_ROOT, SELF_EDIT_WHITELIST, SELF_EDIT_BLOCK
    path = str(path).strip()
    if path.startswith("/") or path.startswith("~"):
        raise PermissionError(f"Path absolut gak boleh: {path}")
    for blocked in SELF_EDIT_BLOCK:
        if path.startswith(blocked):
            raise PermissionError(f"File '{blocked}' DIBLOK. Edit manual dari terminal.")
    allowed = False
    for wl in SELF_EDIT_WHITELIST:
        if path.startswith(wl):
            allowed = True
            break
    if not allowed:
        raise PermissionError(f"File '{path}' gak ada di whitelist self-edit.")
    full = (SELF_ROOT / path).resolve()
    try:
        full.relative_to(SELF_ROOT.resolve())
    except ValueError:
        raise PermissionError(f"Path keluar SELF_ROOT: {path}")
    return full


def self_read(path):
    """Baca file astrix-ai buat self-edit."""
    try:
        full = _check_self_path(path)
        if not full.exists():
            return f"ERROR: File gak ada: {path}"
        content = full.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        return f"[SELF: {path}] ({len(lines)} lines)\\n" + "\n".join(f"{i:>4}: {l}" for i, l in enumerate(lines[:200], 1))
    except PermissionError as e:
        return f"ERROR: {e}"
    except Exception as e:
        return f"ERROR self_read: {e}"


def self_replace(path, old_text, new_text):
    """Replace dengan backup + syntax check + rollback."""
    import shutil, time as _t, subprocess
    from config import SELF_ROOT
    try:
        full = _check_self_path(path)
        if not full.exists():
            return f"ERROR: File gak ada: {path}"
        original = full.read_text(encoding="utf-8")
        if old_text not in original:
            return f"ERROR: old_text gak ketemu di {path}"
        bak = full.with_suffix(full.suffix + f".bak.{int(_t.time())}")
        shutil.copy2(full, bak)
        new_content = original.replace(old_text, new_text, 1)
        full.write_text(new_content, encoding="utf-8")
        if str(full).endswith(".py"):
            r = subprocess.run(["python3", "-c", f"import ast; ast.parse(open('{full}').read())"],
                              capture_output=True, text=True, timeout=10)
            if r.returncode != 0:
                shutil.copy2(bak, full)
                return f"SYNTAX ERROR - rollback. {r.stderr[:400]}"
        try:
            subprocess.run(["git", "add", str(full)], cwd=str(SELF_ROOT), capture_output=True, timeout=10)
            subprocess.run(["git", "commit", "-m", f"self-edit: {path}", "--no-verify"],
                          cwd=str(SELF_ROOT), capture_output=True, timeout=10)
        except Exception:
            pass
        added = new_content.count("\n") - original.count("\n")
        return f"OK: {path} diedit ({added:+d} lines). Backup: {bak.name}"
    except PermissionError as e:
        return f"ERROR: {e}"
    except Exception as e:
        return f"ERROR self_replace: {e}"


def self_write(path, content):
    """Tulis file astrix-ai baru dengan safety."""
    import shutil, time as _t, subprocess
    from config import SELF_ROOT
    try:
        full = _check_self_path(path)
        bak = None
        if full.exists():
            bak = full.with_suffix(full.suffix + f".bak.{int(_t.time())}")
            shutil.copy2(full, bak)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        if str(full).endswith(".py"):
            r = subprocess.run(["python3", "-c", f"import ast; ast.parse(open('{full}').read())"],
                              capture_output=True, text=True, timeout=10)
            if r.returncode != 0:
                if bak: shutil.copy2(bak, full)
                return f"SYNTAX ERROR - {r.stderr[:400]}"
        return f"OK: {path} ditulis ({len(content)} bytes)"
    except PermissionError as e:
        return f"ERROR: {e}"
    except Exception as e:
        return f"ERROR self_write: {e}"


def self_restart(delay=15):
    """Schedule restart service (async)."""
    import subprocess
    try:
        cmd = f"sleep {delay} && systemctl --user restart astrix-web.service"
        subprocess.Popen(["bash", "-c", cmd], start_new_session=True)
        return f"OK: Restart dijadwalkan dalam {delay}s. Selesaikan respons."
    except Exception as e:
        return f"ERROR self_restart: {e}"


def self_status():
    """Cek git log + whitelist."""
    import subprocess
    from config import SELF_ROOT, SELF_EDIT_WHITELIST
    try:
        r = subprocess.run(["git", "log", "--oneline", "-5"],
                          cwd=str(SELF_ROOT), capture_output=True, text=True, timeout=5)
        return f"Git log:\n{r.stdout}\nWhitelist:\n" + "\n".join(f"- {w}" for w in SELF_EDIT_WHITELIST)
    except Exception as e:
        return f"ERROR: {e}"






# === SELF-EDIT TOOLS REGISTRATION ===






# === TOOL GUARD: track file yang udah dibaca di sesi ini ===
_read_files = set()
_edited_files = set()

def _mark_read(path):
    _read_files.add(str(path))

def _mark_edited(path):
    _edited_files.add(str(path))

def was_read(path):
    return str(path) in _read_files

def reset_guard():
    _read_files.clear()
    _edited_files.clear()

def guard_replace_text(path, old_text, new_text):
    """Cek: harus baca file dulu sebelum edit + auto build verify."""
    if not was_read(path):
        return f"❌ ERROR: File `{path}` belum dibaca di sesi ini. Panggil `read_file` dulu sebelum edit.\n\nTool call: read_file(path='{path}')"
    result = replace_text(path, old_text, new_text)

    # Auto-verify syntax kalau .c/.h
    if str(path).endswith((".c", ".h")) and "ERROR" not in str(result):
        try:
            verify = _verify_syntax(Path(path))
            if verify and "error" in str(verify).lower():
                result += f"\n\n⚠️ SYNTAX ERROR terdeteksi setelah edit:\n{verify[:300]}"
        except Exception:
            pass

    # Auto-checkpoint tiap 5 edit
    try:
        from auto_checkpoint import maybe_checkpoint
        maybe_checkpoint()
    except Exception:
        pass

    return result

def guard_delete_lines(path, start_line, end_line=None):
    if not was_read(path):
        return f"❌ ERROR: File `{path}` belum dibaca. Panggil `read_file` dulu."
    return delete_lines(path, start_line, end_line)

def guard_insert_at_line(path, line_num, content):
    if not was_read(path):
        return f"❌ ERROR: File `{path}` belum dibaca. Panggil `read_file` dulu."
    return insert_at_line(path, line_num, content)


# ==========================================
# PATCH: WEB SEARCH & BROWSE TOOL
# ==========================================
import urllib.parse
import urllib.request
import re
import json



TOOLS = {
    "web_search": web_search,
    "browse_url": browse_url,
    "list_dir": list_dir,
    "read_file": read_file,
    "create_file": create_file,
    "write_file": write_file,
    "replace_text": replace_text,
    "delete_file": delete_file,
    "grep": grep,
    "run_command": run_command,
    "build_project": build_project,
    "run_tests_tool": run_tests_tool,
    "detect_tests_tool": detect_tests_tool,
    "append_to_file": append_to_file,
    "insert_at_line": insert_at_line,
    "delete_lines": delete_lines,
    "create_directory": create_directory,
    "rename_file": rename_file,
    "read_lines": read_lines,
    "self_read": self_read,
    "self_replace": self_replace,
    "self_write": self_write,
    "self_restart": self_restart,
    "self_status": self_status,
    "was_read": was_read,
    "reset_guard": reset_guard,
    "guard_replace_text": guard_replace_text,
    "guard_delete_lines": guard_delete_lines,
    "guard_insert_at_line": guard_insert_at_line,
}

# === Browser Tools ===
try:
    from browser_agent import BROWSER_TOOLS
    TOOLS.update(BROWSER_TOOLS)
except Exception as _e:
    print(f'[BROWSER] not loaded: {_e}')
