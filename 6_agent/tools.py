import difflib as _difflib
import os
import re
from web_tools import web_search, browse_url
"""Tools agent — read/write/edit/delete + verification + rollback."""

import shutil, subprocess, time
from pathlib import Path
import config
from config import (
    LOG_FILE, ALLOWED_COMMANDS,
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
    """Make sure the path is inside the active workspace."""

    if not path:
        path = "."
    # Handle ~ expansion
    if path.startswith("~"):
        path = str(Path(path).expanduser())
    # Izinkan absolute path JIKA di dalam workspace
    if path.startswith("/"):
        full = Path(path).resolve()
        try:
            full.relative_to(config.get_workspace().resolve())
            return full
        except ValueError:
            raise PermissionError(f"Path absolut di luar workspace: {path}")
    full = (config.get_workspace() / path).resolve()
    try:
        full.relative_to(config.get_workspace().resolve())
    except ValueError:
        raise PermissionError(f"Path keluar sandbox: {path}")
    return full

def _verify_syntax(path_obj):
    ext = path_obj.suffix
    file_path = str(path_obj.resolve())
    cwd = str(config.get_workspace())

    # Validators for languages and data formats that do not use
    # the legacy VERIFY_COMPILER command table.
    import tempfile

    def run_check(cmd, label, timeout=30):
        try:
            r = subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True,
                timeout=timeout
            )
            if r.returncode == 0:
                return True, f"{label}: valid"
            detail = (r.stderr or r.stdout or "validator failed").strip()
            return False, f"{label}: invalid\n{detail[:500]}"
        except FileNotFoundError:
            return True, f"{label}: validation skipped (tool not installed)"
        except subprocess.TimeoutExpired:
            return False, f"{label}: validation timeout"
        except Exception as e:
            return False, f"{label}: validator error: {e}"

    if ext == ".py":
        try:
            with tempfile.TemporaryDirectory(prefix="astra-verify-") as td:
                pyc = str(Path(td) / "check.pyc")
                return run_check([
                    shutil.which("python3") or "python3",
                    "-c",
                    "import py_compile,sys; py_compile.compile(sys.argv[1], cfile=sys.argv[2], doraise=True)",
                    file_path, pyc
                ], "Python")
        except Exception as e:
            return False, f"Python validator error: {e}"

    if ext == ".json":
        return run_check(["python3", "-m", "json.tool", file_path], "JSON")

    if ext in (".js", ".mjs", ".cjs"):
        return run_check(["node", "--check", file_path], "JavaScript")

    if ext == ".rs":
        try:
            with tempfile.TemporaryDirectory(prefix="astra-rust-") as td:
                output_path = str(Path(td) / "astra_verify.rmeta")
                return run_check([
                    "rustc", "--edition=2021",
                    "--crate-name=astra_verify",
                    "--emit=metadata", "-o", output_path, file_path
                ], "Rust")
        except Exception as e:
            return False, f"Rust validator error: {e}"

    if ext == ".java":
        try:
            with tempfile.TemporaryDirectory(prefix="astra-javac-") as td:
                return run_check([
                    "javac", "-d", td, file_path
                ], "Java", timeout=60)
        except Exception as e:
            return False, f"Java validator error: {e}"

    if ext == ".xml":
        return run_check([
            "python3", "-c",
            "import sys,xml.etree.ElementTree as E; E.parse(sys.argv[1])",
            file_path
        ], "XML")

    if ext == ".toml":
        return run_check([
            "python3", "-c",
            "import sys,tomllib; tomllib.load(open(sys.argv[1], 'rb'))",
            file_path
        ], "TOML")

    if ext in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError:
            return True, "YAML: validation skipped (PyYAML not installed)"
        try:
            with open(file_path, "r", encoding="utf-8") as stream:
                yaml.safe_load(stream)
            return True, "YAML: valid"
        except Exception as e:
            return False, f"YAML: invalid\n{str(e)[:500]}"

    if ext in (".ts", ".tsx", ".jsx"):
        tsc = shutil.which("tsc")
        if not tsc:
            candidate = (
                Path.home()
                / ".local/share/astrix-toolchain/node_modules/.bin/tsc"
            )
            if candidate.is_file():
                tsc = str(candidate)

        if not tsc:
            return True, (
                f"{ext[1:].upper()}: validation skipped "
                "(TypeScript compiler 'tsc' not installed)"
            )

        if ext == ".tsx":
            ts_cmd = [
                tsc, "--noEmit", "--pretty", "false",
                "--jsx", "preserve", file_path
            ]
        elif ext == ".jsx":
            ts_cmd = [
                tsc, "--noEmit", "--pretty", "false",
                "--allowJs", "--checkJs", "false",
                "--jsx", "preserve", file_path
            ]
        else:
            ts_cmd = [
                tsc, "--noEmit", "--pretty", "false", file_path
            ]

        return run_check(ts_cmd, ext[1:].upper(), timeout=60)

    if ext in (".sh", ".bash"):
        return run_check(["bash", "-n", file_path], "Shell")

    if ext == ".go":
        gofmt = shutil.which("gofmt")
        if not gofmt:
            return True, "Go: validation skipped (gofmt not installed)"
        return run_check([gofmt, "-e", file_path], "Go")

    if ext == ".zig":
        zig = shutil.which("zig")
        if not zig:
            return True, "Zig: validation skipped (zig compiler not installed)"
        return run_check([zig, "ast-check", file_path], "Zig AST")

    # GNU assembler: .S uses preprocessing; .s does not.
    if ext in (".S", ".s"):
        gcc = shutil.which("gcc")
        if not gcc:
            return True, "Assembly: validation skipped (gcc not installed)"
        language = "assembler-with-cpp" if ext == ".S" else "assembler"
        try:
            with tempfile.TemporaryDirectory(prefix="astra-asm-") as td:
                obj = str(Path(td) / "check.o")
                return run_check([
                    gcc, "-c", "-x", language,
                    "-o", obj, file_path
                ], "Assembly")
        except Exception as e:
            return False, f"Assembly validator error: {e}"

    # NASM source.
    if ext == ".asm":
        nasm = shutil.which("nasm")
        if not nasm:
            return True, "NASM: validation skipped (nasm not installed)"
        try:
            with tempfile.TemporaryDirectory(prefix="astra-nasm-") as td:
                obj = str(Path(td) / "check.o")
                return run_check([
                    nasm, "-f", "elf64", "-o", obj, file_path
                ], "NASM")
        except Exception as e:
            return False, f"NASM validator error: {e}"

    # C/C++ source files and standalone headers.
    c_exts = {".c", ".h"}
    cpp_exts = {".cpp", ".cc", ".hpp", ".hh"}

    if ext in c_exts | cpp_exts:
        compiler = shutil.which(
            "gcc" if ext in c_exts else "g++"
        )
        if not compiler:
            return True, "C/C++: validation skipped (compiler not installed)"

        cmd = list(VERIFY_COMPILER.get(
            ext, [compiler, "-fsyntax-only"]
        ))
        cmd.append("-ffreestanding")
        cmd.append(
            "-std=gnu++17" if ext in cpp_exts else "-std=gnu11"
        )

        if ext == ".h":
            cmd.extend(["-x", "c"])
        elif ext in (".hpp", ".hh"):
            cmd.extend(["-x", "c++"])

        # Discover nearby include directories in the workspace.
        try:
            import os as _os

            workspace = Path(config.get_workspace()).resolve()
            skip_dirs = {
                ".git", "node_modules", "__pycache__", ".venv",
                "venv", "build", "bin", "dist", "target", ".cache"
            }
            include_dirs = {str(workspace)}

            for root, dirs, _files in _os.walk(str(workspace)):
                dirs[:] = [
                    d for d in dirs if d.lower() not in skip_dirs
                ]
                rel = _os.path.relpath(root, str(workspace))
                depth = 0 if rel == "." else rel.count(_os.sep) + 1

                if depth > 3:
                    dirs[:] = []
                    continue

                include_dirs.add(root)

            for directory in sorted(include_dirs):
                cmd.append(f"-I{directory}")
        except Exception:
            pass

        cmd.append(file_path)
        label = "C++" if ext in cpp_exts else "C"
        return run_check(cmd, label)

    # Objective-C and Objective-C++.
    if ext in (".m", ".mm"):
        compiler_name = "clang" if ext == ".m" else "clang++"
        compiler = shutil.which(compiler_name)
        if not compiler:
            return True, (
                f"{compiler_name}: validation skipped "
                "(compiler not installed)"
            )

        language = "objective-c" if ext == ".m" else "objective-c++"
        cmd = [compiler, "-fsyntax-only", "-x", language]
        if ext == ".mm":
            cmd.append("-std=gnu++17")
        cmd.append(file_path)
        return run_check(cmd, "Objective-C")

    if ext not in VERIFY_COMPILER:
        return True, (
            f"validation skipped: no verifier configured for "
            f"{ext or 'unknown extension'}"
        )

    cmd = list(VERIFY_COMPILER[ext])
    cmd.append(file_path)
    return run_check(cmd, ext)

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
    
    _mark_read(path)
    if offset > 0 or limit > 0:
        lines = content.split("\n")
        total = len(lines)
        start = max(0, offset)
        end = total if limit == 0 else min(total, start + limit)
        sliced = lines[start:end]
        header = f"[Lines {start+1}-{end} of {total}]\n"
        return header + "\n".join(sliced)
    
    return content



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
    workspace_root = Path(config.get_workspace()).resolve()
    trash_dir = workspace_root / ".trash"

    if trash_dir.is_symlink():
        return "ERROR: workspace/.trash tidak boleh berupa symlink"

    try:
        trash_dir.mkdir(parents=True, exist_ok=True)
        trash_dir = trash_dir.resolve()
        trash_dir.relative_to(workspace_root)
    except ValueError:
        return "ERROR: lokasi trash berada di luar workspace"
    except OSError as exc:
        return f"ERROR membuat trash workspace: {exc}"

    stamp = time.strftime("%Y%m%d-%H%M%S")
    trashed = trash_dir / f"{stamp}_{p.name}"
    shutil.move(str(p), str(trashed))
    log(f"DELETE {path} -> {trashed}")
    return f"OK: {path} dipindah ke trash"

