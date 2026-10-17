import traceback
"""Astrix Web UI server — wrap agent + WebSocket streaming."""
import sys, os, json, asyncio, threading, time
from pathlib import Path
from contextlib import asynccontextmanager

sys.path.insert(0, str(Path.home() / "astrix-ai/6_agent"))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from state import load_state, summarize, clear_state
from budget import MODES
import runtime
from events import on_event, get_activity, get_totals
from config import ASTRIX_ROOT


_clients = set()
_log_buffer = []

def broadcast(msg: str, kind: str = "log"):
    """Kirim ke semua client + simpan di buffer."""
    global _log_buffer
    payload = {"kind": kind, "msg": msg, "ts": time.time()}
    _log_buffer.append(payload)
    if len(_log_buffer) > 500:
        _log_buffer = _log_buffer[-500:]
    dead = set()
    for ws in _clients:
        try:
            asyncio.run_coroutine_threadsafe(ws.send_json(payload), _loop)
        except Exception:
            dead.add(ws)
    _clients.difference_update(dead)




def broadcast_json(data: dict):
    """Kirim dict mentah ke semua client (bukan wrap)."""
    global _log_buffer
    data["ts"] = data.get("ts") or time.time()
    _log_buffer.append(data)
    if len(_log_buffer) > 500:
        _log_buffer = _log_buffer[-500:]
    dead = set()
    for ws in _clients:
        try:
            asyncio.run_coroutine_threadsafe(ws.send_json(data), _loop)
        except Exception:
            dead.add(ws)
    _clients.difference_update(dead)


def _file_event_listener(evt_type, data):
    if evt_type == "file_change":
        broadcast_json({"kind": "file_change", **data})


on_event(_file_event_listener)


class _BroadcastStream:
    """Redirect stdout/stderr dari worker thread ke WebSocket."""
    def __init__(self, kind="log"):
        self.kind = kind
        self.buffer = ""
    def write(self, s):
        self.buffer += s
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            if line.strip():
                broadcast(line, self.kind)
    def flush(self):
        if self.buffer.strip():
            broadcast(self.buffer, self.kind)
            self.buffer = ""


_loop = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _loop
    _loop = asyncio.get_event_loop()
    try:
        from model_sync import sync_and_save
        _n, _ = sync_and_save()
        if _n: print(f"[startup] synced {_n} models", flush=True)
    except Exception as _e:
        print(f"[startup] model sync skipped: {_e}", flush=True)

    try:
        _cur_model = runtime.get_model_key()
        _cur_label = _cur_model if _cur_model else "(belum dipilih — buka dropdown Model)"
    except Exception:
        _cur_label = "(belum dipilih)"
    broadcast(f"Astrix Web UI ready — model: {_cur_label}", "system")

    try:
        import mood as _mood
        d = _mood.get()
        from mood import MOODS
        emoji = MOODS.get(d.get("mood"), MOODS["neutral"])["emoji"]
        hour = __import__("datetime").datetime.now().hour
        if hour < 11:
            greet = "pagi"
        elif hour < 15:
            greet = "siang"
        elif hour < 19:
            greet = "sore"
        else:
            greet = "malam"
        broadcast(f"{emoji} {greet}! gw baru nyala nih. ada yang bisa dibantu atau cuma pengen ngobrol?", "chat_response")
    except Exception:
        pass
    yield


app = FastAPI(lifespan=lifespan)

try:
    from settings_ext import register_endpoints as _reg_ext
    def _dbg(msg):
        import sys
        print(msg, file=sys.stderr, flush=True)
    _reg_ext(app, _dbg)
except Exception as _e:
    import sys
    print(f"[SETTINGS-EXT] failed: {_e}", file=sys.stderr)

from fastapi.staticfiles import StaticFiles
import os
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")



class ChatReq(BaseModel):
    message: str
    focus: str = "coding"
    keep_context: bool = True
    web_search: bool = False
    system_prompt: str = "You are a helpful AI assistant."
    language: str = "id"
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    max_tokens: int = 4096
    freq_pen: float = 0.0
    pres_pen: float = 0.0
    compress_history: bool = False
    compress_limit: int = 10
    allow_code_exec: bool = True
    max_tool_rounds: int = 8
    workspace: str = ""
    provider: str = "omniroute"
    base_url: str = ""
    api_key: str = ""
    model_override: str = ""
    response_style: str = "default"


class GoalReq(BaseModel):
    goal: str


def _run_in_thread(fn, *args, **kwargs):
    """Jalankan fn di thread, redirect output ke broadcast."""
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = _BroadcastStream("log")
    sys.stderr = _BroadcastStream("err")
    try:
        fn(*args, **kwargs)
    except Exception as e:
        broadcast(f"ERROR: {type(e).__name__}: {e}", "err")
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        sys.stdout, sys.stderr = old_out, old_err




def _watcher_broadcast(action, rel_path, abs_path):
    try:
        broadcast_json({"kind": "file_watch", "action": action, "path": rel_path})
    except Exception:
        pass


try:
    from watcher import on_change as _watcher_on_change, start as _watcher_start
    _watcher_on_change(_watcher_broadcast)
    _watcher_start()
except Exception:
    pass


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(html_path.read_text())


@app.get("/api/status")
async def status():
    st = load_state()
    if not st:
        return {"active": False}
    s = summarize(st)
    return {
        "active": True,
        "goal": st["goal"],
        "progress": s,
        "tasks": st["tasks"],
        "current_idx": st["current_idx"],
        "sessions": st.get("sessions", 1),
    }


class ChatReq(BaseModel):
    message: str
    focus: str = "coding"
    keep_context: bool = True
    web_search: bool = False
    system_prompt: str = "You are a helpful AI assistant."
    language: str = "id"
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    max_tokens: int = 4096
    freq_pen: float = 0.0
    pres_pen: float = 0.0
    compress_history: bool = False
    compress_limit: int = 10
    allow_code_exec: bool = True
    max_tool_rounds: int = 8
    workspace: str = ""
    provider: str = "omniroute"
    base_url: str = ""
    api_key: str = ""
    model_override: str = ""
    response_style: str = "default"

    focus: str = "chat" 


