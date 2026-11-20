"""Tests for WebSocket token redaction in Uvicorn access logs."""

import logging

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