def grep(pattern, path=".", max_hits=25):
    """Look for patterns (regex) in files/folders. Return: file: line: content."""

    import re as _re
    try:
        p = safe_path(str(path or "."))
        workspace_root = Path(config.get_workspace()).resolve()
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
                        rel = f.relative_to(workspace_root) if workspace_root in f.parents else f
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
    """Jalankan satu perintah tanpa shell; batasi operasi berisiko."""
    import shlex as _shlex
    import shutil as _shutil
    from pathlib import Path as _Path

    cmd = cmd or command
    if not isinstance(cmd, str) or not cmd.strip():
        return "ERROR: command kosong atau tidak valid"

    # Pertahankan auto-detection build lama.
    if cmd.strip() in ("make", "make all", "make build"):
        try:
            detected = detect_build_command()
            if detected != cmd.strip():
                log(f"[AUTO-BUILD] Mengganti '{cmd}' menjadi '{detected}'")
                cmd = detected
        except Exception:
            pass

    try:
        argv = _shlex.split(cmd, posix=True)
    except ValueError as exc:
        return f"ERROR: format command tidak valid: {exc}"

    if not argv:
        return "ERROR: command kosong"

    executable_token = argv[0]
    executable = _Path(executable_token).name

    # Hanya nama program dari allowlist, bukan path executable pilihan.
    if executable_token != executable:
        return "ERROR: path executable langsung tidak diizinkan"
    if executable not in ALLOWED_COMMANDS:
        return f"ERROR: '{executable}' tidak diizinkan"
    if not _shutil.which(executable):
        return f"ERROR: executable '{executable}' tidak ditemukan"

    # Jangan izinkan chaining atau redirection shell.
    shell_operators = {";", "&&", "||", "|", ">", ">>", "<", "<<", "&"}
    if any(token in shell_operators for token in argv):
        return "ERROR: operator shell tidak diizinkan; panggil tool secara terpisah"

    # Hindari eksekusi kode inline melalui interpreter.
    if executable in {"python", "python3"} and any(
        token in {"-c", "--command"} for token in argv[1:]
    ):
        return "ERROR: eksekusi kode Python inline tidak diizinkan"

    if executable == "node" and any(
        token in {"-e", "--eval", "-p", "--print"} for token in argv[1:]
    ):
        return "ERROR: eksekusi kode Node inline tidak diizinkan"

    # Mutasi filesystem harus menggunakan tool khusus yang memvalidasi path.
    direct_mutators = {
        "rm", "mv", "cp", "mkdir", "touch", "chmod", "chown",
        "curl", "wget", "zip", "unzip",
    }
    if executable in direct_mutators:
        return (
            f"ERROR: command '{executable}' dibatasi; "
            "gunakan tool file yang sesuai atau proses build khusus"
        )

    if executable == "sed" and any(
        token in {"-i", "--in-place"} for token in argv[1:]
    ):
        return "ERROR: sed in-place tidak diizinkan"

    if executable == "find" and any(
        token in {
            "-exec", "-execdir", "-delete", "-ok", "-okdir",
            "-fprint", "-fprintf", "-fls",
        }
        for token in argv[1:]
    ):
        return "ERROR: operasi mutasi/eksekusi find tidak diizinkan"

    if executable == "awk" and any(
        "system(" in token.replace(" ", "")
        or "system(" in token
        for token in argv[1:]
    ):
        return "ERROR: awk system() tidak diizinkan"

    # Perubahan Git dilakukan melalui alur yang eksplisit, bukan command umum.
    blocked_git_commands = {
        "add", "commit", "reset", "clean", "checkout", "restore",
        "rm", "apply", "stash", "rebase", "merge", "cherry-pick",
        "revert",
    }
    if executable == "git" and len(argv) > 1:
        if argv[1] in blocked_git_commands:
            return f"ERROR: git {argv[1]} dibatasi di run_command"

    workspace = _Path(config.get_workspace()).resolve()
    self_root = _Path(SELF_ROOT).resolve()

    # Jika workspace sama dengan, di dalam, atau menaungi source Astrix,
    # izinkan inspeksi saja melalui runner umum.
    overlaps_self_tree = (
        workspace == self_root
        or workspace in self_root.parents
        or self_root in workspace.parents
    )

    if overlaps_self_tree:
        readonly_commands = {
            "ls", "cat", "grep", "pwd", "find", "head", "tail", "wc",
            "df", "free", "uname", "tree", "ps", "top", "echo", "git",
        }

        if executable not in readonly_commands:
            return (
                f"ERROR: '{executable}' dibatasi ketika workspace "
                "mencakup source Astrix AI; gunakan tool khusus"
            )

        if executable == "git":
            readonly_git_commands = {
                "status", "diff", "log", "show", "branch",
                "rev-parse", "ls-files",
            }
            if len(argv) < 2 or argv[1] not in readonly_git_commands:
                return "ERROR: hanya subcommand Git read-only yang diizinkan"

    try:
        result = subprocess.run(
            argv,
            shell=False,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return f"exit={result.returncode}\\n{output[:MAX_TOOL_RESULT_CHARS]}"
    except subprocess.TimeoutExpired:
        return "ERROR: timeout 60s"
    except Exception as exc:
        return f"ERROR run_command: {exc}"

def build_project(target="build", jobs=4, timeout=180):
    """Build target pada workspace aktif tanpa menjalankan shell."""
    import re as _re
    import shutil as _shutil

    if not isinstance(target, str):
        return "ERROR: target harus berupa teks"

    target = target.strip()
    if (
        not target
        or len(target) > 128
        or target.startswith("-")
        or not _re.fullmatch(r"[A-Za-z0-9_./:@+-]+", target)
    ):
        return "ERROR: target tidak valid; gunakan nama target sederhana"

    try:
        if isinstance(jobs, bool) or isinstance(timeout, bool):
            raise ValueError("boolean tidak valid")

        jobs = int(jobs)
        timeout = int(timeout)
    except (TypeError, ValueError, OverflowError):
        return "ERROR: jobs dan timeout harus berupa bilangan bulat"

    if not 1 <= jobs <= 64:
        return "ERROR: jobs harus berada pada rentang 1-64"
    if not 1 <= timeout <= 1800:
        return "ERROR: timeout harus berada pada rentang 1-1800 detik"

    try:
        workspace = config.resolve_workspace_path(config.get_workspace())
        make_executable = _shutil.which("make")

        if not make_executable:
            return "ERROR: executable make tidak ditemukan"

        cmd = [make_executable, f"-j{jobs}", target]
        result = subprocess.run(
            cmd,
            shell=False,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        output = (result.stdout or "") + (result.stderr or "")
        errors = [
            line for line in output.splitlines()
            if "error:" in line.lower() or "fatal error" in line.lower()
        ]
        warnings = [
            line for line in output.splitlines()
            if "warning:" in line.lower()
        ]

        status = "SUCCESS" if result.returncode == 0 else "FAILED"

        # Artefak diperiksa pada workspace yang sedang dibangun,
        # bukan pada direktori source aplikasi Astrix.
        boot_path = workspace / "BOOTX64.EFI"
        efi_exists = boot_path.is_file()
        efi_size = boot_path.stat().st_size if efi_exists else 0

        summary = f"""BUILD {status} (exit={result.returncode})
Workspace: {workspace}
Command: make -j{jobs} {target}
Errors: {len(errors)}, Warnings: {len(warnings)}
BOOTX64.EFI: {'ADA ' + str(efi_size) + ' bytes' if efi_exists else 'TIDAK ADA'}"""

        if errors:
            summary += "\n\n=== ERRORS (max 10) ===\n" + "\n".join(errors[:10])
        if warnings and len(warnings) <= 5:
            summary += "\n\n=== WARNINGS ===\n" + "\n".join(warnings[:5])
        if result.returncode == 0:
            tail = "\n".join(output.splitlines()[-10:])
            summary += f"\n\n=== TAIL OUTPUT ===\n{tail}"

        return summary[:MAX_TOOL_RESULT_CHARS]

    except subprocess.TimeoutExpired:
        return f"BUILD TIMEOUT setelah {timeout}s"
    except Exception as exc:
        return f"ERROR build_project: {type(exc).__name__}: {exc}"
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
    """Validasi self-edit setelah path diselesaikan secara kanonis."""
    from config import SELF_ROOT, SELF_EDIT_WHITELIST, SELF_EDIT_BLOCK

    raw_text = str(path).strip()
    if not raw_text or raw_text.startswith("~"):
        raise PermissionError("Path self-edit kosong atau tidak valid.")

    raw = Path(raw_text)
    if raw.is_absolute():
        raise PermissionError(f"Path absolut tidak diizinkan: {raw_text}")

    root = Path(SELF_ROOT).resolve()
    full = (root / raw).resolve()

    try:
        relative = full.relative_to(root)
    except ValueError:
        raise PermissionError(
            f"Path keluar SELF_ROOT setelah resolusi: {raw_text}"
        )

    parts = relative.parts
    relative_text = relative.as_posix()

    # Terapkan blokir terhadap path kanonis, bukan input mentah.
    for item in SELF_EDIT_BLOCK:
        blocked_name = str(item).strip("/")
        if blocked_name == ".env":
            blocked = any(
                part == ".env" or part.startswith(".env.")
                for part in parts
            )
        else:
            blocked = blocked_name in parts

        if blocked:
            raise PermissionError(
                f"Self-edit diblokir untuk path: {relative_text}"
            )

    # Entri berakhiran '/' berarti direktori beserta turunannya.
    allowed = False
    for item in SELF_EDIT_WHITELIST:
        rule = str(item)
        is_directory = rule.endswith("/")
        normalized = rule.rstrip("/")

        if is_directory:
            if (
                relative_text == normalized
                or relative_text.startswith(normalized + "/")
            ):
                allowed = True
                break
        elif relative_text == normalized:
            allowed = True
            break

    if not allowed:
        raise PermissionError(
            f"Path '{relative_text}' tidak ada di whitelist self-edit."
        )

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


def _create_self_backup(full):
    """Buat backup unik tanpa menimpa backup yang sudah ada."""
    import os
    import shutil
    import time
    from pathlib import Path

    full = Path(full)

    for attempt in range(100):
        name = f"{full.name}.bak.{time.time_ns()}.{attempt}"
        backup = full.with_name(name)

        try:
            fd = os.open(
                backup,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
        except FileExistsError:
            continue

        try:
            with full.open("rb") as src:
                with os.fdopen(fd, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            return backup
        except BaseException:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                backup.unlink()
            except OSError:
                pass
            raise

    raise FileExistsError("Tidak bisa membuat nama backup unik.")


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
        bak = _create_self_backup(full)
        new_content = original.replace(old_text, new_text, 1)
        full.write_text(new_content, encoding="utf-8")
        if str(full).endswith(".py"):
            r = subprocess.run(
                [
                    "python3",
                    "-c",
                    (
                        "import ast, pathlib, sys; "
                        "ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))"
                    ),
                    str(full),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if r.returncode != 0:
                shutil.copy2(bak, full)
                return f"SYNTAX ERROR - rollback. {r.stderr[:400]}"
        added = new_content.count("\n") - original.count("\n")
        commit_note = "Git commit belum dibuat."
        try:
            relative = full.relative_to(Path(SELF_ROOT).resolve()).as_posix()
            commit = subprocess.run(
                [
                    "git", "commit", "--only",
                    "-m", f"self-edit: {relative}",
                    "--", relative,
                ],
                cwd=str(SELF_ROOT),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if commit.returncode == 0:
                commit_note = "Git commit berhasil; hooks tidak dilewati."
            else:
                detail = (commit.stderr or commit.stdout or "").strip()
                detail = detail.replace("\n", " ")[:240]
                commit_note = (
                    f"Git commit gagal (exit {commit.returncode}): {detail}"
                )
        except Exception as exc:
            commit_note = f"Git commit gagal: {exc}"

        return (
            f"OK: {path} diedit ({added:+d} lines). "
            f"Backup: {bak.name}. {commit_note}"
        )
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
            bak = _create_self_backup(full)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        if str(full).endswith(".py"):
            r = subprocess.run(
                [
                    "python3",
                    "-c",
                    (
                        "import ast, pathlib, sys; "
                        "ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))"
                    ),
                    str(full),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
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

def _path_key(path):
    try:
        return str(safe_path(path).resolve())
    except Exception:
        return str(path)


def _mark_read(path):
    _read_files.add(_path_key(path))

def _mark_edited(path):
    _edited_files.add(str(path))

def was_read(path):
    return _path_key(path) in _read_files

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
        r = _sp.run(["git", "status", "--short"], cwd=str(config.get_workspace()),
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
        r = _sp.run(cmd, cwd=str(config.get_workspace()),
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
    ws = _P(str(config.get_workspace()))
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


def detect_build_command():
    """Deteksi command build yang tepat berdasarkan file di workspace."""
    from pathlib import Path
    ws = Path(config.get_workspace())
    
    if (ws / "Makefile").exists():
        content = (ws / "Makefile").read_text(errors="ignore")
        if "\nbuild:" in content or "\nbuild :" in content or content.startswith("build:"):
            return "make build -j$(nproc)"
        elif "\nall:" in content or "\nall :" in content or content.startswith("all:"):
            return "make all -j$(nproc)"
        else:
            return "make -j$(nproc)"
    elif (ws / "CMakeLists.txt").exists():
        return "cmake -B build && cmake --build build -j$(nproc)"
    elif (ws / "Cargo.toml").exists():
        return "cargo build --release"
    elif (ws / "package.json").exists():
        return "npm run build"
    elif (ws / "go.mod").exists():
        return "go build ./..."
    else:
        return "make"


def validate_project(path=".", timeout=180, jobs=4):
    """Validate a project using detected manifests, without shell=True."""
    import json as _json
    import shlex as _shlex

    try:
        timeout = max(10, min(int(timeout), 600))
        jobs = max(1, min(int(jobs), 32))
        target = safe_path(str(path))
        if target.is_file():
            target = target.parent
        if not target.is_dir():
            return f"PROJECT VALIDATION FAILED: bukan direktori: {path}"

        root = target.resolve()
        workspace = Path(config.get_workspace()).resolve()
        try:
            root.relative_to(workspace)
        except ValueError:
            return "PROJECT VALIDATION FAILED: direktori di luar workspace."
    except Exception as e:
        return f"PROJECT VALIDATION FAILED: {e}"

    checks = []
    skips = []
    errors = []
    manifests_found = []

    cargo_manifest = root / "Cargo.toml"
    go_manifest = root / "go.mod"
    tsconfig = root / "tsconfig.json"
    package_json = root / "package.json"
    cmake_file = root / "CMakeLists.txt"

    if cargo_manifest.is_file():
        manifests_found.append("Cargo.toml")
        cargo = shutil.which("cargo")
        if cargo:
            checks.append((
                "Rust / Cargo",
                [cargo, "check", "--workspace", "--all-targets"]
            ))
        else:
            skips.append("Rust: cargo tidak tersedia.")

    if go_manifest.is_file():
        manifests_found.append("go.mod")
        go = shutil.which("go")
        if go:
            checks.append(("Go", [go, "build", "./..."]))
        else:
            skips.append("Go: toolchain go tidak tersedia.")

    if tsconfig.is_file():
        manifests_found.append("tsconfig.json")
        tsc = shutil.which("tsc")
        if not tsc:
            candidate = (
                Path.home()
                / ".local/share/astrix-toolchain/node_modules/.bin/tsc"
            )
            if candidate.is_file():
                tsc = str(candidate)

        if tsc:
            checks.append((
                "TypeScript",
                [tsc, "--noEmit", "--pretty", "false",
                 "--project", str(tsconfig.resolve())]
            ))
        else:
            skips.append("TypeScript: compiler tsc tidak tersedia.")

    # Run the package's declared build script only when one exists.
    # npm scripts execute project-defined commands.
    if package_json.is_file():
        manifests_found.append("package.json")
        try:
            package = _json.loads(package_json.read_text(encoding="utf-8"))
            scripts = package.get("scripts", {})
            if not isinstance(scripts, dict):
                raise ValueError("'scripts' harus berupa JSON object.")
            if scripts.get("build"):
                npm = shutil.which("npm")
                if npm:
                    checks.append(("npm build", [npm, "run", "build"]))
                else:
                    skips.append("npm: executable npm tidak tersedia.")
        except Exception as e:
            errors.append(f"package.json tidak valid: {e}")

    if cmake_file.is_file():
        manifests_found.append("CMakeLists.txt")
        cmake = shutil.which("cmake")
        build_dir = root / "build"
        cache = build_dir / "CMakeCache.txt"

        if not cmake:
            skips.append("CMake: executable cmake tidak tersedia.")
        elif cache.is_file():
            checks.append((
                "CMake",
                [cmake, "--build", str(build_dir), "--parallel", str(jobs)]
            ))
        else:
            skips.append(
                "CMake: build/ belum dikonfigurasi; "
                "tidak menjalankan konfigurasi otomatis."
            )

    if not manifests_found:
        if (root / "Makefile").is_file():
            return (
                "PROJECT VALIDATION SKIPPED\n"
                f"Path: {root}\n"
                "Makefile terdeteksi. Gunakan build_project(target, jobs) "
                "agar target build yang sudah ada tetap dipakai."
            )
        return (
            "PROJECT VALIDATION SKIPPED\n"
            f"Path: {root}\n"
            "Tidak ditemukan manifest yang didukung "
            "(Cargo.toml, go.mod, tsconfig.json, package.json, "
            "atau CMakeLists.txt)."
        )

    results = []
    executed = 0
    failed = bool(errors)

    for error in errors:
        results.append(f"FAILED: {error}")

    for message in skips:
        results.append(f"SKIPPED: {message}")

    for label, cmd in checks:
        display = _shlex.join(cmd)
        try:
            result = subprocess.run(
                cmd,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
            executed += 1

            if result.returncode == 0:
                results.append(f"SUCCESS [{label}]: {display}")
            else:
                failed = True
                output = (result.stdout + "\n" + result.stderr).strip()
                tail = "\n".join(output.splitlines()[-12:])
                results.append(
                    f"FAILED [{label}] (exit={result.returncode}): {display}"
                    + (f"\n{tail[:1800]}" if tail else "")
                )
        except FileNotFoundError:
            skips.append(f"{label}: executable tidak ditemukan.")
            results.append(f"SKIPPED [{label}]: executable tidak ditemukan.")
        except subprocess.TimeoutExpired:
            failed = True
            results.append(f"FAILED [{label}]: timeout setelah {timeout}s.")
        except Exception as e:
            failed = True
            results.append(f"FAILED [{label}]: {e}")

    if failed:
        status = "FAILED"
    elif executed == 0:
        status = "SKIPPED"
    elif skips:
        status = "PARTIAL"
    else:
        status = "SUCCESS"

    header = [
        f"PROJECT VALIDATION {status}",
        f"Path: {root}",
        "Manifests: " + ", ".join(manifests_found),
        f"Executed checks: {executed}",
    ]

    return ("\n".join(header + results))[:MAX_TOOL_RESULT_CHARS]


TOOLS = {
    "validate_project": validate_project,
    "web_search": web_search,
    "browse_url": browse_url,
    "list_dir": list_dir,
    "read_file": read_file,
    "create_file": create_file,
    "write_file": write_file,
    "replace_text": guard_replace_text,
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
    "detect_build_command": detect_build_command,
}

# === Browser tools attach (HARUS setelah TOOLS didefinisikan) ===
try:
    from browser_agent import BROWSER_TOOLS
    TOOLS.update(BROWSER_TOOLS)
except Exception as _e:
    print(f'[BROWSER] not loaded: {_e}')
