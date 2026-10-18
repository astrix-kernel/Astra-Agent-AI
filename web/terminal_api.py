import os
import pty
import asyncio
import subprocess
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

@router.websocket("/ws/terminal")
async def terminal_ws(websocket: WebSocket):
    await websocket.accept()
    print("[TERMINAL] WebSocket connected", flush=True)

    cwd = os.environ.get("ASTRIX_WORKSPACE", "").strip()
    if not cwd or not os.path.isdir(cwd):
        cwd = os.path.expanduser("~")
    print(f"[TERMINAL] Starting bash in: {cwd}", flush=True)

    master_fd, slave_fd = pty.openpty()
    
    process = subprocess.Popen(
        ["/bin/bash", "-i"],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd=cwd,
        preexec_fn=os.setsid,
        env={**os.environ, "TERM": "xterm-256color"},
    )
    os.close(slave_fd)

    async def read_from_pty():
        loop = asyncio.get_event_loop()
        while True:
            try:
                data = await loop.run_in_executor(None, os.read, master_fd, 1024)
                if not data: break
                await websocket.send_bytes(data)
            except Exception: break

    async def write_to_pty():
        while True:
            try:
                data = await websocket.receive_bytes()
                os.write(master_fd, data)
            except Exception: break

    try:
        await asyncio.gather(read_from_pty(), write_to_pty())
    except Exception: pass
    finally:
        try: process.terminate()
        except: pass
        try: os.close(master_fd)
        except: pass
