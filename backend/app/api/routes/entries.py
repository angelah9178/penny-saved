"""Authenticated impulse-purchase entry API routes."""

from __future__ import annotations

from typing import Annotated

from app.api.dependencies import enforce_trusted_origin, get_current_user
from app.core.time import Clock, get_clock
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.entry import DashboardEntriesResponse, EntryCreateRequest, EntryEnvelope
from app.services.entries import create_entry, list_dashboard_entries
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/entries", tags=["entries"])


@router.post(
    "",
    operation_id="create_entry",
    response_model=EntryEnvelope,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def create_user_entry(
    payload: EntryCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    clock: Annotated[Clock, Depends(get_clock)],
    trusted_origin: Annotated[None, Depends(enforce_trusted_origin)],
) -> EntryEnvelope:
    """Create a waiting entry for the authenticated user."""
    del trusted_origin
    entry = await create_entry(db, user=user, payload=payload, clock=clock)
    return EntryEnvelope(entry=entry)


@router.get(
    "",
    operation_id="list_dashboard_entries",
    response_model=DashboardEntriesResponse,
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
async def list_user_entries(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> DashboardEntriesResponse:
    """Return the authenticated user's four dashboard entry buckets."""
    return await list_dashboard_entries(db, user=user, clock=clock)
