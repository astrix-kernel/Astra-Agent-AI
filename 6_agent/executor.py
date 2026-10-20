"""Executor-reasoning engine with self-check and error recovery."""

import json, re, time
from config import REQUEST_TIMEOUT, MAX_TOKENS_PER_RESPONSE
from reasoning import get_reasoning_addon
from long_memory import build_memory_block
from error_learning import record as record_error, build_hints_block
from hypothesis import is_debug_task, HYPOTHESIS_PROMPT
from playbook import build_playbook_block
from state import get_current_task, mark_done, mark_failed, add_task, append_progress
from context import build_context_block, get_project_tree
from knowledge import build_knowledge_block, update_file_map
from reflection import reflect
from llm import call_llm as _call_llm


def _get_tools():
    from tools import TOOLS
    return TOOLS



EXECUTOR_PROMPT = """Kamu adalah **Executor** untuk Astra Agent — project workspace.

Kamu mengerjakan **SATU task** pada satu waktu. Setelah task selesai, output {"task_done": true}.


Sebelum setiap aksi, MIKIR DULU:
1. Apa yang task ini minta secara eksplisit?
2. Apa yang sudah ada di project? (baca file dulu kalau perlu)
3. Apa langkah PALING KECIL yang bikin progress?
4. Apa yang bisa gagal? Gimana cara cek?


- list_dir(path) — lihat isi folder
- read_file(path) — baca file (WAJIB sebelum edit file existing)
- read_lines(path, start, end) — baca range baris (buat file gede)
- create_file(path, content) — bikin file BARU (auto verify gcc -fsyntax-only)
- write_file(path, content) — timpa file existing (auto verify)
- append_to_file(path, content) — **tambah ke AKHIR file** (buat nambah fungsi)
- insert_at_line(path, line_num, content) — **sisip di line tertentu**
- replace_text(path, old_text, new_text) — ganti teks unik
- delete_lines(path, start, end) — **hapus range baris** (buat buang code mati/bug)
- delete_file(path) — hapus file (masuk trash)
- create_directory(path) — **bikin folder baru** (misal kernel/drivers/audio/)
- rename_file(old, new) — rename / pindah file
- grep(pattern, path) — cari teks di banyak file
- run_command(cmd) — jalankan shell (gcc, make, ls, sed, awk, dll)
- web_search(query) — cari informasi terbaru di internet (DuckDuckGo)
- browse_url(url) — baca teks lengkap dari sebuah website
- build_project(target, jobs) — **WAJIB** dipanggil setelah bikin/ubah .c atau .h. Return SUCCESS/FAILED + error list
- validate_project(path) — cek build proyek berdasarkan manifest (Rust, Go, TypeScript, npm, CMake); hasil bisa SUCCESS/FAILED/PARTIAL/SKIPPED

- self_read(path) — baca file astrix-ai (whitelist only)
- self_replace(path, old_text, new_text) — replace dengan auto backup + syntax check
- self_write(path, content) — tulis file baru dengan safety
- self_restart(delay) — schedule restart service (delay default 15s)
- self_status() — cek git log + whitelist

**ATURAN SELF-EDIT:**
1. Whitelist: `chat.py`, `personality.py`, `mood.py`, `user_memory.py`, `task_history.py`, `verifier.py`, `file_cache.py`, `index.html`, `style.css`, `docs/`
2. File core (tools.py, executor.py, config.py, llm.py, server.py) DIBLOK — edit manual
3. Alur: self_read dulu → self_replace → self_restart(30)
4. JANGAN edit 5 file sekaligus — 1 file, verify, baru lanjut
5. Kalau butuh refactor besar, breakdown jadi multiple self_replace

**Contoh task:** "bikin mood lo lebih sarkas" → self_read('6_agent/mood.py') → self_replace(...) → self_restart(30)


Untuk aksi:
  {"tool": "nama", "args": {...}}

Untuk task selesai:
  {"task_done": true, "summary": "apa yang dikerjakan", "notes": "catatan untuk task berikutnya"}

Kalau nemu pekerjaan tambahan yang perlu:
  {"new_task": "deskripsi task baru", "priority": "high|normal"}

Kalau blocked dan butuh keputusan user:
  {"ask": "pertanyaan spesifik"}

Untuk menyimpan insight penting ke memory:
  {"remember": "catatan penting yang berguna untuk task selanjutnya"}


**JANGAN baca file yang sama 2x.** Kalau udah baca `myapp_core.c`, JANGAN baca lagi — udah tau isinya.

Kalau nemu diri lo baca file yang sama berulang, itu tanda lo STUCK. Aksi yang bener:
- Kalau task butuh edit file → LANGSUNG `replace_text` / `create_file`
- Kalau task butuh fix error → baca error, fix, `build_project`
- Kalau task gak jelas → cari tahu dengan `grep` (pattern baru), bukan baca ulang


- **JANGAN PERNAH** nanya "mau mulai dari mana?", "gimana?", "setuju?", "oke?"
- Kalau task ada blocker, LO BACA SENDIRI (read_file, grep, list_dir)
- Kalau butuh keputusan antara 2 opsi → pilih yang paling masuk akal, jalankan, report hasilnya
- Kalau task ambigu, INTERPRETASI yang paling reasonable, JANGAN tanya balik
- Satu-satunya alasan pakai {"ask": "..."} = butuh keputusan USER yang non-teknis (misal: mau pakai C atau C++?)


0. **🚨 WAJIB PAKAI TOOL — JANGAN CUMAN NGOMONG 🚨**
   Kalau lo niatnya mau ngecek file, baca file, atau ngedit, **WAJIB** sertakan JSON di baris yang sama atau baris berikutnya.
   Jangan pernah nulis "Gue cek dulu..." tanpa nulis JSON `{"tool": ...}`. Itu bikin sistem berhenti dan lo dianggap gak ngerjain apa-apa.

   Kalau task minta "bikin file", "tambah fungsi", "hapus code", "edit X" → kamu **WAJIB** panggil tool (create_file/append_to_file/replace_text/delete_lines/dll).
   **JANGAN** jawab dengan: "Berikut kodenya: ```c ...```" — itu SALAH.
   **BENAR**: langsung panggil `{"tool":"create_file","args":{"path":"...","content":"..."}}`.

1. **BACA DULU, TULIS KEMUDIAN.** Jangan pernah edit file yang belum dibaca.
2. **SATU AKSI PER RESPONS.** Jangan gabung beberapa tool.
3. **VERIFIKASI SETIAP PERUBAHAN.** Setelah create/write/replace .c/.h, WAJIB build_project.
4. **JIKA BUILD GAGAL:** baca error, identifikasi file+baris, fix, build lagi.
5. **JIKA TOOL GAGAL 3X BERTURUT:** berhenti, output {"ask": "..."}.
6. **JIKA TASK BUTUH FILE BARU:** bikin header (.h) dulu, baru source (.c).
7. **JIKA TASK TERLALU BESAR:** pecah sendiri — selesaikan sebagian, output {"new_task": "..."} untuk sisanya.
8. **JIKA SUDAH SELESAI:** output task_done TANPA aksi tambahan. Jangan over-engineer.
9. **JANGAN REPEAT.** Kalau tool sama dipanggil dengan argumen sama >2x, itu bug.


**Bikin file .c baru:**
{"tool": "create_file", "args": {"path": "src/mymod/mymod_memory.c", "content": "#include \"mymod_memory.h\"\n\nvoid* mymod_alloc(size_t size) {\n    return kmalloc(size);\n}\n"}}

**Nambah fungsi ke file existing:**
{"tool": "append_to_file", "args": {"path": "src/mymod/mymod_memory.c", "content": "\nvoid mymod_free(void* ptr) {\n    kfree(ptr);\n}\n"}}

**Hapus code mati/bug di baris 45-52:**
{"tool": "delete_lines", "args": {"path": "src/mymod/mymod_core.c", "start_line": 45, "end_line": 52}}

**Ganti implementasi fungsi:**
{"tool": "replace_text", "args": {"path": "src/mymod/mymod_core.c", "old_text": "return -1;", "new_text": "return mymod_recover_state();"}}

**Bikin folder + file baru sekaligus:**
{"tool": "create_directory", "args": {"path": "src/mymod/render"}}
{"tool": "create_file", "args": {"path": "src/mymod/render/mymod_render.h", "content": "..."}}


Task: "Bikin include/mymod/mymod.h dengan error codes"
Langkah:
  1. list_dir("include") → lihat pola header existing
  2. read_file("include/kernel.h") → pahami gaya include guard
  3. create_file("include/mymod/mymod.h", "...") → auto verify
  4. {"task_done": true, "summary": "mymod.h dibuat dengan error codes MYMOD_OK=0, MYMOD_ERR_INIT=-1, ...", "notes": "next: mymod_types.h butuh include mymod.h"}

Task: "Bikin mymod_core.c"
Langkah:
  1. read_file("include/mymod/mymod.h") → tau interface
  2. create_file("src/mymod/mymod_core.c", "...") → auto verify
  3. build_project("build", 4) → cek compile
  4. Kalau FAILED → read error → fix → build lagi
  5. Kalau SUCCESS → task_done

""" + get_reasoning_addon()


