import difflib as _difflib
import os
import re
from web_tools import web_search, browse_url
"""Tools agent — read/write/edit/delete + verification + rollback."""

import shutil, subprocess, time
from pathlib import Path
import config
from config import (
    ASTRIX_ROOT, TRASH_DIR, LOG_FILE, ALLOWED_COMMANDS,
    SELF_ROOT, SELF_EDIT_WHITELIST, SELF_EDIT_BLOCK,
    MAX_FILE_READ_BYTES, MAX_TOOL_RESULT_CHARS,
    WRITABLE_EXT, WRITABLE_NAMES, VERIFY_COMPILER,
)

def _emit(event_type, payload):
    """Event emitter for broadcast file change (optional)."""

    try:
        import sys
        from pathlib import Path as _P
        web_dir = _P(__file__).parent.parent / "web"
        if str(web_dir) not in sys.path:
            sys.path.insert(0, str(web_dir))
        from server import broadcast
        broadcast({"kind": event_type, **payload}, event_type)
    except Exception:
        pass 


def log(msg):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

def safe_path(path):
    """Make sure the path is inside astrix_root."""

    if not path:
        path = "."
    # Handle ~ expansion
    if path.startswith("~"):
        path = str(Path(path).expanduser())
    # Izinkan absolute path JIKA di dalam workspace
    if path.startswith("/"):
        full = Path(path).resolve()
        try:
            full.relative_to(config.WORKSPACE.resolve())
            return full
        except ValueError:
            raise PermissionError(f"Path absolut di luar workspace: {path}")
    full = (config.WORKSPACE / path).resolve()
    try:
        full.relative_to(config.WORKSPACE.resolve())
    except ValueError:
        raise PermissionError(f"Path keluar sandbox: {path}")
    return full

