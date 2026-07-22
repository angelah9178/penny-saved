"""Shared API response contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Process-liveness response."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"


class ErrorDetail(BaseModel):
    """Standard safe error detail."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    fields: dict[str, str] | None = None


class ErrorResponse(BaseModel):
    """Envelope returned for every handled HTTP error."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail
