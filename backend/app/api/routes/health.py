"""Process liveness and database readiness endpoints."""

from __future__ import annotations

import asyncio
from typing import Annotated, Literal

from app.db.session import (
    LIFECYCLE_STATE_KEY,
    ApplicationLifecycleState,
    DependencyReadinessState,
    get_db_session,
    set_dependency_readiness,
)
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


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
    lifecycle_state = getattr(request.app.state, LIFECYCLE_STATE_KEY, None)
    if lifecycle_state is not ApplicationLifecycleState.READY:
        set_dependency_readiness(request.app, DependencyReadinessState.UNAVAILABLE)
        return _unavailable_response()
    try:
        async with asyncio.timeout(request.app.state.settings.health_check_timeout_seconds):
            await session.execute(text("SELECT 1"))
    except (TimeoutError, SQLAlchemyError):
        set_dependency_readiness(request.app, DependencyReadinessState.UNAVAILABLE)
        return _unavailable_response()
    set_dependency_readiness(request.app, DependencyReadinessState.READY)
    return ReadinessResponse(status="ready")


def _unavailable_response() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=ReadinessResponse(status="unavailable").model_dump(),
    )
