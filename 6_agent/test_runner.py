"""Test runner — detect & run project tests."""
import subprocess, re, time
from pathlib import Path
from config import ASTRIX_ROOT


def detect_test_command():
    makefile = ASTRIX_ROOT / "Makefile"
    if makefile.exists():
        content = makefile.read_text(errors="ignore")
        for target in ["test", "check", "test-all", "tests"]:
            if re.search(rf'^{target}\s*:', content, re.MULTILINE):
                return f"make {target}", f"Makefile target '{target}'"

    tests_dir = ASTRIX_ROOT / "tests"
    if tests_dir.exists():
        py = list(tests_dir.glob("test_*.py"))
        if py:
            return "python -m pytest tests/ -v", f"{len(py)} Python test files"

    if (ASTRIX_ROOT / "CMakeLists.txt").exists():
        return "ctest --output-on-failure", "CTest"

    return None, None


def run_tests(timeout=180):
    cmd, desc = detect_test_command()
    if not cmd:
        return {"ok": False, "error": "Nggak nemu test command"}

    t0 = time.time()
    try:
        r = subprocess.run(cmd, shell=True, cwd=ASTRIX_ROOT,
                           capture_output=True, text=True, timeout=timeout)
        elapsed = time.time() - t0
        output = (r.stdout + r.stderr)[:8000]

        # Parse summary
        passed = failed = errors = 0
        for line in output.split("\n"):
            m = re.search(r'(\d+)\s+passed', line)
            if m: passed = int(m.group(1))
            m = re.search(r'(\d+)\s+failed', line)
            if m: failed = int(m.group(1))
            m = re.search(r'(\d+)\s+error', line)
            if m: errors = int(m.group(1))

        summary = f"{passed} passed, {failed} failed, {errors} errors" if (passed or failed or errors) else ""

        return {
            "ok": r.returncode == 0,
            "command": cmd,
            "description": desc,
            "returncode": r.returncode,
            "output": output,
            "summary": summary,
            "duration": round(elapsed, 1),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "command": cmd, "error": f"Timeout ({timeout}s)"}
    except Exception as e:
        return {"ok": False, "command": cmd, "error": str(e)}


def format_report(result):
    if "error" in result and "command" not in result:
        return f"❌ Test error: {result['error']}"
    if "error" in result:
        return f"❌ Test error di `{result['command']}`: {result['error']}"

    lines = [
        f"🧪 `{result['command']}`",
        f"📊 {result.get('summary') or 'no summary'} — {result.get('duration', 0)}s",
        f"{'✅ PASS' if result['ok'] else '❌ FAIL'}",
    ]
    if not result["ok"]:
        errs = [l for l in result.get("output", "").split("\n")
                if any(k in l for k in ["FAILED", "AssertionError", "ERROR:", "error:"])][:5]
        for e in errs:
            lines.append(f"  {e[:150]}")
    return "\n".join(lines)
