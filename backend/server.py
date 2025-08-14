from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
# MongoDB removed
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
import os
import uuid
import asyncio
import json
import logging
import sys
import socket
import re
import platform
import subprocess
from starlette.staticfiles import StaticFiles
from starlette.responses import FileResponse, HTMLResponse
from ftplib import FTP, error_perm

ROOT_DIR = Path(__file__).parent
PROJECT_ROOT = ROOT_DIR.parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection removed

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Models (MongoDB-related models removed)
# class StatusCheck(BaseModel):
#     id: str = Field(default_factory=lambda: str(uuid.uuid4()))
#     client_name: str
#     timestamp: datetime = Field(default_factory=datetime.utcnow)


# class StatusCheckCreate(BaseModel):
#     client_name: str


@api_router.get("/")
async def root():
    return {"message": "Hello World"}


# -----------------------------
# Helper: compute resource/static path (works in PyInstaller)
# -----------------------------

def resource_path(relative: str) -> Path:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    # When using PyInstaller, sys._MEIPASS points to temp extract dir
    base_path = getattr(sys, '_MEIPASS', None)
    if base_path:
        return Path(base_path) / relative
    return (ROOT_DIR / relative).resolve()


def get_frontend_build_dir() -> Optional[Path]:
    # Check common locations
    candidates = [
        PROJECT_ROOT / "frontend" / "build",
        ROOT_DIR / "frontend_build",           # when bundled via --add-data "frontend/build;frontend_build"
        resource_path("frontend_build"),       # PyInstaller runtime
    ]
    for p in candidates:
        try:
            if p and p.exists() and (p / "index.html").exists():
                return p
        except Exception:
            continue
    return None


# -----------------------------
# WebSocket Signaling for WebRTC
# -----------------------------
class WSClient:
    def __init__(self, websocket: WebSocket, client_id: str, role: str):
        self.websocket = websocket
        self.client_id = client_id
        self.role = role


class Session:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.clients: Dict[str, WSClient] = {}
        self.lock = asyncio.Lock()

    def peers(self) -> List[str]:
        return list(self.clients.keys())


sessions: Dict[str, Session] = {}


def get_or_create_session(session_id: str) -> Session:
    if session_id not in sessions:
        sessions[session_id] = Session(session_id)
    return sessions[session_id]


async def broadcast_peers(session: Session):
    payload = {"type": "peers", "peers": session.peers()}
    for c in list(session.clients.values()):
        try:
            await c.websocket.send_text(json.dumps(payload))
        except Exception:
            pass


@api_router.websocket("/ws/session/{session_id}")
async def ws_session(websocket: WebSocket, session_id: str):
    await websocket.accept()
    client_id: Optional[str] = None
    role = "unknown"
    session = get_or_create_session(session_id)
    try:
        # Expect a join message
        join_raw = await websocket.receive_text()
        join = json.loads(join_raw)
        if join.get("type") != "join":
            await websocket.close(code=1002)
            return
        client_id = join.get("clientId") or str(uuid.uuid4())
        role = join.get("role", "unknown")
        async with session.lock:
            session.clients[client_id] = WSClient(websocket, client_id, role)
        await broadcast_peers(session)

        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            mtype = msg.get("type")

            if mtype in ("sdp-offer", "sdp-answer", "ice-candidate", "text"):
                target = msg.get("to")
                if not target:
                    continue
                target_client = session.clients.get(target)
                if target_client:
                    try:
                        await target_client.websocket.send_text(json.dumps({**msg, "from": client_id}))
                    except Exception:
                        pass
            elif mtype == "leave":
                break
            elif mtype == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            else:
                # ignore
                pass
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logging.exception("WebSocket error: %s", e)
    finally:
        if client_id:
            async with session.lock:
                session.clients.pop(client_id, None)
            if len(session.clients) == 0:
                sessions.pop(session.session_id, None)
        try:
            await broadcast_peers(session)
        except Exception:
            pass


# -----------------------------
# Minimal FTP bridge endpoints (LAN FTP target)
# -----------------------------
class FTPConfig(BaseModel):
    host: str
    port: int = 21
    user: str
    password: str
    passive: bool = True
    cwd: str = "/"


class FTPPath(BaseModel):
    config: FTPConfig
    path: str = "."


