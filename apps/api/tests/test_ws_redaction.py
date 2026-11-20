"""Tests for WebSocket token redaction in Uvicorn access logs."""

import logging

import pytest

from app.main import TokenRedactingFilter


def test_ws_token_redaction_in_message():
    """Verify that ?token=<anything> in record.msg is rewritten to ?token=[REDACTED]."""
    filter_ = TokenRedactingFilter()
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="GET /api/v1/ws?token=secret_ws_jwt_token_12345 HTTP/1.1 101",
        args=(),
        exc_info=None,
    )

    allowed = filter_.filter(record)

    assert allowed is True
    assert record.msg == "GET /api/v1/ws?token=[REDACTED] HTTP/1.1 101"
    assert "secret_ws_jwt_token_12345" not in record.getMessage()


def test_ws_token_redaction_with_args():
    """Verify that ?token=<anything> formatted via args is rewritten to [REDACTED]."""
    filter_ = TokenRedactingFilter()
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:54321", "GET", "/api/v1/ws?token=my_secret_token_abc&param=1", "1.1", 101),
        exc_info=None,
    )

    allowed = filter_.filter(record)

    assert allowed is True
    formatted = record.getMessage()
    assert "?token=[REDACTED]&param=1" in formatted
    assert "my_secret_token_abc" not in formatted


def test_ws_token_redaction_installed_on_uvicorn_access_logger():
    """Verify the filter is installed on the uvicorn.access logger."""
    access_logger = logging.getLogger("uvicorn.access")
    filters = [f for f in access_logger.filters if isinstance(f, TokenRedactingFilter)]
    assert len(filters) >= 1


@pytest.mark.asyncio
async def test_real_uvicorn_ws_connection_logs_no_token(capsys):
    """Real running server test: connect via WebSocket, verify no token appears in any uvicorn logs."""
    import asyncio
    import json
    import socket
    import threading

    import uvicorn
    import websockets

    from app.database import engine
    from app.models.base import Base

    # Ensure tables exist for uvicorn lifespan startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Find free port
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    secret_service_token = "secret_service_jwt_token_XYZ987"
    secret_query_token = "secret_legacy_query_token_ABC123"

    from app.main import app

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=True,
    )
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to be responsive
    for _ in range(50):
        if server.started:
            break
        await asyncio.sleep(0.1)

    try:
        # Case 1: Connect via first-message auth (clean URL without token in query)
        try:
            async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws:
                await ws.send(json.dumps({"type": "auth", "token": secret_service_token}))
                await asyncio.sleep(0.2)
        except Exception:
            pass

        # Case 2: Connect with query token (backstop redaction test)
        try:
            async with websockets.connect(
                f"ws://127.0.0.1:{port}/ws?token={secret_query_token}"
            ) as ws:
                await asyncio.sleep(0.2)
        except Exception:
            pass

        server.should_exit = True
        thread.join(timeout=3.0)

        out, err = capsys.readouterr()
        all_logs = f"{out}\n{err}"

        # Assert no token string appears anywhere in the captured logs
        assert secret_service_token not in all_logs
        assert secret_query_token not in all_logs
        # Assert clean URL connection logged
        assert "WebSocket /ws" in all_logs
        # Assert query token was redacted
        assert "token=[REDACTED]" in all_logs or "?token=[REDACTED]" in all_logs
    finally:
        server.should_exit = True