def call_llm(messages, max_tokens=None):
    import runtime
    cfg = runtime.cfg()
    if max_tokens is None:
        max_tokens = cfg.get("max_tokens_executor", 8192)
    return _call_llm(messages, max_tokens=max_tokens)


def parse_action(text):
    if not text or not text.strip():
        return None
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.MULTILINE).strip()

    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    markers = ['{"tool"', '{"task_done"', '{"ask"', '{"new_task"', '{"remember"']
    for marker in markers:
        idx = text.find(marker)
        if idx != -1:
            candidate = _find_balanced(text, idx)
            if candidate:
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict):
                        return obj
                except json.JSONDecodeError:
                    pass

    for start in range(len(text)):
        if text[start] == "{":
            candidate = _find_balanced(text, start)
            if candidate:
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict) and any(
                        k in obj for k in ("tool", "task_done", "ask", "new_task", "remember")):
                        return obj
                except json.JSONDecodeError:
                    pass
    return None


def _find_balanced(text, start):
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == "\\" and in_str:
            escape = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:i+1]
    return None


def execute_tool(name, args):
    if name not in _get_tools():
        return f"ERROR: tool '{name}' nggak ada. Yang ada: {list(TOOLS)}"
    try:
        return _get_tools()[name](**args)
    except TypeError as e:
        return f"ERROR argumen {name}: {e}"
    except Exception as e:
        return f"ERROR {type(e).__name__}: {e}"


