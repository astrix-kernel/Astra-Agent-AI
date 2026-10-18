"""Astra Agent — main loop: plan → execute → verify → repeat."""
from state import (
    load_state, save_state, clear_state, create_state,
    get_current_task, mark_done, mark_failed, is_complete,
    summarize, append_progress,
)
from planner import plan
from git_checkpoint import checkpoint, ensure_branch, auto_commit_and_push
from notify import notify_done, notify_error, notify_blocked
from executor import execute_task


def run_goal(goal, verbose=True, max_tasks_per_session=50, force_new=False):
    """Main entry: kerjakan goal besar sampai selesai."""

    state = load_state()

    try:
        ensure_branch()
    except Exception:
        pass

    if force_new and state:
        if verbose:
            print(f"\n🆕 Goal baru (mengganti: '{state.get('goal', '')[:50]}...')\n")
        clear_state()
        state = None

    if state:
        old_goal = state.get("goal", "")
        if old_goal != goal:
            if verbose:
                print(f"\n📋 Goal baru (mengganti): '{old_goal[:60]}...'")
                print(f"   (Goal lama ditutup otomatis)\n")
            clear_state()
            state = None
        else:
            if verbose:
                print(f"\n📋 Resume goal: '{goal[:60]}...'\n")

    if not state:
        if verbose:
            print(f"\n╔════════════════════════════════════════╗")
            print(f"║  GOAL: {goal[:30]:<30} ║")
            print(f"╚════════════════════════════════════════╝\n")
            print("[1] PLANNING — pecah goal jadi task kecil...")

        try:
            tasks = plan(goal, verbose=verbose)
        except KeyboardInterrupt:
            print("\n  ⛔ Planning dibatalkan user. Nggak ada state yang dibuat.")
            return "Dibatalkan."
        except Exception as e:
            print(f"\n  ❌ Gagal planning: {e}")
            print("  Jalanin lagi nanti — server biasanya pulih.")
            return f"❌ Gagal planning: {e}"

        state = create_state(goal, tasks)
        save_state(state)

        if verbose:
            print(f"\n✅ Planner kasih {len(tasks)} task:")
            for t in tasks[:10]:
                print(f"   #{t['id']} {t['desc'][:70]}")
            if len(tasks) > 10:
                print(f"   ... dan {len(tasks)-10} task lain")
            print()
    else:
        if verbose:
            s = summarize(state)
            print(f"\n🔄 RESUME — melanjutkan goal:")
            print(f"   {state['goal']}")
            print(f"   Progress: {s['done']}/{s['total']} done, {s['failed']} failed, {s['pending']} pending\n")
        state["sessions"] = state.get("sessions", 1) + 1
        save_state(state)

    tasks_done_this_session = 0
    while not is_complete(state):
        if tasks_done_this_session >= max_tasks_per_session:
            save_state(state)
            s = summarize(state)
            return f"⏸️  Sesi ini selesai ({tasks_done_this_session} task). Progress: {s['done']}/{s['total']}. Jalanin lagi nanti buat lanjut."

        task = get_current_task(state)
        if not task:
            break

        try:
            status, info = execute_task(state, verbose=verbose)
        except KeyboardInterrupt:
            save_state(state)
            print(f"\n  ⛔ Dihentikan user. Progress tersimpan.")
            return f"⏸️  Dihentikan. Progress: {summarize(state)['done']}/{summarize(state)['total']}. Jalanin lagi buat resume."

        if status == "done":
            mark_done(state, info)
            save_state(state)
            tasks_done_this_session += 1

            if tasks_done_this_session % 5 == 0:
                try:
                    cp = auto_commit_and_push(label=f"task-{task['id']}", push=True)
                    if cp.get("ok") and cp.get("hash"):
                        pushed_str = " + pushed" if cp.get("pushed") else ""
                        print(f"  💾 Commit: {cp['hash']}{pushed_str}")
                        print(f"     {cp.get('message', '')}")
                        if cp.get("push_error"):
                            print(f"     ⚠️  Push gagal: {cp['push_error'][:100]}")
                except Exception as e:
                    if verbose:
                        print(f"  ⚠️  Auto-commit gagal: {e}")

            if tasks_done_this_session % 10 == 0:
                import time as _t
                print(f"\n  ☕ Jeda 30s (setiap 10 task selesai)...\n")
                _t.sleep(30)
            append_progress(f"✓ Task #{task['id']} SELESAI: {task['desc']}\n  {info[:300]}")
            if verbose:
                print(f"\n  ✅ Task #{task['id']} selesai. Progress: {summarize(state)['done']}/{summarize(state)['total']}\n")

        elif status == "ask":
            save_state(state)
            try:
                notify_blocked(f"Agent Butuh Keputusan", info[:150])
            except Exception:
                pass
            return f"❓ Agent bertanya (task #{task['id']}):\n{info}\n\nJawab dengan: /goal <jawaban>"

        elif status == "max_step":
            save_state(state)
            append_progress(f"⚠️ Task #{task['id']} MAX STEP: {task['desc']}")
            if verbose:
                print(f"\n  ⚠️ Task #{task['id']} kena max step.\n")
            mark_failed(state, "max step exceeded")
            state["current_idx"] += 1
            save_state(state)

        elif status == "error":
            save_state(state)
            append_progress(f"❌ Task #{task['id']} ERROR: {info}")

            try:
                notify_error(f"Task #{task['id']} Error", info[:150])
            except Exception:
                pass

            if not task.get("cascade_tried"):
                if verbose:
                    print(f"\n  🔄 Cascade: pecah task #{task['id']} jadi sub-task...\n")
                task["cascade_tried"] = True

                import uuid
                subs = [
                    f"[Cascade {task['id']}.1] Analisis ulang: baca file terkait, identifikasi blocker",
                    f"[Cascade {task['id']}.2] Coba pendekatan alternatif untuk: {task['desc'][:80]}",
                    f"[Cascade {task['id']}.3] Verifikasi hasil alternatif + build",
                ]
                insert_at = state["current_idx"] + 1
                for i, sub_desc in enumerate(subs):
                    new_id = max([t["id"] for t in state["tasks"]], default=0) + 1
                    state["tasks"].insert(insert_at + i, {
                        "id": new_id,
                        "desc": sub_desc,
                        "status": "pending",
                        "result": "",
                        "notes": "",
                        "cascade_parent": task["id"],
                    })
                for i, t in enumerate(state["tasks"], 1):
                    t["id"] = i
                mark_failed(state, f"error: {info[:100]} (di-cascade)")
                state["current_idx"] += 1
                save_state(state)
                continue
            else:
                return f"❌ Task #{task['id']} gagal permanen: {info}\n\nState tersimpan di ~/.astrix-agent/state.json"

        else:
            break

    if is_complete(state):
        s = summarize(state)
        append_progress(f"🎉 GOAL SELESAI: {state['goal']}\n  Total task: {s['total']}, done: {s['done']}")

        try:
            cp = auto_commit_and_push(label="goal-complete", push=True)
            if cp.get("ok") and cp.get("hash"):
                pushed_str = " + pushed" if cp.get("pushed") else ""
                print(f"  💾 Final commit: {cp['hash']}{pushed_str}")
                print(f"     {cp.get('message', '')}")
        except Exception:
            pass

        try:
            notify_done("Goal Selesai!", f"{s['done']}/{s['total']} task done")
        except Exception:
            pass

        result = f"\n🎉 SELESAI! Goal tuntas.\n  Total: {s['total']} task, {s['done']} done, {s['failed']} failed\n  Sesi: {state.get('sessions', 1)}"
        save_state(state)
        return result

    s = summarize(state)
    return f"⏸️  Sesi berhenti. Progress: {s['done']}/{s['total']}. Jalanin ulang buat lanjut."


def run_chat(message, verbose=True):
    """Chat tanpa eksekusi."""
    import requests
    from config import LLM_URL, LLM_API_KEY, REQUEST_TIMEOUT
    import runtime
    messages = [
        {"role": "system", "content": "Kamu Astra Agent — asisten coding workspace. Jawab singkat dan teknis."},
        {"role": "user", "content": message},
    ]
    r = requests.post(LLM_URL,
        headers={"Authorization": f"Bearer {LLM_API_KEY}"},
        json={"model": runtime.get_model_id(), "messages": messages, "max_tokens": 2048, "temperature": 0.3, "stream": False},
        timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]