class SessionReq(BaseModel):
    session_id: str = ""


@app.get("/api/sessions")
async def list_sessions_api():
    import chat_store
    sessions, active = chat_store.list_sessions()
    return {"sessions": sessions, "active": active}


@app.post("/api/sessions/new")
async def new_session_api():
    import chat_store
    s = chat_store.new_session()
    broadcast("Sesi baru dibuat.", "system")
    return {"ok": True, "session": s}


@app.post("/api/sessions/load")
async def load_session_api(req: SessionReq):
    import chat_store
    s = chat_store.load_session(req.session_id)
    if not s:
        return {"ok": False, "error": "session nggak ada"}
    chat_store.set_active(req.session_id)
    return {"ok": True, "session": s}


@app.post("/api/sessions/delete")
async def delete_session_api(req: SessionReq):
    import chat_store
    new_active = chat_store.delete_session(req.session_id)
    return {"ok": True, "active": new_active}


@app.post("/api/sessions/clear")
async def clear_active_session():
    import chat_store
    data = chat_store.clear_active()
    broadcast("Percakapan aktif dihapus.", "system")
    return {"ok": True, "session": data}


@app.get("/api/session/active")
async def get_active_session():
    import chat_store
    s = chat_store.get_active_session()
    return {"session": s}


from fastapi.responses import StreamingResponse


@app.post("/api/chat/stream")
async def chat_stream(req: ChatReq):
    import chat_store, json as _json
    from chat import _stream_api, _build_messages
    from config import LLM_URL, LLM_API_KEY
    
    session = chat_store.get_active_session()
    sid = session["id"]
    chat_store.append_message(sid, "user", req.message)
    history = [{"role": m["role"], "content": m["content"]} for m in session["messages"][:-1]] if getattr(req, 'keep_context', True) else []
    
    print(f"\n[CHAT-STREAM] msg={req.message[:30]!r} base_url={req.base_url!r} model={req.model_override!r}", flush=True)
    
    def sync_gen():
        yield f"data: {_json.dumps({'type': 'chunk', 'text': '🧪 '})}\n\n"
        
        try:
            import re as _re
            url_match = _re.search(r'https?://[^\s<>"]+', req.message)
            final_system_prompt = req.system_prompt
            final_user_message = req.message
            
            if url_match:
                url = url_match.group(0).rstrip('.,!?;:')
                print(f"[AUTO-BROWSE] Detected URL: {url}", flush=True)
                yield f"data: {_json.dumps({'type': 'chunk', 'text': f'🌐 Buka {url}... ' })}\n\n"
                
                try:
                    import sys as _sys
                    _sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent / "6_agent"))
                    from browser_agent import browser_open
                    page_content = browser_open(url)
                    print(f"[AUTO-BROWSE] Fetched {len(page_content)} chars", flush=True)
                    content_snippet = page_content[:4000]
                    final_user_message = f"""⚠️ CRITICAL: Kamu WAJIB jawab dari [LIVE WEB CONTENT] di bawah. DILARANG bilang "dari memori" atau "tidak punya akses web". Konten ini BARU SAJA DI-FETCH LIVE dari {url}.

════════ [LIVE WEB CONTENT] ════════
{content_snippet}
════════ [END LIVE WEB CONTENT] ════════

PERTANYAAN USER: {req.message}

WAJAB: Jawab berdasarkan konten di atas. Sebutkan "berdasarkan halaman yang saya buka"."""
                    yield f"data: {_json.dumps({'type': 'chunk', 'text': '✅ ' })}\n\n"

                    
                    try:
                        import re as _re2
                        click_m = _re2.search(r"(?:click|klik)\s+(?:on\s+|pada\s+)?[`'\"]([^`'\"]+)[`'\"]", req.message, _re2.I)
                        type_m = _re2.search(r"(?:type|fill|isi|ketik)\s+[`'\"]([^`'\"]+)[`'\"]\s+(?:into|to|ke|di)\s+[`'\"]([^`'\"]+)[`'\"]", req.message, _re2.I)
                        
                        if click_m:
                            from browser_agent import browser_click, browser_get_text
                            sel = click_m.group(1).strip()
                            print(f"[AUTO-CLICK] sel={sel}", flush=True)
                            click_result = browser_click(sel)
                            print(f"[AUTO-CLICK] result={click_result}", flush=True)
                            page_after = browser_get_text("body")
                            final_user_message += f"\n\n[AFTER CLICK {sel}]\n{click_result}\n\nCURRENT PAGE:\n{page_after[:3000]}\n[END AFTER CLICK]\n\nKalau click_result nyebut Navigated to, jelaskan halaman baru."
                        
                        if type_m:
                            from browser_agent import browser_type
                            text_val = type_m.group(1).strip()
                            sel = type_m.group(2).strip()
                            print(f"[AUTO-TYPE] {text_val} into {sel}", flush=True)
                            type_result = browser_type(sel, text_val)
                            print(f"[AUTO-TYPE] result={type_result}", flush=True)
                            final_user_message += f"\n\n[TYPED INTO {sel}]: {type_result}"

                        
                        enter_m = _re2.search(r"(?:tekan|press|hit|submit|kirim|enter)\s+(?:enter|return|submit|form)", req.message, _re2.I)
                        if enter_m and (click_m or type_m):
                            from browser_agent import browser_press, browser_get_text as _bgt
                            print(f"[AUTO-ENTER] pressing Enter", flush=True)
                            enter_result = browser_press("Enter")
                            print(f"[AUTO-ENTER] {enter_result}", flush=True)
                            import time as _t
                            _t.sleep(2) 
                            page_after_enter = _bgt("body")
                            final_user_message += f"\n\n[AFTER ENTER]\n{enter_result}\n\nRESULT PAGE:\n{page_after_enter[:3000]}\n[END RESULT]\n\nJawab berdasarkan halaman HASIL setelah Enter."
                    except Exception as _ce:
                        print(f"[AUTO-ACTION] Error: {_ce}", flush=True)
                except Exception as e:
                    print(f"[AUTO-BROWSE] Error: {e}", flush=True)
                    yield f"data: {_json.dumps({'type': 'chunk', 'text': f'❌ {e}' })}\n\n"
            
            msgs = _build_messages(history, final_user_message, final_system_prompt)
            
            if req.base_url and req.api_key:
                url = req.base_url.rstrip('/') + '/chat/completions'
                headers = {"Authorization": f"Bearer {req.api_key}", "Content-Type": "application/json"}
            else:
                url = LLM_URL
                headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
            
            payload = {
                "model": req.model_override or "openrouter/deepseek/deepseek-v4.1-flash",
                "messages": msgs,
                "temperature": req.temperature,
                "max_tokens": req.max_tokens,
                "stream": True,
            }
            
            print(f"[BYPASS] POST {url} | model={payload['model']}", flush=True)
            
            collected = []
            def cb(t):
                collected.append(t)
                print(f"[BYPASS] chunk: {repr(t[:40])}", flush=True)
            
            _stream_api(url, headers, payload, cb)
            
            print(f"[BYPASS] Selesai: {len(collected)} chunks", flush=True)
            
            if not collected:
                yield f"data: {_json.dumps({'type': 'chunk', 'text': '⚠️ API kasih response kosong. Coba model lain atau tunggu 60 detik.'})}\n\n"
            else:
                for c in collected:
                    yield f"data: {_json.dumps({'type': 'chunk', 'text': c})}\n\n"
            
            final = "".join(collected)
            if final.strip():
                chat_store.append_message(sid, "assistant", final)
            yield f"data: {_json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {_json.dumps({'type': 'chunk', 'text': '❌ ' + str(e)})}\n\n"
            yield f"data: {_json.dumps({'type': 'done'})}\n\n"
    
    return StreamingResponse(
        sync_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )



