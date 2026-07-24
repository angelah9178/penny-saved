"""Shared API response contracts."""

from __future__ import annotations

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Safe details describing one API error."""

    code: str
    message: str
    fields: dict[str, str] | None = None


class ErrorResponse(BaseModel):
    """Standard envelope returned for every API error."""

    error: ErrorDetail
