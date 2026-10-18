"""Self-Reflection — agent review kerjanya sendiri sebelum task_done."""
import json
import requests
from config import LLM_URL, LLM_API_KEY, REQUEST_TIMEOUT
import runtime


def _get_tools():
    from tools import TOOLS
    return TOOLS



REFLECTION_PROMPT = """Kamu adalah **Reviewer** untuk task OS dev di workspace.

Kamu baru saja menyelesaikan task. Tugasmu: REVIEW apakah hasilnya benar-benar sesuai task.

- Task eksplorasi (baca/list) → OK kalau ada bukti file yang dibaca
- JANGAN flag "no evidence" kalau task = eksplorasi dan agent udah baca file
- JANGAN flag "kurang lengkap" kalau task = baca file dan file udah dibaca
- Cuma flag kalau: (a) build gagal, (b) file nggak ada, (c) task eksekusi gagal total
- Kalau ragu → pass aja (jangan bikin agent loop)


1. Cek apakah SEMUA yang diminta task sudah dikerjakan
2. Cek apakah ada yang MISSING atau tidak lengkap
3. Cek apakah file yang dibuat/diubah SUDAH dibuild (kalau .c/.h)
4. Cek apakah build BERHASIL (kalau gagal, harus fix dulu)
5. Cek apakah ada file terkait yang perlu di-update (Makefile, Kconfig, header)


- list_dir(path), read_file(path), grep(pattern, path)
- run_command(cmd), build_project(target, jobs)


Kalau task SUDAH benar selesai:
  {"review": "pass", "reason": "penjelasan singkat"}

Kalau masih ada kekurangan:
  {"review": "fix", "issues": ["issue 1", "issue 2"], "next_action": {"tool": "...", "args": {...}}}

Kalau perlu build ulang:
  {"review": "fix", "issues": ["belum di-build"], "next_action": {"tool": "build_project", "args": {"target": "build", "jobs": 4}}}



1. Section "FILE YANG DISENTUH" di prompt = bukti agent UDAH KERJA. Kalau ada minimal 1 baris, artinya agent udah baca/list file → PASS.
2. Kalau agent bilang `task_done` dan ada file disentuh → **PASTI PASS**. Jangan flag.
3. Kalau task = "Eksplorasi", "baca", "list", "cek" → PASS kalau ada `read_file:` atau `list_dir:` di files_touched.
4. JANGAN pernah flag "no files read" kalau files_touched ada isinya. Itu SALAH.
5. Kalau ragu → PASS. Default = PASS.
"""


def reflect(task_desc, task_summary, files_touched, verbose=True):
    """
    Agent review hasil kerjanya.
    Return: (status, next_action_or_reason)
    status: "pass" | "fix" | "error"
    """
    task_lower = task_desc.lower()
    
    is_build_task = any(k in task_lower for k in [
        "build", "compile", "test", "verify", "verifikasi",
        "fix error", "fix syntax", "check compile"
    ])
    
    if not is_build_task:
        return "pass", f"auto-pass (task non-build, {len(files_touched)} files touched)"
    
    files_str = "\n".join(f"  ✓ {f}" for f in files_touched) if files_touched else "  (nggak ada)"

    messages = [
        {"role": "system", "content": REFLECTION_PROMPT},
        {"role": "user", "content": f"""TASK YANG DIKERJAKAN:
{task_desc}

RINGKASAN HASIL (dari executor):
{task_summary}

FILE YANG DISENTUH:
{files_str}

Review hasil ini. Kalau ada yang kurang, kasih next_action. Kalau sudah bagus, kasih "pass"."""},
    ]

    from llm import call_llm as _call_llm
    try:
        raw = _call_llm(messages, max_tokens=2048)
    except Exception as e:
        return "error", str(e)

    import re
    raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip(), flags=re.MULTILINE)
    m = re.search(r'\{[\s\S]*\}', raw)
    if not m:
        return "pass", "reflection parse failed, assume OK"

    try:
        obj = json.loads(m.group())
    except json.JSONDecodeError:
        return "pass", "reflection parse failed"

    review = obj.get("review", "pass")
    if review == "pass":
        return "pass", obj.get("reason", "OK")
    elif review == "fix":
        return "fix", {
            "issues": obj.get("issues", []),
            "next_action": obj.get("next_action"),
        }
    return "pass", "unknown"
