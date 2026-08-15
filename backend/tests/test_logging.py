"""Tests for safe structured logging configuration."""

from __future__ import annotations

import json
import logging
from io import StringIO

from app.core.config import AppEnvironment, LogFormat, LogLevel
from app.core.logging import LOGGER_NAME, configure_logging, redact_sensitive_value


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
        "event": "request.completed",
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
    assert payload["event"] == "emitted"


def test_text_log_format_is_readable_and_preserves_stable_fields() -> None:
    stream = StringIO()
    logger = configure_logging(
        AppEnvironment.DEVELOPMENT,
        LogLevel.INFO,
        log_format=LogFormat.TEXT,
        stream=stream,
    )

    logger.info(
        "request.completed",
        extra={"request_id": "safe-id", "method": "GET", "route": "/api/health"},
    )

    output = stream.getvalue()
    assert 'environment="development"' in output
    assert 'event="request.completed"' in output
    assert 'request_id="safe-id"' in output
    assert 'route="/api/health"' in output


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


def test_formatter_redacts_labeled_authentication_material_in_messages() -> None:
    stream = StringIO()
    logger = configure_logging(AppEnvironment.TEST, LogLevel.INFO, stream=stream)

    logger.warning(
        "password=plain-secret Cookie:cookie-secret "
        "Set-Cookie=session-secret authorization=bearer-secret "
        "session_token_hash=digest-secret"
    )

    output = stream.getvalue()
    for secret in (
        "plain-secret",
        "cookie-secret",
        "session-secret",
        "bearer-secret",
        "digest-secret",
    ):
        assert secret not in output
    assert output.count("<redacted>") == 5


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


def test_recursive_context_redacts_nested_secrets_and_credential_urls() -> None:
    stream = StringIO()
    logger = configure_logging(AppEnvironment.TEST, LogLevel.INFO, stream=stream)
    secrets = {
        "password": "nested-password-secret",
        "Authorization": "Bearer nested-authorization-secret",
        "database_url": "postgresql://user:database-password@database/app",
        "rate_limit_key": "rate-limit-key-secret",
        "api_key": "api-key-secret",
    }

    logger.warning(
        "safe event",
        extra={
            "context": {
                "request": secrets,
                "items": [
                    {"cookie": "nested-cookie-secret"},
                    "database=postgresql://user:url-password@database/app",
                ],
            }
        },
    )

    payload = json.loads(stream.getvalue())
    output = stream.getvalue()
    for secret in (
        "nested-password-secret",
        "nested-authorization-secret",
        "database-password",
        "rate-limit-key-secret",
        "api-key-secret",
        "nested-cookie-secret",
        "url-password",
    ):
        assert secret not in output
    assert payload["context"]["request"]["password"] == "<redacted>"
    assert payload["context"]["items"][1] == ("database=postgresql://user:<redacted>@database/app")


def test_redaction_preserves_safe_values_and_does_not_mutate_input() -> None:
    original = {
        "request_id": "safe-id",
        "status": 401,
        "details": ["password=secret", {"reason": "safe explanation"}],
    }

    redacted = redact_sensitive_value(original)

    assert original["details"][0] == "password=secret"
    assert redacted == {
        "request_id": "safe-id",
        "status": 401,
        "details": ["password=<redacted>", {"reason": "safe explanation"}],
    }


def test_multiline_and_quoted_labeled_values_are_redacted() -> None:
    stream = StringIO()
    logger = configure_logging(AppEnvironment.TEST, LogLevel.INFO, stream=stream)

    logger.warning(
        "password=\"secret with spaces\"\nclient_secret: 'another secret'\napi_key=final-secret"
    )

    output = stream.getvalue()
    assert "secret with spaces" not in output
    assert "another secret" not in output
    assert "final-secret" not in output
    assert output.count("<redacted>") == 3
