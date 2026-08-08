"""Process liveness and database readiness endpoints."""

from __future__ import annotations

import asyncio
from typing import Annotated, Literal

from app.core.metrics import MetricsRegistry
from app.db.session import get_db_session
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

READINESS_TIMEOUT_SECONDS = 2.0


class HealthResponse(BaseModel):
    """Stable process-liveness response contract."""

    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    """Stable database-readiness response contract."""

    status: Literal["ready", "unavailable"]


router = APIRouter(tags=["health"])


@router.get(
    "/health",
    operation_id="get_health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
)
async def get_health() -> HealthResponse:
    """Report that the application process can serve HTTP requests."""
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    operation_id="get_readiness",
    response_model=ReadinessResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ReadinessResponse,
            "description": "PostgreSQL is unavailable.",
        }
    },
)
async def get_readiness(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReadinessResponse | JSONResponse:
    """Report whether PostgreSQL can serve database-backed requests."""
    try:
        async with asyncio.timeout(READINESS_TIMEOUT_SECONDS):
            await session.execute(text("SELECT 1"))
    except (TimeoutError, SQLAlchemyError):
        _metrics_registry(request).set_readiness(False)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ReadinessResponse(status="unavailable").model_dump(),
        )
    _metrics_registry(request).set_readiness(True)
    return ReadinessResponse(status="ready")


def _metrics_registry(request: Request) -> MetricsRegistry:
    return request.app.state.metrics_registry