@app.post("/api/chat/stop")
async def chat_stop(req: dict = None):
    """Cancel chat yang lagi jalan."""
    import stop_flag
    sid = (req or {}).get("session_id")
    ok = stop_flag.request_stop(sid)
    if ok:
        broadcast("🛑 Stop signal dikirim", "system")
    return {"ok": ok}


@app.post("/api/chat")
async def chat(req: ChatReq):
    threading.Thread(
        target=_run_in_thread,
        args=(_do_chat, req.message, req.focus, req.web_search),
        daemon=True,
    ).start()
    return {"ok": True}


def _do_chat(msg, focus, web_search=False):
    from chat import chat_turn
    import chat_store
    import stop_flag

    session = chat_store.get_active_session()
    sid = session["id"]
    stop_flag.set_current(sid) 

    chat_store.append_message(sid, "user", msg)

    history = []
    if getattr(req, 'keep_context', True):
        history = [{"role": m["role"], "content": m["content"]} for m in session["messages"][:-1]]

    response, _ = chat_turn(history, msg, focus=focus, web_search=getattr(req, 'web_search', False))

    chat_store.append_message(sid, "assistant", response)

    stop_flag.clear(sid)
    broadcast(response, "chat_response")
    broadcast({"kind": "session_updated", "session_id": sid}, "system")


@app.post("/api/goal")
async def goal(req: GoalReq):
    from loop import run_goal
    threading.Thread(
        target=_run_in_thread,
        args=(run_goal, req.goal),
        daemon=True,
    ).start()
    return {"ok": True}


class ModeReq(BaseModel):
    mode: str


@app.get("/api/mode")
async def get_mode_api():
    cur = runtime.get()
    return {
        "current": cur,
        "config": MODES[cur],
        "all": [{"id": k, **MODES[k]} for k in MODES],
    }


@app.post("/api/mode")
async def set_mode_api(req: ModeReq):
    try:
        new = runtime.set_mode(req.mode)
        broadcast(f"Mode: {MODES[new]['icon']} {MODES[new]['label']}", "system")
        return {"ok": True, "mode": new}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


class ModelReq(BaseModel):
    model: str




class QemuReq(BaseModel):
    disk_image: str = ""
    ram: str = "512"


@app.post("/api/qemu/launch")
async def qemu_launch(req: QemuReq):
    from qemu_vision import launch
    import os
    disk = req.disk_image
    if not disk:
        return {"ok": False, "msg": "disk_image kosong"}
    ovmf = None
    for pth in ["/usr/share/edk2/x64/OVMF.4m.fd",
                "/usr/share/edk2-ovmf/x64/OVMF.fd",
                "/usr/share/OVMF/OVMF_CODE.fd"]:
        if os.path.exists(pth):
            ovmf = pth
            break
    extra = []
    if ovmf:
        extra = ["-drive", f"if=pflash,format=raw,readonly=on,file={ovmf}"]
    ok, msg = launch(disk, ram=req.ram, extra=extra)
    broadcast(f"QEMU: {msg}", "system")
    return {"ok": ok, "msg": msg}


@app.post("/api/qemu/stop")
async def qemu_stop():
    from qemu_vision import stop
    ok, msg = stop()
    broadcast(f"QEMU: {msg}", "system")
    return {"ok": ok, "msg": msg}


from fastapi.responses import FileResponse


@app.get("/api/qemu/image")
async def qemu_image(path: str):
    import os
    if not os.path.exists(path):
        return {"error": "file nggak ada"}
    if not path.startswith(str(Path.home() / ".astrix-agent")):
        return {"error": "path invalid"}
    return FileResponse(path, media_type="image/png")


@app.get("/api/qemu/status")
async def qemu_status():
    from qemu_vision import is_running, is_installed
    return {"running": is_running(), "installed": is_installed()}


