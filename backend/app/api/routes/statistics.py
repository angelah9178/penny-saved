"""Authenticated statistics summary API routes."""

from __future__ import annotations

from typing import Annotated

from app.api.dependencies import get_current_user
from app.api.errors import ApplicationError
from app.core.time import Clock, get_clock
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.statistics import StatisticsRange, StatisticsSummaryResponse
from app.services.statistics import get_statistics_summary
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/stats", tags=["statistics"])


async def get_statistics_range(
    request: Request,
    selected_range: Annotated[StatisticsRange, Query(alias="range")],
) -> StatisticsRange:
    """Require exactly one supported statistics range query value."""
    if len(request.query_params.getlist("range")) != 1:
        raise ApplicationError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message="The submitted data is invalid.",
            fields={"range": "Provide exactly one range."},
        )
    return selected_range


@router.get(
    "/summary",
    operation_id="get_statistics_summary",
    response_model=StatisticsSummaryResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
async def get_user_statistics_summary(
    selected_range: Annotated[StatisticsRange, Depends(get_statistics_range)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> StatisticsSummaryResponse:
    """Return aggregate statistics for the authenticated user and selected range."""
    return await get_statistics_summary(
        db,
        user_id=user.id,
        selected_range=selected_range,
        clock=clock,
    )
