from fastapi import APIRouter, Request
from pydantic import BaseModel
import sys
import os

# Add 6_agent to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '6_agent')))
from coder_agent import coder

router = APIRouter()

class ScanReq(BaseModel):
    file_path: str

class RemoveReq(BaseModel):
    file_path: str
    pattern: str

class WriteReq(BaseModel):
    file_path: str
    content: str

@router.post("/api/coder/scan")
async def api_scan(req: ScanReq):
    return {"result": coder.scan_bugs(req.file_path)}

@router.post("/api/coder/remove")
async def api_remove(req: RemoveReq):
    return {"result": coder.remove_unused_code(req.file_path, req.pattern)}

@router.post("/api/coder/write")
async def api_write(req: WriteReq):
    return {"result": coder.write_code(req.file_path, req.content)}

@router.post("/api/coder/build")
async def api_build(req: dict = None):
    cmd = (req or {}).get("command", "make -j4")
    return {"result": coder.auto_build(cmd)}
