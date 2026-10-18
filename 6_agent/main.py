"""Astra Agent CLI — goal mode + chat mode."""
from config import ASTRIX_ROOT
from loop import run_goal, run_chat
from chat import chat_turn as _chat_turn
from state import load_state, clear_state, summarize
from pathlib import Path
from budget import MODES
from personality import get as get_personality, set_mode as set_personality
from models import MODELS, all_models
from speed import is_fast, set_fast
import runtime

BANNER = f"""
╔════════════════════════════════════════════════════════╗
║   ASTRIX AGENT — dibuat dari 0, local-first     ║
╠════════════════════════════════════════════════════════╣
║  Sandbox : {str(ASTRIX_ROOT):<42} ║
║  Model   : {runtime.get_model()['icon']} {runtime.get_model()['label']:<38} ║
║  Mode    : {runtime.cfg()["icon"]} {runtime.cfg()["label"]:<39} ║
╚════════════════════════════════════════════════════════╝

  Commands:
    /goal <instruksi>   — goal besar, agent plan + eksekusi otonom
    /status             — lihat progress goal aktif
    /reset              — hapus state, mulai goal baru
    /chat <pesan>       — mode ngobrol (default, kalau nggak ada /)
    /clear              — hapus history chat
    /exit               — keluar

  Tips: ketik apa aja tanpa "/" → otomatis masuk mode ngobrol
"""




_tts_on = False