@app.post("/api/qemu/screenshot")
async def qemu_screenshot(req: QemuReq):
    from qemu_vision import full_report, format_report, is_running, launch
    import os
    if not is_running() and req.disk_image:
        ovmf = None
        for pth in ["/usr/share/edk2/x64/OVMF.4m.fd",
                    "/usr/share/edk2-ovmf/x64/OVMF.fd",
                    "/usr/share/OVMF/OVMF_CODE.fd"]:
            if os.path.exists(pth):
                ovmf = pth
                break
        extra = []
        if ovmf:
            extra = ["-drive", f"if=pflash,format=raw,readonly=on,file={ovmf}"]
        launch(req.disk_image, ram="512", extra=extra)
        import time as _t
        _t.sleep(10)

    report = full_report(disk_image=None, auto_launch=False)
    text = format_report(report)
    broadcast(text, "chat_response")
    return {"ok": "error" not in report, "report": report, "text": text}


@app.post("/api/test/run")
async def run_test_api():
    from test_runner import run_tests, format_report
    result = run_tests()
    text = format_report(result)
    broadcast(text, "chat_response")
    return {"ok": result.get("ok", False), "text": text}


@app.get("/api/test/detect")
async def detect_test_api():
    from test_runner import detect_test_command
    cmd, desc = detect_test_command()
    return {"cmd": cmd, "description": desc}


@app.post("/api/watcher/start")
async def watcher_start():
    from watcher import start, is_running
    if is_running():
        return {"ok": True, "msg": "udah jalan"}
    ok, msg = start()
    broadcast(f"👁️ Watcher: {msg}", "system")
    return {"ok": ok, "msg": msg}


@app.post("/api/watcher/stop")
async def watcher_stop():
    from watcher import stop
    ok, msg = stop()
    broadcast(f"👁️ Watcher: {msg}", "system")
    return {"ok": ok, "msg": msg}


@app.get("/api/watcher/status")
async def watcher_status():
    from watcher import is_running, get_recent
    return {"running": is_running(), "recent": get_recent(20)}


@app.post("/api/voice/start")
async def voice_start():
    try:
        import voice
        ok = voice.start_recording()
        return {"ok": ok}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/voice/stop")
async def voice_stop():
    try:
        import voice
        wav = voice.stop_recording()
        if not wav:
            return {"ok": False, "error": "no audio"}
        text = voice.transcribe(wav)
        if not text:
            return {"ok": False, "error": "empty transcription"}

        broadcast({"kind": "user_message", "msg": text}, "system")
        broadcast(text, "voice_transcript")

        threading.Thread(
            target=_run_in_thread,
            args=(_do_voice_chat, text),
            daemon=True,
        ).start()
        return {"ok": True, "text": text}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/voice/status")
async def voice_status():
    try:
        import voice
        return {"recording": voice.is_recording()}
    except Exception:
        return {"recording": False}


def _do_voice_chat(text):
    from chat import chat_turn
    import chat_store
    session = chat_store.get_active_session()
    sid = session["id"]
    chat_store.append_message(sid, "user", text)
    history = []
    if getattr(req, 'keep_context', True):
        history = [{"role": m["role"], "content": m["content"]} for m in session["messages"][:-1]]
    response, _ = chat_turn(history, text, focus="chat")
    chat_store.append_message(sid, "assistant", response)
    broadcast(response, "chat_response")




@app.post("/api/vision/analyze")
async def vision_analyze(req: dict):
    """Analisis gambar yang di-upload atau screenshot terbaru."""
    path = req.get("path", "")
    question = req.get("question", "")
    from vision import analyze_image, analyze_screenshot_latest

    if path:
        result = analyze_image(path, question or None)
    else:
        result = analyze_screenshot_latest(question or None)

    broadcast(result, "chat_response")
    return {"ok": True, "result": result}


