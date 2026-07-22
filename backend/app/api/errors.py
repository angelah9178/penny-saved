"""Standard API errors and exception handlers."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """An expected error safe to expose through the API contract."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        fields: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.fields = fields


def error_content(code: str, message: str, fields: dict[str, str] | None = None) -> dict[str, Any]:
    """Build the standard JSON-safe error envelope."""
    detail: dict[str, Any] = {"code": code, "message": message}
    if fields:
        detail["fields"] = fields
    return {"error": detail}


async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_content(exc.code, exc.message, exc.fields),
    )


async def validation_error_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = exc.errors()
    if any(error.get("type") == "json_invalid" for error in errors):
        return JSONResponse(
            status_code=400,
            content=error_content("malformed_json", "The request body is not valid JSON."),
        )

    fields: dict[str, str] = {}
    for error in errors:
        location = error.get("loc", ())
        field = ".".join(str(part) for part in location if part not in {"body", "query", "path"})
        if field:
            fields.setdefault(field, "Invalid value.")
    return JSONResponse(
        status_code=422,
        content=error_content(
            "validation_error",
            "One or more fields are invalid.",
            fields or None,
        ),
    )


async def http_error_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    messages = {
        404: ("not_found", "The requested resource was not found."),
        405: ("method_not_allowed", "The request method is not allowed."),
    }
    code, message = messages.get(
        exc.status_code,
        ("http_error", "The request could not be completed."),
    )
    return JSONResponse(status_code=exc.status_code, content=error_content(code, message))


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unavailable")
    logger.exception(
        "unexpected_request_error",
        exc_info=exc,
        extra={"request_id": request_id},
    )
    return JSONResponse(
        status_code=500,
        content=error_content("internal_server_error", "An unexpected error occurred."),
        headers={"X-Request-ID": request_id},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Install handlers in one place so all routes share the same contract."""
    app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unexpected_error_handler)