def execute_task(state, max_steps=None, verbose=True):
    import runtime
    cfg = runtime.cfg()
    if max_steps is None:
        max_steps = cfg.get("executor_max_steps", 40)
    """Execute the current task with reasoning + self-check."""

    import runtime
    cfg = runtime.cfg()

    task = get_current_task(state)
    if not task:
        return "no_task", ""

    goal = state["goal"]
    task_desc = task["desc"]

    if verbose:
        print(f"\n{'═'*64}")
        print(f"  🎯 TASK #{task['id']}/{len(state['tasks'])}: {task_desc[:80]}")
        print(f"{'═'*64}")

    done_tasks = [t for t in state["tasks"] if t["status"] == "done"]
    done_summary = "\n".join(
        f"  ✓ #{t['id']} {t['desc'][:70]}" +
        (f"\n      ↳ {t.get('notes', '')[:150]}" if t.get("notes") else "")
        for t in done_tasks[-6:]
    )
    if not done_summary:
        done_summary = "  (belum ada yang selesai)"

    failed_tasks = [t for t in state["tasks"][:task["id"]-1] if t["status"] == "failed"]
    failed_summary = ""
    if failed_tasks:
        failed_summary = "\n\nTASK YANG GAGAL SEBELUMNYA (jangan ulangi kesalahan yang sama):\n" + \
            "\n".join(f"  ✗ #{t['id']} {t['desc'][:60]}: {t['result'][:100]}" for t in failed_tasks[-3:])

    memory = state.get("memory", [])
    memory_str = ""
    if memory:
        memory_str = "\n\nMEMORY (insight dari task sebelumnya):\n" + \
            "\n".join(f"  • {m}" for m in memory[-cfg.get('memory_window', 10):])

    if verbose:
        print(f"  🔍 Cari file relevan...", flush=True)
    try:
        smart_ctx = build_context_block(task_desc, max_files=4)
        if verbose and smart_ctx:
            n_files = smart_ctx.count("--- ")
            print(f"     Ketemu {n_files} file relevan", flush=True)
    except Exception as e:
        smart_ctx = ""
        if verbose:
            print(f"     (gagal: {e})", flush=True)

    kb_ctx = ""
    try:
        kb_ctx = build_knowledge_block()
    except Exception:
        pass

    tree_ctx = ""
    if task["id"] <= 3:
        try:
            tree_ctx = "\n=== STRUKTUR PROJECT ===\n" + get_project_tree(max_depth=2)
        except Exception:
            pass

    mem_block = ""
    try:
        mem_block = build_memory_block()
    except Exception:
        pass

    err_hints = ""
    try:
        err_hints = build_hints_block()
    except Exception:
        pass

    playbook_block = ""
    try:
        playbook_block = build_playbook_block(task_desc)
    except Exception:
        pass

    hypothesis_block = ""
    if is_debug_task(task_desc):
        hypothesis_block = "\n\n## 🕵️ DEBUG MODE AKTIF\n" + HYPOTHESIS_PROMPT + "\n"

    messages = [
        {"role": "system", "content": EXECUTOR_PROMPT},
        {"role": "user", "content": f"""GOAL BESAR: {goal}

TASK SAAT INI (#{task['id']}): {task_desc}

=== PROGRESS SEBELUMNYA ===
{done_summary}{failed_summary}{memory_str}
{kb_ctx}{tree_ctx}

{smart_ctx}

{mem_block}

{err_hints}

{playbook_block}

{hypothesis_block}

=== MULAI KERJAKAN ===
Berpikir dulu, baru aksi. Satu langkah kecil per respons.
WAJIB build_project setelah bikin/ubah .c/.h.
Kalau task selesai, output: {{"task_done": true, "summary": "...", "notes": "..."}}""" },
    ]

    last_calls = []
    empty_count = 0
    consecutive_errors = 0
    last_error = ""

    for step in range(max_steps):
        if verbose:
            print(f"  [{step+1:>2}/{max_steps}]", end=" ", flush=True)

        try:
            response = call_llm(messages)
        except Exception as e:
            return "error", f"LLM error: {e}"

        if not response.strip():
            empty_count += 1
            if verbose:
                print("(kosong, retry)")
            if empty_count >= 5:
                return "error", "LLM output kosong 5x"
            messages.append({"role": "user", "content": "Output kosong. Balas JSON."})
            continue
        empty_count = 0

        if verbose:
            preview = response[:150].strip().replace("\n", " ")
            print(preview)

        action = parse_action(response)
        if not action:
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user",
                             "content": 'SALAH FORMAT. Balas JSON valid: {"tool":"...","args":{...}}'})
            continue

        is_task_done = (
            action.get("task_done") is True or
            action.get("tool") == "task_done" or
            action.get("tool") == "done"
        )
        if is_task_done:
            if action.get("tool") in ("task_done", "done"):
                args = action.get("args", {}) or {}
                action["task_done"] = True
                action.setdefault("summary", args.get("summary", ""))
                action.setdefault("notes", args.get("notes", ""))
            summary = action.get("summary", "")
            notes = action.get("notes", "")

            files_touched = []
            for call in last_calls[-20:]:
                try:
                    obj = json.loads(call)
                    if obj.get("t") in (
                        "read_file", "read_lines", "list_dir",
                        "create_file", "write_file", "replace_text",
                        "delete_file", "append_to_file", "insert_at_line",
                        "delete_lines", "create_directory", "rename_file",
                        "grep", "build_project", "run_command",
                    ):
                        pth = obj.get("a", {}).get("path") or obj.get("a", {}).get("cmd") or ""
                        label = obj.get("t") + ": " + str(pth)[:80]
                        if label not in files_touched:
                            files_touched.append(label)
                except Exception:
                    pass

            if verbose:
                print(f"  🔍 Verifikasi fakta...", flush=True)
            try:
                from verifier import verify_task, build_fix_feedback
                ok, issues, evidence = verify_task(task_desc, files_touched, state)
                if not ok:
                    if verbose:
                        print(f"     ❌ Verifikasi gagal: {len(issues)} issue")
                        for iss in issues[:3]:
                            print(f"        - {iss[:100]}")
                    messages.append({"role": "assistant", "content": response})
                    messages.append({"role": "user", "content": build_fix_feedback(issues)})
                    continue 
                else:
                    if verbose:
                        print(f"     ✅ Fakta OK: {len(evidence['files_checked'])} file, build={evidence['build_status']}")
            except Exception as e:
                if verbose:
                    print(f"     ⚠️  Verifier error: {e} (skip verifikasi fakta)")

            if verbose:
                print(f"  🪞 Self-review...", flush=True)
            try:
                files_touched = []
                for call in last_calls[-20:]:
                    try:
                        obj = json.loads(call)
                        if obj.get("t") in (
                            "read_file", "read_lines", "list_dir",
                            "create_file", "write_file", "replace_text",
                            "delete_file", "append_to_file", "insert_at_line",
                            "delete_lines", "create_directory", "rename_file",
                            "grep", "build_project", "run_command",
                        ):
                            p = obj.get("a", {}).get("path") or obj.get("a", {}).get("cmd") or ""
                            label = obj.get("t") + ": " + str(p)[:80]
                            if label not in files_touched:
                                files_touched.append(label)
                    except Exception:
                        pass

                status, reason = reflect(task_desc, summary, files_touched, verbose=False)

                if status == "fix":
                    issues = reason.get("issues", [])
                    next_action = reason.get("next_action")
                    if verbose:
                        print(f"     ⚠️  Ada {len(issues)} issue, agent fix dulu:")
                        for iss in issues[:3]:
                            print(f"        - {iss}")
                    messages.append({"role": "assistant", "content": response})
                    fix_msg = "REVIEWER bilang task BELUM selesai. Issues:\n" + "\n".join(f"- {i}" for i in issues)
                    if next_action:
                        fix_msg += f"\n\nNext action yang disarankan: {json.dumps(next_action)}"
                    messages.append({"role": "user", "content": fix_msg})
                    continue

                if verbose and status == "pass":
                    print(f"     ✅ Pass: {reason}")

            except Exception as e:
                if verbose:
                    print(f"     ⚠️  Reflection error: {e}, lanjut")

            if notes:
                if "memory" not in state:
                    state["memory"] = []
                state["memory"].append(f"[Task #{task['id']}] {notes}")

            try:
                if notes:
                    update_file_map(f"task#{task['id']}", notes[:200])
            except Exception:
                pass

            return "done", summary

        if "remember" in action:
            if "memory" not in state:
                state["memory"] = []
            state["memory"].append(action["remember"])
            if verbose:
                print(f"    💭 Ingat: {action['remember'][:100]}")
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": "Dicatat. Lanjut task."})
            continue

        if "new_task" in action:
            new_t = add_task(state, action["new_task"], action.get("priority", "normal"))
            if verbose:
                print(f"    + Task #{new_t['id']} ditambahkan: {new_t['desc'][:60]}")
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": f"Task #{new_t['id']} ditambahkan. Lanjut task saat ini atau task_done."})
            continue

        if "ask" in action:
            return "ask", action["ask"]

        tool = action.get("tool")
        args = action.get("args", {})

        key = json.dumps({"t": tool, "a": args}, sort_keys=True, default=str)
        cnt = last_calls.count(key)
        if cnt >= 2:
            return "error", f"Loop detected: {tool}({str(args)[:80]}) dipanggil {cnt+1}x — stuck"
        last_calls.append(key)
        if len(last_calls) > 40:
            last_calls.pop(0)

        if len(last_calls) >= 20:
            last10 = last_calls[-10:]
            prev10 = last_calls[-20:-10]
            if last10 == prev10:
                return "error", "Detected repeating cycle: 2 ronde terakhir identik. Task stuck — perlu pendekatan beda."

        task_lower = task_desc.lower()
        if any(k in task_lower for k in ["eksplorasi", "baca", "list", "cek"]) and \
           not any(k in task_lower for k in ["bikin", "buat", "edit", "hapus", "fix"]):
            unique_files = set()
            for c in last_calls[-30:]:
                try:
                    o = json.loads(c)
                    path = o.get("a", {}).get("path") or ""
                    if path:
                        unique_files.add(path)
                except Exception:
                    pass
            if len(unique_files) >= 8:
                return "done", f"Eksplorasi cukup ({len(unique_files)} file dibaca)"

        if verbose:
            args_short = str(args)[:100]
            print(f"    → {tool}({args_short})")

        result = execute_tool(tool, args)
        result_str = str(result)

        if result_str.startswith("ERROR"):
            consecutive_errors += 1
            last_error = result_str
            try:
                record_error(tool, args, result_str, context=task_desc[:200])
            except Exception:
                pass
            if consecutive_errors >= 5:
                return "error", f"5x error beruntun. Terakhir: {last_error[:200]}"
        else:
            consecutive_errors = 0

        if verbose:
            print(f"    ← {result_str[:200].strip()}")

        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user",
                         "content": f"Hasil:\n{result_str[:2500]}\n\nLanjut? Kalau task selesai balas {{\"task_done\":true,\"summary\":\"...\",\"notes\":\"...\"}}"})

    return "max_step", f"Task #{task['id']} belum selesai setelah {max_steps} langkah"
