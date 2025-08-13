from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict
import uuid
from datetime import datetime
import asyncio
import json


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection (kept as-is; used by sample endpoints)
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StatusCheckCreate(BaseModel):
    client_name: str


# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Hello World"}


@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.dict()
    status_obj = StatusCheck(**status_dict)
    _ = await db.status_checks.insert_one(status_obj.dict())
    return status_obj


@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]


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
    payload = {
        "type": "peers",
        "peers": session.peers(),
    }
    for c in session.clients.values():
        try:
            await c.websocket.send_text(json.dumps(payload))
        except Exception:
            pass


@api_router.websocket("/ws/session/{session_id}")
async def ws_session(websocket: WebSocket, session_id: str):
    # Accept connection first to receive the join message
    await websocket.accept()
    client_id = None
    role = "unknown"
    session = get_or_create_session(session_id)
    try:
        # Expect a join message first
        join_message = await websocket.receive_text()
        join = json.loads(join_message)
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

            # Simple router: forward signaling messages to a specific target
            if mtype in ("sdp-offer", "sdp-answer", "ice-candidate"):
                target = msg.get("to")
                if not target:
                    continue
                target_client = session.clients.get(target)
                if target_client:
                    try:
                        await target_client.websocket.send_text(json.dumps({
                            **msg,
                            "from": client_id,
                        }))
                    except Exception:
                        pass
            elif mtype == "leave":
                # client requested to leave
                break
            else:
                # ignore unknown
                pass
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logging.exception("WebSocket error: %s", e)
    finally:
        # Cleanup
        if client_id:
            async with session.lock:
                if client_id in session.clients:
                    del session.clients[client_id]
            # If session empty, drop it
            if len(session.clients) == 0:
                sessions.pop(session.session_id, None)
        try:
            await broadcast_peers(session)
        except Exception:
            pass


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()