@app.post("/api/vision/upload")
async def vision_upload(req: dict):
    """Terima gambar base64, simpan, analisis."""
    import base64
    import time as _t
    data_url = req.get("data", "")
    question = req.get("question", "")
    if not data_url.startswith("data:image/"):
        return {"ok": False, "error": "Format salah"}

    try:
        header, b64 = data_url.split(",", 1)
        ext = "png"
        if "jpeg" in header or "jpg" in header: ext = "jpg"
        elif "webp" in header: ext = "webp"

        uploads = Path.home() / ".astrix-agent/uploads"
        uploads.mkdir(parents=True, exist_ok=True)
        fname = f"upload-{_t.strftime('%H%M%S')}.{ext}"
        fpath = uploads / fname
        fpath.write_bytes(base64.b64decode(b64))

        from vision import analyze_image
        result = analyze_image(str(fpath), question or None)
        broadcast(result, "chat_response")
        return {"ok": True, "path": str(fpath), "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}




class TermReq(BaseModel):
    cmd: str
    timeout: int = 60


@app.post("/api/terminal/run")
async def terminal_run(req: TermReq):
    from terminal import run, format_result
    broadcast(f"$ {req.cmd}", "term_in")
    r = run(req.cmd, timeout=req.timeout)
    text = format_result(r)
    broadcast(text, "term_out")
    return {"ok": r.get("ok", False), "result": r, "text": text}


@app.get("/api/personality")
async def get_personality():
    from personality import get
    return {"mode": get()}


@app.post("/api/personality")
async def set_personality_api(req: dict):
    from personality import set_mode
    try:
        mode = set_mode(req.get("mode", "roast"))
        broadcast(f"Personality: {mode.upper()}", "system")
        return {"ok": True, "mode": mode}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/speed")
async def get_speed():
    from speed import is_fast
    return {"fast": is_fast()}


@app.post("/api/speed")
async def set_speed(req: dict):
    from speed import set_fast
    on = bool(req.get("fast", False))
    set_fast(on)
    broadcast("Speed: " + ("🚀 FAST" if on else "🐢 QUALITY"), "system")
    return {"ok": True, "fast": on}


@app.get("/api/user_memory")
async def get_user_memory():
    import user_memory as _um
    d = _um.load()
    return {
        "facts": d.get("facts", []),
        "streak_days": d.get("streak_days", 0),
        "last_seen": d.get("last_seen", 0),
    }


@app.post("/api/user_memory/add")
async def add_user_memory(req: dict = None):
    import user_memory as _um
    fact = (req or {}).get("fact", "")
    if fact:
        _um.add_fact(fact)
        return {"ok": True, "facts": _um.load()["facts"]}
    return {"ok": False}


@app.get("/api/mood")
async def get_mood():
    import mood as _mood
    d = _mood.get()
    from mood import MOODS
    return {
        "mood": d.get("mood"),
        "intensity": d.get("intensity"),
        "streak": d.get("streak", 0),
        "emoji": MOODS.get(d.get("mood"), MOODS["neutral"])["emoji"],
        "desc": MOODS.get(d.get("mood"), MOODS["neutral"])["desc"],
    }


@app.post("/api/mood/set")
async def set_mood_api(req: dict = None):
    import mood as _mood
    m = (req or {}).get("mood", "chill")
    d = _mood.set_mood(m)
    return {"ok": True, "mood": d.get("mood")}


@app.get("/api/model")
async def get_model_api():
    from models import MODELS, all_models, by_provider
    cur = runtime.get_model_key()
    info = MODELS.get(cur) if cur else None
    return {
        "current": cur,
        "info": info,
        "all": all_models(),
        "grouped": by_provider(),
    }


@app.post("/api/model")
async def set_model_api(req: ModelReq):
    try:
        new = runtime.set_model(req.model)
        from models import MODELS
        m = MODELS[new]
        broadcast(f"Model: {m['icon']} {m['label']}", "system")
        return {"ok": True, "model": new, "info": m}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/model/sync")
async def sync_models_api():
    from model_sync import sync_and_save
    n, err = sync_and_save()
    if err:
        return {"ok": False, "error": err}
    import importlib, models
    importlib.reload(models)
    return {"ok": True, "synced": n}

@app.get("/api/checkpoints")
async def checkpoints_api():
    from git_checkpoint import list_checkpoints, is_git_repo
    return {
        "is_git": is_git_repo(),
        "checkpoints": list_checkpoints()[-20:][::-1],
    }


@app.post("/api/checkpoints/rollback")
async def rollback_api(req: dict):
    from git_checkpoint import rollback
    steps = req.get("steps", 1)
    result = rollback(steps=steps)
    if result.get("ok"):
        broadcast(f"Rollback ke {result['hash']}", "system")
    return result


@app.post("/api/checkpoints/save")
async def save_ckpt_api():
    from git_checkpoint import checkpoint
    result = checkpoint(label="manual")
    if result.get("ok") and result.get("hash"):
        broadcast(f"Checkpoint: {result['hash']}", "system")
    return result


@app.get("/api/activity")
async def activity():
    return {
        "activity": get_activity(),
        "total_added": get_totals()["added"],
        "total_removed": get_totals()["removed"],
    }


@app.post("/api/reset")
async def reset():
    clear_state()
    broadcast("State dihapus.", "system")
    return {"ok": True}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    _clients.add(ws)
    try:
        for msg in _log_buffer[-50:]:
            await ws.send_json(msg)
        while True:
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=60)
            except asyncio.TimeoutError:
                await ws.send_json({"kind": "ping", "msg": "", "ts": time.time()})
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(ws)




class AgentReq(BaseModel):
    goal: str
    scope: str
    model: str = ""
    mode: str = "medium"


@app.post("/api/agents/spawn")
async def agents_spawn(req: AgentReq):
    from multi_agent import spawn
    try:
        aid = spawn(req.goal, req.scope, model=req.model or None, mode=req.mode)
        broadcast(f"Agent spawned: {aid} @ {req.scope}", "system")
        return {"ok": True, "agent_id": aid}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/agents/list")
async def agents_list():
    from multi_agent import list_agents
    agents = []
    for a in list_agents():
        agents.append({
            "id": a["id"],
            "goal": a["goal"][:200],
            "scope": a["scope"],
            "status": a["status"],
            "tasks_done": a["tasks_done"],
            "tasks_total": a["tasks_total"],
            "current_task": a["current_task"][:100],
            "log_tail": [x["text"] for x in a["log"][-5:]],
            "result": a.get("result"),
        })
    return {"agents": agents}


@app.post("/api/agents/stop")
async def agents_stop(req: dict):
    from multi_agent import stop
    aid = req.get("agent_id", "")
    ok, msg = stop(aid)
    return {"ok": ok, "msg": msg}


@app.get("/api/agents/{aid}")
async def agents_detail(aid: str):
    from multi_agent import get
    a = get(aid)
    if not a:
        return {"error": "nggak ada"}
    return {
        "id": a["id"], "goal": a["goal"], "scope": a["scope"],
        "status": a["status"], "tasks_done": a["tasks_done"],
        "tasks_total": a["tasks_total"], "current_task": a["current_task"],
        "log": a["log"][-50:], "result": a.get("result"), "error": a.get("error"),
    }


class TermReq(BaseModel):
    cmd: str
    timeout: int = 60


@app.post("/api/terminal/run")
async def terminal_run(req: TermReq):
    from terminal import run, format_result
    broadcast(f"$ {req.cmd}", "term_in")
    r = run(req.cmd, timeout=req.timeout)
    text = format_result(r)
    broadcast(text, "term_out")
    return {"ok": r.get("ok", False), "result": r, "text": text}




