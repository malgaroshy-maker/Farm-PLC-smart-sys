"""WebSocket endpoint for real-time events.

Connect with  ws://<host>/ws
Authentication via:
  1. First message: {"type": "auth", "token": "<token>"} (recommended, keeps tokens out of URLs/logs)
  2. Header: Authorization: Bearer <token> or Sec-WebSocket-Protocol: bearer, <token>
  3. Query param: ?token=<token> (legacy fallback)

On connect the server sends a `state.snapshot`, then pushes events as they happen.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.database import async_session_factory
from app.deps import resolve_token
from app.services.live_state import current_map_state
from app.services.realtime import manager

log = logging.getLogger(__name__)
router = APIRouter(tags=["WebSockets"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = ""):
    auth_token = token

    # Check Authorization header or Sec-WebSocket-Protocol if query token absent
    if not auth_token:
        auth_hdr = websocket.headers.get("authorization")
        if auth_hdr and auth_hdr.lower().startswith("bearer "):
            auth_token = auth_hdr[7:].strip()
        else:
            subprotocol = websocket.headers.get("sec-websocket-protocol")
            if subprotocol:
                parts = [p.strip() for p in subprotocol.split(",")]
                auth_token = parts[-1]

    # If still no token, accept connection and await first auth message
    accepted = False
    if not auth_token:
        await websocket.accept()
        accepted = True
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("type") == "auth":
                auth_token = data.get("token", "")
        except Exception as exc:
            log.warning("WebSocket auth handshake failed: %s", exc)
            await websocket.close(code=4401)
            return

    async with async_session_factory() as db:
        actor = await resolve_token(auth_token, db) if auth_token else None
        if actor is None:
            if accepted:
                await websocket.close(code=4401)
            else:
                await websocket.close(code=4401)
            return

        if not accepted:
            await websocket.accept()
        snapshot = await current_map_state(db)

    await manager.send(websocket, "state.snapshot", snapshot)
    await manager.connect(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await manager.send(websocket, "pong", {})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
