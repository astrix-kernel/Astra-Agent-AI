"""Intelligent planner-breakdown with dependency & verification."""

import json, re, time
from config import REQUEST_TIMEOUT
from tools import list_dir, read_file, grep
from knowledge import build_knowledge_block
from context import get_project_tree


PLANNER_PROMPT = """Kamu adalah **Planner** untuk Astra Agent — workspace project.

Tugasmu: baca goal dari user, breakdown jadi **15-30 task** yang SATU ORANG BISA KERJA SENDIRI.


1. **Eksplorasi dulu** (3-5 task pertama):
   - Baca Makefile, Kconfig
   - Lihat struktur folder yang relevan
   - Baca 2-3 file existing untuk pahami pola kode

2. **Desain sebelum implementasi**:
   - Buat dokumen arsitektur kalau perlu
   - Definisikan interface/header DULU sebelum .c

3. **Satu file per task**:
   - JANGAN gabung "bikin a.c dan b.c" dalam 1 task
   - Kecuali sangat kecil, pisah per file

4. **Verifikasi per komponen**:
   - Setelah bikin file .c, wajib ada task "build & fix error"
   - Task terakhir: "verify end-to-end"

5. **Urutan dependency**:
   - Header sebelum source
   - Low-level (memory, types) sebelum high-level (render, AI)
   - Test satu komponen sebelum lanjut ke berikutnya


{"tasks": [
  {"id": 1, "desc": "Eksplorasi: baca Makefile untuk pahami build target"},
  {"id": 2, "desc": "Eksplorasi: list isi kernel/ dan lihat pola folder"},
  {"id": 3, "desc": "Baca kernel/main.c untuk pahami entry point & existing patterns"},
  {"id": 4, "desc": "Bikin include/mymod/mymod.h — include guard, versi, error codes, struct forward declaration"},
  {"id": 5, "desc": "Bikin include/mymod/mymod_types.h — struct mymod_context_t, enum, konstanta"},
  {"id": 6, "desc": "Bikin src/mymod/mymod_core.c — implementasi mymod_init() dan mymod_shutdown()"},
  {"id": 7, "desc": "Build & fix error kompilasi mymod_core.c"},
  {"id": 8, "desc": "Bikin src/mymod/mymod_core_extra.c — fitur tambahan modul"},
  {"id": 9, "desc": "Build & fix error mymod_core_extra.c"},
  {"id": 10, "desc": "Update build system (Makefile/CMake/package.json) untuk include source baru"},
  {"id": 11, "desc": "Build full project & pastikan BOOTX64.EFI generated"},
  {"id": 12, "desc": "Verifikasi: cek simbol modul ter-load di binary/build output"}
]}

- JANGAN lebih dari 30 task (mode max: 40)
- JANGAN kurang dari 8 task (kecuali goal sangat kecil)
- Setiap task harus SPESIFIK dan TERUKUR
- Nggak boleh task ambiguous kayak "bikin bagus" atau "fix semua"
- Pastikan ada task BUILD setelah setiap batch file .c
- Output HANYA JSON, tanpa teks lain
"""


def plan(goal, verbose=True):
    if verbose:
        print("[Planner] Baca struktur project...", flush=True)
    root_info = list_dir(path=".")

    kernel_info = ""
    try:
        kernel_info = list_dir(path="kernel")
    except Exception:
        pass

    include_info = ""
    try:
        include_info = list_dir(path="include")
    except Exception:
        pass

    try:
        tree = get_project_tree(max_depth=2)
    except Exception:
        tree = "(gagal)"
    try:
        kb = build_knowledge_block(max_items=10)
    except Exception:
        kb = ""

    context = f"""=== STRUKTUR PROJECT ===
{tree[:1500]}

=== ISI kernel/ ===
{kernel_info[:1000]}

=== ISI include/ ===
{include_info[:800]}

{kb}

=== GOAL USER ===
{goal}
"""

    messages = [
        {"role": "system", "content": PLANNER_PROMPT},
        {"role": "user", "content": context},
    ]

    from llm import call_llm
    if verbose:
        print("[Planner] Minta LLM breakdown (1-3 menit)...", flush=True)

    t0 = time.time()
    import runtime
    cfg = runtime.cfg()
    raw = call_llm(messages,
                   max_tokens=cfg.get("max_tokens_planner", 8192),
                   temperature=cfg.get("temperature", 0.2))
    if verbose:
        print(f"[Planner] Selesai dalam {time.time()-t0:.1f}s", flush=True)

    raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip(), flags=re.MULTILINE)
    m = re.search(r'\{[\s\S]*"tasks"[\s\S]*\}', raw)
    if not m:
        raise ValueError(f"Planner output bukan JSON valid:\n{raw[:500]}")

    data = json.loads(m.group())
    tasks = []
    for i, t in enumerate(data.get("tasks", []), 1):
        tasks.append({
            "id": i,
            "desc": t.get("desc", str(t)),
            "status": "pending",
            "result": "",
            "notes": "", 
        })

    if not tasks:
        raise ValueError("Planner nggak ngasilin task.")

    return tasks