@app.get("/api/system")
async def get_system_info():
    """System info — cross-platform: Linux (all distros) / Windows / macOS."""
    import platform, os, time

    os_name = platform.system()
    os_release = platform.release()
    os_display = f"{os_name} {os_release}" if os_name else "Unknown"

    ram_used = ram_total = ram_pct = 0.0
    uptime_sec = 0.0
    gpu = "Unknown"

    try:
        import psutil
        mem = psutil.virtual_memory()
        ram_total = mem.total / (1024**3)
        ram_used = (mem.total - mem.available) / (1024**3)
        ram_pct = mem.percent
        uptime_sec = time.time() - psutil.Process().create_time()
    except ImportError:
        if os_name == "Linux":
            try:
                with open("/proc/meminfo") as f:
                    for line in f:
                        if "MemTotal" in line:
                            ram_total = int(line.split()[1]) / (1024**2)
                        elif "MemAvailable" in line:
                            avail = int(line.split()[1]) / (1024**2)
                ram_used = ram_total - avail
                ram_pct = (ram_used / ram_total * 100) if ram_total > 0 else 0
            except Exception: pass
            try:
                with open("/proc/uptime") as f:
                    uptime_sec = float(f.read().split()[0])
            except Exception: pass
        elif os_name == "Darwin": 
            try:
                import subprocess, re as _re
                total_bytes = int(subprocess.check_output(
                    ["sysctl", "-n", "hw.memsize"], timeout=3).strip())
                ram_total = total_bytes / (1024**3)
                vm = subprocess.check_output(["vm_stat"], text=True, timeout=3)
                free_pages = 0
                page_size = 4096
                for line in vm.splitlines():
                    if "page size of" in line:
                        m = _re.search(r"(\d+)", line)
                        if m: page_size = int(m.group(1))
                    if "Pages free" in line:
                        free_pages = int(line.split(":")[1].strip().rstrip("."))
                ram_used = ram_total - (free_pages * page_size / (1024**3))
                ram_pct = (ram_used / ram_total * 100) if ram_total > 0 else 0
                boot = subprocess.check_output(
                    ["sysctl", "-n", "kern.boottime"], text=True, timeout=3)
                m = _re.search(r"sec = (\d+)", boot)
                if m: uptime_sec = time.time() - int(m.group(1))
            except Exception: pass
        elif os_name == "Windows":
            try:
                import ctypes
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]
                ms = MEMORYSTATUSEX()
                ms.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
                ram_total = ms.ullTotalPhys / (1024**3)
                ram_used = (ms.ullTotalPhys - ms.ullAvailPhys) / (1024**3)
                ram_pct = float(ms.dwMemoryLoad)
                uptime_sec = ctypes.windll.kernel32.GetTickCount64() / 1000.0
            except Exception: pass

    uptime_str = "Unknown"
    if uptime_sec > 0:
        days = int(uptime_sec // 86400)
        hours = int((uptime_sec % 86400) // 3600)
        mins = int((uptime_sec % 3600) // 60)
        secs = int(uptime_sec % 60)
        uptime_str = f"{days}d {hours}h {mins}m {secs}s" if days > 0 else f"{hours}h {mins}m {secs}s"

    try:
        import subprocess
        if os_name == "Linux":
            try:
                out = subprocess.check_output(["lspci"], text=True, timeout=3)
                for line in out.splitlines():
                    if "VGA" in line or "3D controller" in line:
                        gpu = line.split(": ")[1].split(" (")[0]
                        break
            except Exception:
                try:
                    import glob
                    for card in glob.glob("/sys/class/drm/card*/device/vendor"):
                        gpu = "GPU detected (install pciutils for name)"
                        break
                except Exception: pass
        elif os_name == "Darwin":
            try:
                out = subprocess.check_output(
                    ["system_profiler", "SPDisplaysDataType"], text=True, timeout=5)
                for line in out.splitlines():
                    if "Chipset Model:" in line:
                        gpu = line.split(":", 1)[1].strip()
                        break
            except Exception: pass
        elif os_name == "Windows":
            try:
                out = subprocess.check_output(
                    ["wmic", "path", "win32_VideoController", "get", "name"],
                    text=True, timeout=5)
                lines = [l.strip() for l in out.splitlines() if l.strip() and l.strip() != "Name"]
                if lines: gpu = lines[0]
            except Exception: pass
    except Exception: pass

    return {
        "gpu": gpu,
        "ram": f"{ram_used:.1f} GB / {ram_total:.1f} GB",
        "ram_pct": ram_pct,
        "uptime": uptime_str,
        "os": os_display,
    }


@app.get("/api/list-dir")
async def list_dir(path: str = None):
    import os
    if not path:
        path = os.path.expanduser("~")
    
    path = os.path.abspath(path)
    try:
        items = os.listdir(path)
        folders = []
        for item in items:
            full_path = os.path.join(path, item)
            if os.path.isdir(full_path) and not item.startswith('.'):
                folders.append(item)
        folders.sort()
        return {"current_path": path, "folders": folders}
    except Exception as e:
        return {"error": str(e)}



@app.post("/api/fetch-models")
async def fetch_models(req: dict):
    """Deteksi model dari custom OpenAI-compatible endpoint."""
    import urllib.request
    import json
    
    base_url = (req.get("base_url") or "").rstrip("/")
    api_key = req.get("api_key") or ""
    
    if not base_url:
        return {"error": "Base URL kosong"}
    
    url = base_url + "/models"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    
    try:
        request = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode())
        
        models = []
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
            for m in data["data"]:
                if isinstance(m, dict) and "id" in m:
                    models.append(m["id"])
        elif isinstance(data, list):
            for m in data:
                if isinstance(m, dict) and "id" in m:
                    models.append(m["id"])
                elif isinstance(m, str):
                    models.append(m)
        
        models.sort()
        return {"models": models, "count": len(models)}
    except Exception as e:
        return {"error": str(e)}


import subprocess as _sp
import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.dirname(__file__))
try:
    from extensions_1000 import EXTENSIONS as _EXTS
except Exception as _e:
    print("Ext catalog load error:", _e)
    _EXTS = []

def _check_ext_available(ext):
    try:
        if ext["check_type"] == "bin":
            r = _sp.run(["which", ext["check_target"]], capture_output=True, timeout=3)
            return r.returncode == 0
        elif ext["check_type"] == "pyimport":
            r = _sp.run(["python3", "-c", f"import {ext['check_target']}"], capture_output=True, timeout=5)
            return r.returncode == 0
    except Exception:
        return False
    return False

@app.get("/api/extensions/list")
async def ext_list():
    return {"extensions": _EXTS}

@app.get("/api/extensions/status")
async def ext_status():
    status = {}
    for ext in _EXTS:
        status[ext["id"]] = _check_ext_available(ext)
    return {"status": status}

@app.post("/api/extensions/active-prompts")
async def ext_active_prompts(req: dict):
    ids = req.get("ids", [])
    lines = []
    active = []
    for ext in _EXTS:
        if ext["id"] in ids and _check_ext_available(ext):
            lines.append(f"- {ext['name']}: {ext['prompt']}")
            active.append(ext["id"])
    return {"prompts": "\n".join(lines), "active": active}

@app.post("/api/extensions/install-cmd")
async def ext_install_cmd(req: dict):
    ext_id = req.get("id")
    ext = next((e for e in _EXTS if e["id"] == ext_id), None)
    if not ext:
        return {"error": "not found"}
    if ext["check_type"] == "bin":
        cmd = f"sudo pacman -S {ext['install_pkg']}"
    else:
        cmd = f"pip install --user {ext['install_pkg']}"
    return {"cmd": cmd, "pkg": ext["install_pkg"]}


import uuid as _uuid
from threading import Thread as _Thread
import shutil as _shutil

_install_jobs = {}

def _run_install_job(job_id, ext):
    import subprocess as _sp
    jobs = _install_jobs
    jobs[job_id]["status"] = "running"
    output = []
    
    cmds = []
    if ext["check_type"] == "pyimport":
        pip_bin = _shutil.which("pip") or _shutil.which("pip3") or "pip"
        cmds.append([pip_bin, "install", "--user", "--break-system-packages", ext["install_pkg"]])
    else:
        if _shutil.which("pkexec"):
            cmds.append(["pkexec", "pacman", "-S", "--noconfirm", "--needed", ext["install_pkg"]])
        if _shutil.which("sudo"):
            cmds.append(["sudo", "pacman", "-S", "--noconfirm", "--needed", ext["install_pkg"]])
    
    success = False
    for cmd in cmds:
        try:
            output.append(f"▶ Menjalankan: {' '.join(cmd)}\n\n")
            jobs[job_id]["output"] = "".join(output)
            
            proc = _sp.Popen(cmd, stdout=_sp.PIPE, stderr=_sp.STDOUT,
                             text=True, bufsize=1, env={**_os.environ, "DEBIAN_FRONTEND": "noninteractive"})
            for line in proc.stdout:
                output.append(line)
                jobs[job_id]["output"] = "".join(output)
            proc.wait()
            
            if proc.returncode == 0:
                success = True
                break
            else:
                output.append(f"\n⚠ Exit code {proc.returncode}, coba metode lain...\n")
        except FileNotFoundError:
            output.append(f"❌ Command `{cmd[0]}` nggak tersedia di sistem.\n")
            continue
        except Exception as e:
            output.append(f"❌ Error: {e}\n")
            continue
    
    if success:
        verify = _check_ext_available(ext)
        jobs[job_id]["status"] = "success" if verify else "verify_failed"
        if verify:
            jobs[job_id]["output"] += f"\n\n✅ {ext['name']} BERHASIL diinstal & terdeteksi!\n"
        else:
            jobs[job_id]["output"] += f"\n\n⚠ Install sukses tapi tool nggak terdeteksi. Coba restart shell.\n"
    else:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["output"] += "\n\n❌ Semua metode install gagal.\n"
    jobs[job_id]["output"] = "".join(output) if isinstance(jobs[job_id]["output"], list) else jobs[job_id]["output"]


@app.post("/api/extensions/install")
async def ext_install(req: dict):
    ext_id = req.get("id")
    ext = next((e for e in _EXTS if e["id"] == ext_id), None)
    if not ext:
        return {"error": "Extension tidak ditemukan"}
    
    if _check_ext_available(ext):
        return {"status": "already_installed", "ext_id": ext_id}
    
    job_id = str(_uuid.uuid4())[:8]
    _install_jobs[job_id] = {"status": "pending", "output": "", "ext_id": ext_id, "name": ext["name"]}
    _Thread(target=_run_install_job, args=(job_id, ext), daemon=True).start()
    return {"job_id": job_id, "ext_id": ext_id}


@app.get("/api/extensions/install-status/{job_id}")
async def ext_install_status(job_id: str):
    job = _install_jobs.get(job_id)
    if not job:
        return {"error": "Job tidak ditemukan"}
    return job


@app.post("/api/extensions/uninstall")
async def ext_uninstall(req: dict):
    """Uninstall (simple: just remove from active list, no actual system removal)."""
    return {"status": "ok"}



@app.get("/api/test-stream")
async def test_stream():
    """DEBUG: test streaming minimal."""
    import asyncio
    async def gen():
        for i in range(5):
            yield f"data: {i}\n\n"
            await asyncio.sleep(0.5)
    return StreamingResponse(gen(), media_type="text/event-stream")



@app.post("/api/validate-api-key")
async def validate_api_key(req: dict):
    """Cek API key valid atau nggak — hit /models endpoint."""
    import urllib.request, urllib.error, ssl, json as _j
    base_url = (req.get("base_url") or "").rstrip("/")
    api_key = req.get("api_key") or ""
    
    if not base_url:
        return {"valid": False, "error": "Base URL kosong"}
    
    try:
        ctx = ssl._create_unverified_context()
        url = base_url + "/models"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        req_obj = urllib.request.Request(url, headers=headers)
        r = urllib.request.urlopen(req_obj, timeout=10, context=ctx)
        if r.status == 200:
            data = _j.loads(r.read().decode())
            models = data.get("data", data.get("models", [])) if isinstance(data, dict) else []
            return {"valid": True, "models_count": len(models)}
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return {"valid": False, "error": f"Invalid API key (HTTP {e.code})"}
        return {"valid": False, "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"valid": False, "error": str(e)}
    
    return {"valid": False, "error": "Unknown"}



@app.get("/api/workspace/list")
async def workspace_list(path: str = None):
    """List folder & file dalam path — buat file browser."""
    import os
    if not path:
        path = os.path.expanduser("~")
    
    try:
        path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isdir(path):
            return {"error": f"Path bukan folder: {path}"}
        
        items = []
        for entry in os.scandir(path):
            if entry.name.startswith('.'): continue
            try:
                is_dir = entry.is_dir()
                size = 0 if is_dir else entry.stat().st_size
                items.append({
                    "name": entry.name,
                    "is_dir": is_dir,
                    "size": size,
                    "size_human": _format_size(size) if not is_dir else ""
                })
            except (PermissionError, OSError):
                continue
        
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        
        return {
            "current_path": path,
            "parent": os.path.dirname(path) if path != "/" else None,
            "items": items,
            "total": len(items)
        }
    except Exception as e:
        return {"error": str(e)}


def _format_size(size):
    """Format bytes jadi human readable."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024: return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


@app.post("/api/workspace/validate")
async def workspace_validate(req: dict):
    """Validasi folder workspace + hitung statistik."""
    import os
    path = (req.get("path") or "").strip()
    if not path:
        return {"valid": False, "error": "Path kosong"}
    
    try:
        path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isdir(path):
            return {"valid": False, "error": f"Bukan folder: {path}"}
        
        total_files = 0
        total_size = 0
        MAX_SCAN = 5000
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', 'build', '__pycache__', '.venv', 'venv']]
            for f in files:
                if total_files >= MAX_SCAN: break
                try:
                    fp = os.path.join(root, f)
                    total_size += os.path.getsize(fp)
                    total_files += 1
                except: pass
            if total_files >= MAX_SCAN: break
        
        project_type = "Unknown"
        markers = {
            "Makefile": "C/C++ Project",
            "Cargo.toml": "Rust",
            "package.json": "Node.js",
            "requirements.txt": "Python",
            "pyproject.toml": "Python (pyproject)",
            "go.mod": "Go",
            "pom.xml": "Java Maven",
            "build.gradle": "Java Gradle",
            "CMakeLists.txt": "CMake",
            "docker-compose.yml": "Docker",
            "docker-compose.yaml": "Docker",
            ".git": "Git Repo"
        }
        for marker, ptype in markers.items():
            if os.path.exists(os.path.join(path, marker)):
                project_type = ptype
                break
        
        return {
            "valid": True,
            "path": path,
            "name": os.path.basename(path),
            "total_files": total_files,
            "total_size": total_size,
            "size_human": _format_size(total_size),
            "project_type": project_type
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


@app.get("/api/workspace/home")
async def workspace_home():
    """Get home directory + common project folders."""
    import os
    home = os.path.expanduser("~")
    
    suggestions = []
    common = ["Projects", "Documents", "Desktop", "Downloads", "workspace", "code"]
    for name in common:
        p = os.path.join(home, name)
        if os.path.isdir(p):
            suggestions.append({"name": name, "path": p})
    
    try:
        for entry in os.scandir(home):
            if entry.is_dir() and not entry.name.startswith('.'):
                if entry.name in [s["name"] for s in suggestions]: continue
                if os.path.exists(os.path.join(entry.path, '.git')) or \
                   os.path.exists(os.path.join(entry.path, 'Makefile')) or \
                   os.path.exists(os.path.join(entry.path, 'package.json')):
                    suggestions.append({"name": entry.name, "path": entry.path})
    except: pass
    
    return {"home": home, "suggestions": suggestions}



@app.get("/api/memory/list")
async def memory_list():
    try:
        import sys
        sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent / "6_agent"))
        from memory import list_all
        rows = list_all(200)
        return {"memories": [{"category": r[0], "key": r[1], "value": r[2], "updated": r[3]} for r in rows], "count": len(rows)}
    except Exception as e:
        return {"error": str(e), "memories": []}


@app.post("/api/memory/add")
async def memory_add(req: dict):
    try:
        import sys
        sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent / "6_agent"))
        from memory import save_fact
        save_fact(req.get("category", "general"), req.get("key", ""), req.get("value", ""))
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


@app.delete("/api/memory/{category}/{key}")
async def memory_delete(category: str, key: str):
    try:
        import sys
        sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent / "6_agent"))
        from memory import delete_fact
        delete_fact(category, key)
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/memory/clear")
async def memory_clear():
    try:
        import sys
        sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent / "6_agent"))
        from memory import clear_all
        clear_all()
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}



@app.post("/api/multi-agent/run")
async def multi_agent_run(req: dict):
    import sys
    sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent / "6_agent"))
    from multi_agent import run_multi_agent
    import asyncio
    
    goal = req.get("goal", "").strip()
    if not goal:
        return {"error": "Goal kosong"}
    
    max_tasks = req.get("max_tasks", 5)
    base_url = req.get("base_url") or None
    api_key = req.get("api_key") or None
    model = req.get("model") or None
    
    loop = asyncio.get_event_loop()
    logs = []
    def on_log(msg):
        logs.append(msg)
        print(f"[MULTI-API] {msg}", flush=True)
    
    try:
        result = await loop.run_in_executor(
            None, 
            lambda: run_multi_agent(goal, on_log=on_log, max_tasks=max_tasks,
                                    base_url=base_url, api_key=api_key, model=model)
        )
        result["logs"] = logs
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "logs": logs}

if __name__ == "__main__":
    import uvicorn
    print("[SERVER] Starting uvicorn on http://0.0.0.0:8765", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")