def _verify_syntax(path_obj):
    ext = path_obj.suffix
    if ext not in VERIFY_COMPILER:
        return True, "no verifier"
    cmd = list(VERIFY_COMPILER[ext])
    # === ASTRIX PATCH: include paths untuk kode kernel C/C++ ===
    # cwd = config.WORKSPACE, jadi cukup pakai relative path.
    if ext in (".S", ".s", ".asm"):
        try:
            asm_cmd = ["gcc", "-fsyntax-only", "-x", "assembler-with-cpp", str(path_obj)] if ext != ".asm" else ["nasm", "-f", "elf64", str(path_obj), "-o", "/dev/null"]
            r = subprocess.run(asm_cmd, cwd=str(config.WORKSPACE),
                               capture_output=True, text=True, timeout=30)
            return (r.returncode == 0, "syntax OK" if r.returncode == 0 else (r.stderr or r.stdout)[:500])
        except FileNotFoundError:
            return True, "assembler not installed, skipped"
        except Exception as e:
            return False, f"assembler error: {e}"
    if ext in (".c", ".h", ".cpp"):
        cmd += ["-ffreestanding", "-std=gnu11"]
        # Auto-detect include paths: scan semua subdir dari workspace
        try:
            import os as _os
            from pathlib import Path as _P
            _ws = _P(str(config.WORKSPACE))
            _included = set()
            # Selalu tambah root
            cmd.append(f"-I{_ws}")
            # Scan subdir (kedalaman max 3 untuk performa)
            for _root, _dirs, _fs in _os.walk(str(_ws)):
                _rel = _os.path.relpath(_root, str(_ws))
                if _rel == '.': continue
                # Skip build/cache dirs
                if any(x in _rel.lower() for x in ['.git','node_modules','__pycache__','.venv','venv','build/','bin/','dist/','target/']):
                    continue
                _depth = _rel.count(_os.sep) + 1
                if _depth > 3: continue
                if _rel not in _included:
                    cmd.append(f"-I{_root}")
                    _included.add(_rel)
        except Exception:
            pass
    cmd.append(str(path_obj))
    # === END PATCH ===
    try:
        r = subprocess.run(cmd, cwd=str(config.WORKSPACE), capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return True, "syntax OK"
        return False, (r.stderr or r.stdout)[:500]
    except subprocess.TimeoutExpired:
        return False, "verifikasi timeout"


def list_dir(path="."):
    p = safe_path(path)
    if not p.is_dir():
        return f"ERROR: {path} bukan folder"
    lines = []
    for child in sorted(p.iterdir()):
        if child.name.startswith("."):
            continue
        if any(pat in child.name for pat in [".bak", ".backup-", ".old", ".corrupted", ".recovered"]):
            continue
        if child.is_dir():
            lines.append(f"  [dir]  {child.name}/")
        else:
            lines.append(f"  [file] {child.stat().st_size:>8}  {child.name}")
    return f"Isi {path}:\n" + "\n".join(lines) if lines else f"{path} kosong"

def read_file(path, offset=0, limit=0):
    """Read the file, optional offset & limit (lines)."""

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
    """Look for patterns (regex) in files/folders. Return: file: line: content."""

    import re as _re
    try:
        p = Path(path) if Path(path).is_absolute() else ASTRIX_ROOT / path
        if not p.exists():
            return f"ERROR: Path gak ada: {path}"

        try:
            regex = _re.compile(pattern)
        except _re.error as e:
            return f"ERROR regex '{pattern}': {e}"

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
        for f in files[:500]: 
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



def run_command(cmd=None, command=None):
    cmd = cmd or command
    parts = cmd.split()
    if not parts:
        return "ERROR: command kosong"
    if parts[0] not in ALLOWED_COMMANDS:
        return f"ERROR: '{parts[0]}' tidak diizinkan"
    try:
        r = subprocess.run(cmd, shell=True, cwd=str(config.WORKSPACE),
                           capture_output=True, text=True, timeout=60)
        return f"exit={r.returncode}\n{(r.stdout+r.stderr)[:MAX_TOOL_RESULT_CHARS]}"
    except subprocess.TimeoutExpired:
        return "ERROR: timeout 60s"


def build_project(target="build", jobs=4, timeout=180):
    """Run make <target> -j<jobs>, return status + output concise."""

    cmd = f"make {target} -j{jobs}"
    try:
        r = subprocess.run(cmd, shell=True, cwd=str(config.WORKSPACE),
                           capture_output=True, text=True, timeout=timeout)
        out = (r.stdout + r.stderr)

        errors = [l for l in out.split("\n") if "error:" in l.lower() or "fatal error" in l.lower()]
        warnings = [l for l in out.split("\n") if "warning:" in l.lower()]

        status = "SUCCESS" if r.returncode == 0 else "FAILED"

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
    """Check whether the project has a test."""

    from test_runner import detect_test_command
    cmd, desc = detect_test_command()
    if cmd:
        return f"Ada test: {cmd} ({desc})"
    return "Nggak ada test command terdeteksi"




def append_to_file(path, content):
    """Add content to the END OF THE file."""

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
        p.write_text(old) 
        log(f"ROLLBACK APPEND {path}: {msg}")
        return f"ERROR: syntax gagal, rollback.\n{msg}"
    return f"OK: append {len(content)}b ke {path}, {msg}"


def insert_at_line(path, line_num, content):
    """Insert content in line_num (1-indexed)."""

    p = safe_path(path)
    if not p.is_file():
        return f"ERROR: {path} nggak ada"
    old = p.read_text(errors="replace")
    lines = old.split("\n")
    if line_num < 1 or line_num > len(lines) + 1:
        return f"ERROR: line_num harus 1-{len(lines) + 1}, dikasih {line_num}"
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
    """Delete line start_line.. end_line (1-indexed, inclusive)."""

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
    """Create a new folder (can be nested)."""

    p = safe_path(path)
    if p.exists() and p.is_dir():
        return f"OK: {path} udah ada"
    if p.exists():
        return f"ERROR: {path} udah ada tapi itu file"
    p.mkdir(parents=True, exist_ok=True)
    log(f"MKDIR {path}")
    return f"OK: folder {path} dibuat"


def rename_file(old_path, new_path):
    """Rename / move files."""

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


def read_lines(path, start=1, end=None, default_span=200, start_line=None, end_line=None):
    # Aliases: LLM kadang manggil start_line/end_line
    if start_line is not None: start = start_line
    if end_line is not None: end = end_line
    """Read line range. Output format: [LINES X-Y of N] + numbered lines."""

    try:
        p = safe_path(path)  # safe_path handles both relative (→WORKSPACE) and absolute
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



def _check_self_path(path):
    """Validate self-edit path: should be whitelisted, not blocked."""

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
    """Read theastrix-ai file for self-editing."""

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
    """Replace with backup + syntax check + rollback."""

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
    """Write a new astrix-ai file with safety."""

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
    """Check git log + whitelist."""

    import subprocess
    from config import SELF_ROOT, SELF_EDIT_WHITELIST
    try:
        r = subprocess.run(["git", "log", "--oneline", "-5"],
                          cwd=str(SELF_ROOT), capture_output=True, text=True, timeout=5)
        return f"Git log:\n{r.stdout}\nWhitelist:\n" + "\n".join(f"- {w}" for w in SELF_EDIT_WHITELIST)
    except Exception as e:
        return f"ERROR: {e}"












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
    """Check: you must read the file first before editing + auto build verify."""

    if not was_read(path):
        return f"❌ ERROR: File `{path}` belum dibaca di sesi ini. Panggil `read_file` dulu sebelum edit.\n\nTool call: read_file(path='{path}')"
    result = replace_text(path, old_text, new_text)

    if str(path).endswith((".c", ".h")) and "ERROR" not in str(result):
        try:
            verify = _verify_syntax(Path(path))
            if verify and "error" in str(verify).lower():
                result += f"\n\n⚠️ SYNTAX ERROR terdeteksi setelah edit:\n{verify[:300]}"
        except Exception:
            pass

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


import urllib.parse
import urllib.request
import re
import json





# (browser tools attach dipindah ke akhir file)


# ============ NEW TOOLS ============

def search_text(pattern, path=".", include="*.c,*.h", max_results=50):
    """Cari regex pattern di file matching include glob."""
    import re as _re
    p = safe_path(path)
    if not p.exists():
        return f"ERROR: {path} tidak ada"
    includes = [x.strip() for x in include.split(",") if x.strip()]
    results = []
    try:
        regex = _re.compile(pattern)
    except _re.error as e:
        return f"ERROR: regex invalid: {e}"
    for inc in includes:
        for f in p.rglob(inc):
            if not f.is_file(): continue
            try:
                for i, line in enumerate(f.read_text(errors="replace").split("\n"), 1):
                    if regex.search(line):
                        results.append(f"{f.relative_to(p)}:{i}: {line[:200]}")
                        if len(results) >= max_results: break
            except Exception:
                continue
            if len(results) >= max_results: break
    if not results:
        return f"OK: tidak ada hasil untuk '{pattern}'"
    return f"Found {len(results)} match:\n" + "\n".join(results)


def find_files(pattern, path=".", max_results=100):
    """Cari file by glob pattern (e.g. '*.c', '**/*.h')."""
    p = safe_path(path)
    if not p.exists():
        return f"ERROR: {path} tidak ada"
    results = []
    for f in p.rglob(pattern):
        if f.is_file():
            results.append(str(f.relative_to(p)))
            if len(results) >= max_results: break
    if not results:
        return f"OK: tidak ada file match '{pattern}'"
    return f"Found {len(results)} files:\n" + "\n".join(results)


def multi_write(files):
    """Tulis BANYAK file sekaligus. files = [{"path": "...", "content": "..."}]"""
    if not isinstance(files, list):
        return "ERROR: files harus list of {path, content}"
    results = []
    for entry in files:
        if not isinstance(entry, dict):
            results.append("SKIP: bukan dict")
            continue
        pth = entry.get("path", "")
        cnt = entry.get("content", "")
        if not pth:
            results.append("SKIP: path kosong")
            continue
        try:
            r = write_file(pth, cnt)
            results.append(f"{pth}: {r[:120]}")
        except Exception as e:
            results.append(f"{pth}: ERROR {e}")
    return "\n".join(results)


def rename_file(old_path, new_path):
    """Rename atau move file."""
    p = safe_path(old_path)
    q = safe_path(new_path)
    if not p.exists():
        return f"ERROR: {old_path} tidak ada"
    if q.exists():
        return f"ERROR: {new_path} sudah ada"
    q.parent.mkdir(parents=True, exist_ok=True)
    p.rename(q)
    log(f"RENAME {old_path} -> {new_path}")
    return f"OK: {old_path} -> {new_path}"


def copy_file(src, dst):
    """Copy file."""
    import shutil as _sh
    p = safe_path(src)
    q = safe_path(dst)
    if not p.exists():
        return f"ERROR: {src} tidak ada"
    q.parent.mkdir(parents=True, exist_ok=True)
    _sh.copy2(p, q)
    log(f"COPY {src} -> {dst}")
    return f"OK: {src} -> {dst}"


def git_status():
    """Show git status short."""
    import subprocess as _sp
    try:
        r = _sp.run(["git", "status", "--short"], cwd=str(config.WORKSPACE),
                    capture_output=True, text=True, timeout=10)
        return r.stdout or "(clean)"
    except Exception as e:
        return f"ERROR: {e}"


def git_diff(path=""):
    """Show git diff."""
    import subprocess as _sp
    try:
        cmd = ["git", "diff"]
        if path: cmd.append(path)
        r = _sp.run(cmd, cwd=str(config.WORKSPACE),
                    capture_output=True, text=True, timeout=10)
        return (r.stdout or "(no diff)")[:3000]
    except Exception as e:
        return f"ERROR: {e}"

# ============ END NEW TOOLS ============


# ============ TOOLS DICT (dipindah ke akhir agar fungsi terdefinisi dulu) ============
# ============ NEW TOOLS (moved before TOOLS dict) ============

def multi_edit(edits):
    """Batch replace_text. edits = [{"path": "...", "old": "...", "new": "..."}, ...]"""
    if not isinstance(edits, list):
        return "ERROR: edits harus list of {path, old, new}"
    results = []
    for e in edits:
        if not isinstance(e, dict):
            results.append("SKIP: bukan dict")
            continue
        pth = e.get("path", "")
        old = e.get("old", "")
        new = e.get("new", "")
        if not pth or not old:
            results.append(f"SKIP: {pth} - path/old kosong")
            continue
        try:
            r = replace_text(pth, old, new)
            results.append(f"{pth}: {r[:100]}")
        except Exception as ex:
            results.append(f"{pth}: ERROR {ex}")
    return "\n".join(results)


def analyze_workspace(keyword, max_files=15, preview_lines=30):
    """Cari file by keyword, baca preview. Return struktur ringkas."""
    import os as _os
    from pathlib import Path as _P
    ws = _P(str(config.WORKSPACE))
    if not ws.exists():
        return f"ERROR: workspace {ws} tidak ada"

    # Cari dir yang match keyword
    matches = []
    for _root, _dirs, _fs in _os.walk(str(ws)):
        rl = _root.lower()
        if any(x in rl for x in ['/.git','/node_modules','/venv','/__pycache__']):
            continue
        for _fn in _fs:
            if _fn.endswith(('.c','.h','.cpp','.S','.asm','.rs','.go','.py','.js','.ts','.mk','.make')) or _fn in ('Makefile','CMakeLists.txt'):
                if keyword.lower() in _root.lower() or keyword.lower() in _fn.lower():
                    rel = _os.path.relpath(_os.path.join(_root, _fn), str(ws))
                    matches.append(rel)
            if len(matches) >= max_files:
                break
        if len(matches) >= max_files:
            break

    if not matches:
        return f"OK: tidak ada file match '{keyword}'"

    out = [f"Found {len(matches)} files matching '{keyword}':\n"]
    for rel in matches[:max_files]:
        out.append(f"\n{'='*60}\n{rel}\n{'='*60}")
        try:
            p = ws / rel
            lines = p.read_text(errors='replace').split('\n')
            # Preview: 10 baris awal + signature functions
            preview = lines[:preview_lines]
            out.append("\n".join(preview))
            # Cari fungsi
            funcs = [l.strip() for l in lines if ('def ' in l or 'int ' in l or 'void ' in l or 'fn ' in l) and '(' in l][:5]
            if funcs:
                out.append(f"\n... functions: {', '.join(f[:50] for f in funcs)}")
        except Exception as e:
            out.append(f"ERROR reading: {e}")
    return "\n".join(out)

# ============ END NEW TOOLS ============


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
    "search_text": search_text,
    "find_files": find_files,
    "multi_write": multi_write,
    "copy_file": copy_file,
    "git_status": git_status,
    "git_diff": git_diff,
    "multi_edit": multi_edit,
    "analyze_workspace": analyze_workspace,
}

# === Browser tools attach (HARUS setelah TOOLS didefinisikan) ===
try:
    from browser_agent import BROWSER_TOOLS
    TOOLS.update(BROWSER_TOOLS)
except Exception as _e:
    print(f'[BROWSER] not loaded: {_e}')
