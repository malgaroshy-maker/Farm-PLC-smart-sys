"""WebSocket hub. Envelope per REALTIME_EVENTS.md §3: {type, ts, payload}."""

import json
from typing import Any

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

from app.core.timeutil import utcnow


def envelope(event_type: str, payload: Any) -> str:
    return json.dumps(
        {"type": event_type, "ts": utcnow().isoformat(), "payload": jsonable_encoder(payload)}
    )


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)

    async def send(self, websocket: WebSocket, event_type: str, payload: Any) -> None:
        await websocket.send_text(envelope(event_type, payload))

    async def broadcast(self, event_type: str, payload: Any) -> None:
        if not self.active_connections:
            return
        message = envelope(event_type, payload)
        dead = []
        for ws in list(self.active_connections):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()
