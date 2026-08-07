"""Structured application logging and request correlation."""

from __future__ import annotations

import json
import logging
import re
import sys
import traceback
from collections.abc import Mapping, Sequence
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from time import perf_counter
from typing import TextIO
from uuid import UUID, uuid4

from app.core.config import AppEnvironment, LogLevel
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

LOGGER_NAME = "penny_saved"
REQUEST_ID_HEADER = "X-Request-ID"
_request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
_SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)\b(password|passwd|pwd|cookie|set[-_]?cookie|authorization|auth[-_]?token|"
    r"access[-_]?token|refresh[-_]?token|session[-_](?:token|token[-_]hash|digest)|"
    r"database[-_]?url|api[-_]?key|client[-_]?secret|rate[-_]?limit[-_]?key)\b"
    r"(\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_CREDENTIAL_URL_PATTERN = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://[^\s:/?#]+:)([^@\s/]+)(@[^\s]+)")
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)^(?:password|passwd|pwd|cookie|set[-_]?cookie|authorization|auth[-_]?token|"
    r"access[-_]?token|refresh[-_]?token|session[-_](?:token|token[-_]hash|digest)|"
    r"database[-_]?url|api[-_]?key|client[-_]?secret|rate[-_]?limit[-_]?key)$"
)


def redact_sensitive_text(value: str) -> str:
    """Redact labeled authentication material before it reaches structured output."""
    labeled = _SENSITIVE_VALUE_PATTERN.sub(r"\1\2<redacted>", value)
    return _CREDENTIAL_URL_PATTERN.sub(r"\1<redacted>\3", labeled)


def redact_sensitive_value(value: object, *, key: str | None = None) -> object:
    """Recursively sanitize an approved structured log value."""
    if key is not None and _SENSITIVE_KEY_PATTERN.fullmatch(key):
        return "<redacted>"
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, Mapping):
        return {
            str(item_key): redact_sensitive_value(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_sensitive_value(item) for item in value]
    return value


class JsonFormatter(logging.Formatter):
    """Format application records as one safe JSON object per line."""

    def __init__(self, environment: AppEnvironment) -> None:
        super().__init__()
        self.environment = environment.value

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, UTC).isoformat().replace("+00:00", "Z")
        payload: dict[str, object] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "environment": getattr(record, "environment", self.environment),
            "message": redact_sensitive_text(record.getMessage()),
        }
        for field in (
            "request_id",
            "method",
            "route",
            "status",
            "duration_ms",
            "user_id",
            "context",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = redact_sensitive_value(value, key=field)
        if record.exc_info:
            exception_type, _, exception_traceback = record.exc_info
            payload["exception_type"] = exception_type.__name__
            payload["stack_trace"] = [
                {
                    "file": frame.filename,
                    "line": frame.lineno,
                    "function": frame.name,
                }
                for frame in traceback.extract_tb(exception_traceback)
            ]
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def configure_logging(
    environment: AppEnvironment,
    log_level: LogLevel,
    *,
    stream: TextIO | None = None,
) -> logging.Logger:
    """Configure the isolated application logger."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(log_level.value)
    logger.propagate = False

    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()

    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(JsonFormatter(environment))
    logger.addHandler(handler)
    return logger


def get_request_id() -> str | None:
    """Return the request ID associated with the current async context."""
    return _request_id_context.get()


def _set_request_id(request_id: str) -> Token[str | None]:
    return _request_id_context.set(request_id)


def _reset_request_id(token: Token[str | None]) -> None:
    _request_id_context.reset(token)


def _resolve_request_id(scope: Scope) -> str:
    candidate = Headers(scope=scope).get(REQUEST_ID_HEADER)
    if candidate:
        try:
            return str(UUID(candidate))
        except (ValueError, AttributeError):
            pass
    return str(uuid4())


def _route_template(scope: Scope) -> str:
    route = scope.get("route")
    route_path = getattr(route, "path", None)
    if route_path is None:
        return "unmatched"

    root_path = scope.get("root_path", "")
    if root_path and not route_path.startswith(root_path):
        return f"{root_path.rstrip('/')}/{route_path.lstrip('/')}"

    raw_segments = scope.get("path", "").strip("/").split("/")
    route_segments = route_path.strip("/").split("/")
    prefix_length = len(raw_segments) - len(route_segments)
    if prefix_length > 0 and ":path}" not in route_path:
        prefix = "/".join(raw_segments[:prefix_length])
        return f"/{prefix}/{route_path.lstrip('/')}"
    return route_path


class RequestContextMiddleware:
    """Correlate and log each HTTP request without reading sensitive payloads."""

    def __init__(self, app: ASGIApp, environment: AppEnvironment) -> None:
        self.app = app
        self.environment = environment.value
        self.logger = logging.getLogger(f"{LOGGER_NAME}.requests")

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _resolve_request_id(scope)
        scope.setdefault("state", {})["request_id"] = request_id
        token = _set_request_id(request_id)
        started_at = perf_counter()
        response_status = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            duration_ms = round((perf_counter() - started_at) * 1000, 3)
            log_level = _level_for_status(response_status)
            self.logger.log(
                log_level,
                "request.completed",
                extra={
                    "environment": self.environment,
                    "request_id": request_id,
                    "method": scope.get("method", "unknown"),
                    "route": _route_template(scope),
                    "status": response_status,
                    "duration_ms": duration_ms,
                },
            )
            _reset_request_id(token)


def _level_for_status(response_status: int) -> int:
    if response_status >= 500:
        return logging.ERROR
    if response_status >= 400:
        return logging.WARNING
    return logging.INFO