def connect_ftp(cfg: FTPConfig) -> FTP:
    try:
        ftp = FTP()
        ftp.connect(cfg.host, cfg.port, timeout=10)
        ftp.login(cfg.user, cfg.password)
        ftp.set_pasv(cfg.passive)
        if cfg.cwd:
            ftp.cwd(cfg.cwd)
        return ftp
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"FTP connect failed: {e}")


@api_router.post("/ftp/list")
async def ftp_list(body: FTPPath):
    def _list():
        ftp = connect_ftp(body.config)
        try:
            ftp.cwd(body.path)
            lines: List[str] = []
            ftp.retrlines('LIST', lines.append)
            return {"entries": lines}
        finally:
            try:
                ftp.quit()
            except Exception:
                pass
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _list)


class FTPUploadQuery(BaseModel):
    config: FTPConfig
    dest_dir: str = "/"
    filename: Optional[str] = None


@api_router.post("/ftp/upload")
async def ftp_upload(config: str, dest_dir: str = "/", file: UploadFile = File(...), filename: Optional[str] = None):
    # config is JSON string due to multipart; parse
    try:
        cfg_dict = json.loads(config)
        cfg = FTPConfig(**cfg_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid config: {e}")

    def _upload():
        ftp = connect_ftp(cfg)
        try:
            ftp.cwd(dest_dir)
            name = filename or file.filename
            if not name:
                raise Exception("Missing filename")
            ftp.storbinary(f"STOR {name}", file.file)
            return {"ok": True, "path": f"{dest_dir}/{name}"}
        finally:
            try:
                ftp.quit()
            except Exception:
                pass
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _upload)


# -----------------------------
# Host info for LAN QR generation
# -----------------------------
PRIVATE_RANGES = [
    re.compile(r"^10\..*"),
    re.compile(r"^192\.168\..*"),
    re.compile(r"^172\.(1[6-9]|2[0-9]|3[0-1])\..*"),
]


def is_private_ipv4(ip: str) -> bool:
    if ip.startswith("127.") or ip.startswith("169.254."):
        return False
    return any(p.match(ip) for p in PRIVATE_RANGES)


def parse_windows_ipconfig(output: str) -> List[str]:
    # Matches lines like: IPv4 Address. . . . . . . . . . . : 192.168.1.23
    ips = re.findall(r"IPv4[^:]*:\s*([0-9\.]+)", output)
    return [ip for ip in ips if is_private_ipv4(ip)]


def parse_unix_ip(output: str) -> List[str]:
    # Parse `ip -4 addr` output
    ips = re.findall(r"inet\s([0-9\.]+)", output)
    return [ip for ip in ips if is_private_ipv4(ip)]


def get_ipv4_candidates() -> List[str]:
    candidates: List[str] = []
    try:
        if platform.system().lower().startswith('win'):
            out = subprocess.check_output(["ipconfig"], text=True, errors='ignore')
            candidates = parse_windows_ipconfig(out)
        else:
            # Prefer `ip -4 addr`, fall back to ifconfig
            try:
                out = subprocess.check_output(["ip", "-4", "addr"], text=True, errors='ignore')
                candidates = parse_unix_ip(out)
            except Exception:
                out = subprocess.check_output(["ifconfig"], text=True, errors='ignore')
                candidates = parse_unix_ip(out)
    except Exception:
        pass

    # Fallback: try UDP trick to discover default route IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if is_private_ipv4(ip) and ip not in candidates:
            candidates.append(ip)
    except Exception:
        pass

    # Deduplicate, preserve order
    seen = set()
    res = []
    for ip in candidates:
        if ip not in seen:
            seen.add(ip)
            res.append(ip)
    return res


@api_router.get("/host-info")
async def host_info():
    port = int(os.environ.get("PORT", 8001))
    ips = get_ipv4_candidates()
    urls = [f"http://{ip}:{port}" for ip in ips]
    return {"port": port, "ips": ips, "urls": urls}


# Include the router in the main app
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)

# -----------------------------
# Static frontend (if build available). This does NOT alter /api routes
# -----------------------------
_frontend_dir = get_frontend_build_dir()
if _frontend_dir:
    # Serve static assets
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="static")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # Let /api handlers handle their routes
        if full_path.startswith("api"):
            raise HTTPException(status_code=404)
        index_file = _frontend_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return HTMLResponse("Frontend build not found", status_code=404)

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)