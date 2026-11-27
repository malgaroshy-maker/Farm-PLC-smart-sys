"""WebSocket hub. Envelope per REALTIME_EVENTS.md §3: {type, ts, payload}."""

import asyncio
import json
from contextlib import suppress
from typing import Any

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

from app.core.timeutil import utcnow

SEND_TIMEOUT_SEC = 3.0


def envelope(event_type: str, payload: Any) -> str:
    return json.dumps(
        {"type": event_type, "ts": utcnow().isoformat(), "payload": jsonable_encoder(payload)}
    )


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: set[WebSocket] = set()
        self._users: dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, user_id: str | None = None) -> None:
        self.active_connections.add(websocket)
        if user_id:
            self._users[websocket] = user_id

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)
        self._users.pop(websocket, None)

    async def close_user(self, user_id: str) -> None:
        """End every live connection of a user whose sign-in is no longer valid."""
        for ws in [w for w, uid in self._users.items() if uid == user_id]:
            self.disconnect(ws)
            with suppress(Exception):
                await asyncio.wait_for(ws.close(code=4401), SEND_TIMEOUT_SEC)

    async def send(self, websocket: WebSocket, event_type: str, payload: Any) -> None:
        await websocket.send_text(envelope(event_type, payload))

    async def broadcast(self, event_type: str, payload: Any) -> None:
        if not self.active_connections:
            return
        message = envelope(event_type, payload)
        targets = list(self.active_connections)
        results = await asyncio.gather(
            *(asyncio.wait_for(ws.send_text(message), SEND_TIMEOUT_SEC) for ws in targets),
            return_exceptions=True,
        )
        for ws, result in zip(targets, results, strict=True):
            if isinstance(result, BaseException):
                self.disconnect(ws)
                with suppress(Exception):
                    await asyncio.wait_for(ws.close(code=1011), 1.0)


manager = ConnectionManager()