def _speak_response(text):
    """Baca respons pakai TTS kalau aktif."""
    if not _tts_on:
        return
    try:
        import tts
        import re
        clean = re.sub(r'```[\s\S]*?```', ' kode ', text)
        clean = re.sub(r'`[^`]+`', '', clean)
        clean = re.sub(r'[#*_>\[\]|]', '', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        if len(clean) > 500:
            clean = clean[:500] + "... dan seterusnya"
        if clean:
            tts.speak(clean)
    except Exception as e:
        print(f"  ⚠️  TTS error: {e}")


def _close_previous_goal(reason="new goal started"):
    """Tutup goal lama secara eksplisit sebelum mulai goal baru."""
    import state as _st
    import task_history as _th

    prev = _st.load_state()
    if prev:
        for t in prev.get("tasks", []):
            if t.get("status") == "pending":
                t["status"] = "aborted"
                t["result"] = reason
        _st.save_state(prev)
        print(f"  \u23f9  Goal lama ditutup: {prev.get('goal', '?')[:60]}")
        _st.clear_state()

    hist = _th.load()
    if hist.get("current_session"):
        _th.finish_task(summary=f"closed: {reason}")
        print(f"  \u23f9  Task history ditutup")


def main():
    global _tts_on
    print(BANNER)

    state = load_state()
    if state:
        s = summarize(state)
        print(f"  📋 Goal aktif: {state['goal'][:60]}")
        print(f"     Progress  : {s['done']}/{s['total']} task done")
        print(f"     Sesi      : #{state.get('sessions', 1)}\n")

    chat_history = []

    while True:
        try:
            cmd = input("astrix> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not cmd:
            continue

        if cmd in ("/exit", "/quit"):
            break
        if cmd == "/help":
            print(BANNER)
        elif cmd.startswith("/consult "):
            q = cmd[9:].strip()
            if not q:
                print("Usage: /consult <pertanyaan>\n")
            else:
                from multi_model import consult
                print(f"\n  🔮 Consulting multi-model...\n")
                result = consult(q)
                print(f"{result}\n")
        elif cmd == "/memory" or cmd.startswith("/memory "):
            import long_memory
            parts = cmd.split(maxsplit=2)
            if len(parts) == 1:
                st = long_memory.stats()
                print(f"\n  🧠 Long-term Memory:")
                for k, v in st.items():
                    print(f"     {k}: {v}")
                print(f"\n  Lihat: /memory show")
                print(f"  Tambah: /memory add <kategori> <teks>")
                print(f"  Kategori: preferences, decisions, patterns, facts, learnings\n")
            elif parts[1] == "show":
                block = long_memory.build_memory_block(max_items=30)
                print(f"\n{block if block else '  (kosong)'}\n")
            elif parts[1] == "add" and len(parts) >= 3:
                rest = parts[2].split(maxsplit=1)
                if len(rest) >= 2:
                    cat, text = rest[0], rest[1]
                    long_memory.add(cat, text)
                    print(f"  ✅ Disimpan ke {cat}\n")
                else:
                    print("  Usage: /memory add <kategori> <teks>\n")
            elif parts[1] == "clear":
                import os
                p = Path.home() / ".astrix-agent/long_memory.json"
                if p.exists():
                    p.unlink()
                print("  🗑️  Memory dihapus\n")
            else:
                print("  Usage: /memory | /memory show | /memory add <cat> <text> | /memory clear\n")
        elif cmd == "/personality" or cmd.startswith("/personality "):
            parts = cmd.split(maxsplit=1)
            if len(parts) == 1:
                cur = get_personality()
                print(f"\n  Personality aktif: {cur}")
                print("  Pilihan: roast (kasar + roasting), sopan, normal\n")
                print("  Ganti: /personality roast | sopan | normal\n")
            else:
                target = parts[1].strip().lower()
                try:
                    new = set_personality(target)
                    print(f"\n  ✅ Personality: {new}\n")
                except ValueError as e:
                    print(f"  ❌ {e}\n")
        elif cmd == "/roast":
            set_personality("roast")
            print("\n  🔥 ROAST MODE ON — siap di roasting\n")
        elif cmd == "/sopan":
            set_personality("sopan")
            print("\n  ✨ SOPAN MODE ON\n")
        elif cmd == "/normal":
            set_personality("normal")
            print("\n  😐 NORMAL MODE ON\n")
        elif cmd == "/tts":
            _tts_on = not _tts_on
            print(f"\n  {'🔊 TTS ON' if _tts_on else '🔇 TTS OFF'}\n")
        elif cmd == "/voice":
            try:
                import voice
                text = voice.voice_cli()
                if text:
                    print(f"  📝 \"{text}\"")
                    resp, _ = _chat_turn([], text, focus="chat")
                    print(f"\n{resp}\n")
            except Exception as e:
                print(f"  ❌ Voice error: {e}\n")
        elif cmd == "/fast":
            set_fast(True)
            print("\n  🚀 FAST MODE ON")
            print("  • Auto-route: chat simple → Lightning, coding → DeepSeek Flash")
            print("  • Parallel tool execution")
            print("  • Max tool rounds dikurangi (4)")
            print("  • Chat singkat, task cepat\n")
        elif cmd == "/slow":
            set_fast(False)
            print("\n  🐢 SLOW MODE (quality mode)")
            print("  • Manual model: pilih via /model")
            print("  • Full tool rounds (8)")
            print("  • Kualitas maksimal\n")
        elif cmd.startswith("/newfile "):
            parts = cmd[9:].strip().split(maxsplit=1)
            if not parts:
                print("Usage: /newfile <path> [content]\n")
            else:
                from tools import create_file
                path = parts[0]
                content = parts[1] if len(parts) > 1 else ""
                result = create_file(path, content)
                print(f"\n  {result}\n")
        elif cmd.startswith("/append "):
            parts = cmd[8:].strip().split(maxsplit=1)
            if len(parts) < 2:
                print("Usage: /append <path> <content>\n")
            else:
                from tools import append_to_file
                result = append_to_file(parts[0], parts[1])
                print(f"\n  {result}\n")
        elif cmd.startswith("/delete-lines "):
            parts = cmd[14:].strip().split()
            if len(parts) < 2:
                print("Usage: /delete-lines <path> <start> [end]\n")
            else:
                from tools import delete_lines
                path = parts[0]
                start = int(parts[1])
                end = int(parts[2]) if len(parts) > 2 else None
                result = delete_lines(path, start, end)
                print(f"\n  {result}\n")
        elif cmd == "/model" or cmd.startswith("/model "):
            parts = cmd.split(maxsplit=1)
            if len(parts) == 1:
                cur = runtime.get_model_key()
                m = MODELS[cur]
                print(f"\n  Model aktif: {m['icon']} {m['label']} ({cur})")
                print(f"  {m['desc']}")
                print(f"  Use case: {m['use_case']} | Speed: {'★'*m['speed']}{'☆'*(5-m['speed'])}")
                print(f"  Reasoning: {'★'*m['reasoning']}{'☆'*(5-m['reasoning'])} | Coding: {'★'*m['coding']}{'☆'*(5-m['coding'])}\n")
                print("  Daftar model:")
                for k in MODELS:
                    marker = "→" if k == cur else " "
                    mm = MODELS[k]
                    print(f"  {marker} {mm['icon']} {k:<20}  {mm['label']}")
                print("\n  Ganti: /model <nama>\n")
            else:
                target = parts[1].strip().lower()
                try:
                    new = runtime.set_model(target)
                    m = MODELS[new]
                    print(f"\n  ✅ Model: {m['icon']} {m['label']}")
                    print(f"  {m['desc']}")
                    print(f"  Rekomendasi mode: {m.get('recommended_mode', 'medium').upper()}\n")
                except ValueError as e:
                    print(f"  ❌ {e}\n")
        elif cmd == "/mode" or cmd.startswith("/mode "):
            parts = cmd.split(maxsplit=1)
            if len(parts) == 1:
                cur = runtime.get()
                print(f"\n  Mode aktif: {MODES[cur]['icon']} {MODES[cur]['label']} ({cur})")
                print(f"  {MODES[cur]['desc']}\n")
                for m, cfg in MODES.items():
                    marker = "→" if m == cur else " "
                    print(f"  {marker} {cfg['icon']} {m:<8}  {cfg['label']:<8}  {cfg['desc']}")
                print("\n  Ganti: /mode minimum | /mode medium | /mode maximum\n")
            else:
                target = parts[1].strip().lower()
                try:
                    new = runtime.set_mode(target)
                    print(f"\n  ✅ Mode: {MODES[new]['icon']} {MODES[new]['label']}\n")
                except ValueError as e:
                    print(f"  ❌ {e}\n")
        elif cmd == "/clear":
            chat_history = []
            print("  ✅ History chat dihapus.\n")
        elif cmd == "/status":
            st = load_state()
            if not st:
                print("  Nggak ada goal aktif.\n")
            else:
                s = summarize(st)
                print(f"\n  Goal: {st['goal']}")
                print(f"  Progress: {s['done']}/{s['total']} done, {s['failed']} failed, {s['pending']} pending")
                print(f"  Sesi: #{st.get('sessions', 1)}, updated: {st.get('updated_at', '?')}\n")
        elif cmd == "/reset":
            clear_state()
            print("  ✅ State dihapus.\n")
        elif cmd.startswith("/goal "):
            goal = cmd[6:].strip()
            if not goal:
                print("Usage: /goal <instruksi>")
                continue
            _close_previous_goal()
            chat_history = []
            result = run_goal(goal, force_new=True)
            print(f"\n{result}\n")
        elif cmd == "/resume":
            result = run_goal(None, force_new=False)
            print(f"\n{result}\n")
        elif cmd.startswith("/chat "):
            msg = cmd[6:].strip()
            if not msg:
                continue
            try:
                response, chat_history = _chat_turn(chat_history, msg)
                print(f"\n{response}\n")
                _speak_response(response)
            except KeyboardInterrupt:
                print("\n  ⛔ Dibatalkan.\n")
        elif cmd.startswith("/ask "):
            q = cmd[5:].strip()
            if q:
                try:
                    print("\n" + run_chat(q) + "\n")
                except KeyboardInterrupt:
                    print("\n  ⛔ Dibatalkan.\n")
        else:
            try:
                response, chat_history = _chat_turn(chat_history, cmd)
                print(f"\n{response}\n")
                _speak_response(response)
            except KeyboardInterrupt:
                print("\n  ⛔ Dibatalkan.\n")


if __name__ == "__main__":
    main()
