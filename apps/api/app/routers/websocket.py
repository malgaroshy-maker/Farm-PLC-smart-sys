"""WebSocket endpoint for real-time events.

Connect with  ws://<host>/ws?token=<access token>
On connect the server sends a `state.snapshot`, then pushes events as they happen.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.database import async_session_factory
from app.deps import resolve_token
from app.services.live_state import build_map_state, load_snapshots
from app.services.realtime import manager

router = APIRouter(tags=["WebSockets"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = ""):
    async with async_session_factory() as db:
        actor = await resolve_token(token, db) if token else None
        if actor is None:
            await websocket.close(code=4401)
            return
        await websocket.accept()
        snapshot = build_map_state(await load_snapshots(db))

    await manager.send(websocket, "state.snapshot", snapshot)
    await manager.connect(websocket)
    try:
        while True:
            if await websocket.receive_text() == "ping":
                await manager.send(websocket, "pong", {})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
