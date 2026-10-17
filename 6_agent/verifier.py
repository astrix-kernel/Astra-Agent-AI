"""Verifier — check task FACTS, not just LLM review."""

import re, subprocess
from pathlib import Path
from tools import safe_path, _verify_syntax

ASTRIX_ROOT = ASTRIX_ROOT


def verify_task(task_desc, files_touched, state=None):
    """
from config import ASTRIX_ROOT
    Cek fakta apakah task beneran selesai.
    Return: (ok: bool, issues: list, evidence: dict)
    """
    issues = []
    evidence = {"files_checked": [], "build_status": None, "grep_results": []}
    desc = task_desc.lower()

    file_patterns = [
        r'(?:bikin|buat|create|new file|tambah)\s+([a-z0-9_/\.\-]+\.(?:c|h|S|asm|ld|mk|py|sh))',
        r'file\s+([a-z0-9_/\.\-]+\.(?:c|h|S|asm|ld|mk|py|sh))',
        r'path[:\s]+([a-z0-9_/\.\-]+\.(?:c|h|S|asm|ld|mk|py|sh))',
    ]
    expected_files = []
    for pat in file_patterns:
        expected_files.extend(re.findall(pat, desc))

    if any(k in desc for k in ["bikin file", "buat file", "create file", "new file", "bikin"]) and expected_files:
        for f in expected_files[:3]:
            found = list(ASTRIX_ROOT.rglob(f)) + list(ASTRIX_ROOT.rglob(Path(f).name))
            if not found:
                issues.append(f"❌ File `{f}` GAK ADA — task bilang udah bikin")
            else:
                evidence["files_checked"].append(str(found[0].relative_to(ASTRIX_ROOT)))

    if any(k in desc for k in ["fix", "build", "compile", "benerin", "error"]):
        try:
            r = subprocess.run(["make", "-j4"], cwd=str(ASTRIX_ROOT),
                              capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                err_preview = (r.stderr or r.stdout)[-500:]
                issues.append(f"❌ BUILD MASIH GAGAL: {err_preview}")
                evidence["build_status"] = "FAILED"
            else:
                evidence["build_status"] = "OK"
        except FileNotFoundError:
            pass
        except subprocess.TimeoutExpired:
            issues.append("⚠️ Build timeout >2 menit")
            evidence["build_status"] = "TIMEOUT"

    fn_patterns = [
        r'(?:tambah|bikin|buat)\s+(?:fungsi|function)\s+([a-z_][a-z0-9_]+)',
        r'(?:fungsi|function)\s+([a-z_][a-z0-9_]+)',
    ]
    expected_fns = []
    for pat in fn_patterns:
        expected_fns.extend(re.findall(pat, desc))

    for fn in expected_fns[:2]:
        try:
            r = subprocess.run(
                ["grep", "-rn", "--include=*.c", "--include=*.h", f"\\b{fn}\\b", "."],
                cwd=str(ASTRIX_ROOT), capture_output=True, text=True, timeout=15)
            if fn in r.stdout:
                evidence["grep_results"].append(f"✓ {fn} found")
            else:
                issues.append(f"❌ Fungsi `{fn}` GAK DITEMUKAN di codebase")
        except Exception:
            pass

    if not files_touched and "eksplorasi" not in desc and "baca" not in desc:
        issues.append("⚠️ Gak ada file yang disentuh — agent mungkin cuma jawab tanpa aksi")

    ok = len(issues) == 0
    return ok, issues, evidence


def build_fix_feedback(issues):
    """Make feedback for the executor if verification fails."""

    if not issues:
        return ""
    lines = ["## 🚫 VERIFIKASI GAGAL — TASK BELUM SELESAI"]
    lines.append("Verifier nemu masalah berikut. FIX DULU sebelum task_done:")
    for i, issue in enumerate(issues, 1):
        lines.append(f"{i}. {issue}")
    lines.append("")
    lines.append("Setelah fix, panggil tool yang sesuai, terus baru output task_done.")
    return "\n".join(lines)


def verify_error_pattern(tool, args, error):
    """Check if the error pattern has ever happened + there is an old solution."""

    from error_learning import find_similar
    prev = find_similar(tool, args, error)
    if prev and prev.get("count", 0) >= 2:
        sol = prev.get("solution", "")
        return f"⚠️ ERROR INI PERNAH KEJADIAN {prev['count']}x. " + \
               (f"Solusi lama yang works: {sol}" if sol else "Coba pendekatan BEDA.")
    return ""
