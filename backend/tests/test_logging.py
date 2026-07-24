"""Tests for safe structured logging configuration."""

from __future__ import annotations

import json
import logging
from io import StringIO

from app.core.config import AppEnvironment, LogLevel
from app.core.logging import LOGGER_NAME, configure_logging


def test_configured_logger_emits_stable_json_fields() -> None:
    stream = StringIO()
    logger = configure_logging(AppEnvironment.TEST, LogLevel.INFO, stream=stream)

    logger.info(
        "request.completed",
        extra={
            "request_id": "420bd8d8-79e4-4c9c-8d80-eaf03ef5c4c3",
            "method": "GET",
            "route": "/api/health",
            "status": 200,
            "duration_ms": 1.25,
        },
    )

    payload = json.loads(stream.getvalue())
    assert payload == {
        "timestamp": payload["timestamp"],
        "level": "INFO",
        "environment": "test",
        "message": "request.completed",
        "request_id": "420bd8d8-79e4-4c9c-8d80-eaf03ef5c4c3",
        "method": "GET",
        "route": "/api/health",
        "status": 200,
        "duration_ms": 1.25,
    }
    assert payload["timestamp"].endswith("Z")


def test_configured_logger_respects_log_level() -> None:
    stream = StringIO()
    logger = configure_logging(AppEnvironment.PRODUCTION, LogLevel.WARNING, stream=stream)

    logger.info("not emitted")
    logger.warning("emitted")

    payload = json.loads(stream.getvalue())
    assert payload["level"] == "WARNING"
    assert payload["message"] == "emitted"


def test_formatter_omits_unapproved_sensitive_extra_fields() -> None:
    stream = StringIO()
    logger = configure_logging(AppEnvironment.TEST, LogLevel.INFO, stream=stream)

    logger.info(
        "safe message",
        extra={
            "password": "password-secret",
            "cookie": "cookie-secret",
            "authorization": "authorization-secret",
            "database_url": "database-secret",
            "session_digest": "session-secret",
        },
    )

    output = stream.getvalue()
    assert "password-secret" not in output
    assert "cookie-secret" not in output
    assert "authorization-secret" not in output
    assert "database-secret" not in output
    assert "session-secret" not in output


def test_configuration_is_isolated_from_root_logger() -> None:
    root_handlers = list(logging.getLogger().handlers)

    logger = configure_logging(AppEnvironment.TEST, LogLevel.DEBUG, stream=StringIO())

    assert logger.name == LOGGER_NAME
    assert logger.propagate is False
    assert logging.getLogger().handlers == root_handlers


def test_exception_log_includes_safe_stack_without_exception_message() -> None:
    stream = StringIO()
    logger = configure_logging(AppEnvironment.TEST, LogLevel.INFO, stream=stream)

    try:
        raise RuntimeError("exception-message-secret")
    except RuntimeError:
        logger.exception("request.unhandled_exception")

    payload = json.loads(stream.getvalue())
    assert payload["exception_type"] == "RuntimeError"
    assert payload["stack_trace"]
    assert "exception-message-secret" not in stream.getvalue()
