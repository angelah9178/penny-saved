"""Centralized safe API error handling."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence

from app.core.logging import LOGGER_NAME, REQUEST_ID_HEADER, get_request_id
from app.schemas.common import ErrorDetail, ErrorResponse
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(f"{LOGGER_NAME}.errors")


class ApplicationError(Exception):
    """Expected application failure safe to translate for API clients."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        fields: dict[str, str] | None = None,
    ) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.fields = fields


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    fields: dict[str, str] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Build the canonical error envelope without optional null fields."""
    body = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            fields=fields,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(exclude_none=True),
        headers=headers,
    )


async def application_error_handler(
    request: Request,
    error: ApplicationError,
) -> JSONResponse:
    """Translate an expected application failure."""
    del request
    return error_response(
        status_code=error.status_code,
        code=error.code,
        message=error.message,
        fields=error.fields,
    )


async def request_validation_error_handler(
    request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    """Translate malformed JSON and safe field validation failures."""
    del request
    errors = error.errors()
    if any(item.get("type") == "json_invalid" for item in errors):
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="malformed_json",
            message="The request body contains malformed JSON.",
        )

    fields = _safe_validation_fields(errors)
    return error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="validation_error",
        message="The submitted data is invalid.",
        fields=fields or None,
    )


async def database_unavailable_handler(
    request: Request,
    error: OperationalError,
) -> JSONResponse:
    """Hide database details behind a generic availability response."""
    del request, error
    return error_response(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="service_unavailable",
        message="The service is temporarily unavailable.",
    )


async def unexpected_error_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    """Log an unexpected failure and return a request-correlated safe response."""
    request_id = getattr(request.state, "request_id", None) or get_request_id()
    logger.exception(
        "request.unhandled_exception",
        exc_info=error,
        extra={"request_id": request_id},
    )
    return error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="internal_error",
        message="An unexpected error occurred.",
        headers={REQUEST_ID_HEADER: request_id} if request_id else None,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register all foundation-level exception handlers."""
    app.add_exception_handler(ApplicationError, application_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(OperationalError, database_unavailable_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)


def _safe_validation_fields(
    errors: Sequence[dict[str, object]],
) -> dict[str, str]:
    fields: dict[str, str] = {}
    for error in errors:
        location = error.get("loc")
        if not isinstance(location, tuple):
            continue
        field = _field_name(location)
        if field:
            fields.setdefault(field, _safe_validation_message(str(error.get("type", ""))))
    return fields


def _field_name(location: tuple[object, ...]) -> str | None:
    parts = [str(part) for part in location if part not in {"body", "path", "query", "header"}]
    return ".".join(parts) or None


def _safe_validation_message(error_type: str) -> str:
    if error_type == "missing":
        return "This field is required."
    if "integer" in error_type or error_type.startswith("int_"):
        return "Enter a valid integer."
    if "string" in error_type:
        return "Enter valid text."
    if "uuid" in error_type:
        return "Enter a valid identifier."
    return "Enter a valid value."
