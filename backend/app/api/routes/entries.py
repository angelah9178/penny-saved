"""Authenticated impulse-purchase entry API routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from app.api.dependencies import enforce_trusted_origin, get_current_user
from app.core.time import Clock, get_clock
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.entry import (
    DashboardEntriesResponse,
    EntryCheckInRequest,
    EntryCreateRequest,
    EntryEnvelope,
    EntryUpdateRequest,
)
from app.services.entries import (
    check_in_entry,
    create_entry,
    delete_entry,
    get_entry_detail,
    list_dashboard_entries,
    update_entry,
)
from fastapi import APIRouter, Depends, Response, status
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


@router.get(
    "/{entry_id}",
    operation_id="get_entry_detail",
    response_model=EntryEnvelope,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def get_user_entry(
    entry_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> EntryEnvelope:
    """Return one entry owned by the authenticated user."""
    entry = await get_entry_detail(db, user=user, entry_id=entry_id, clock=clock)
    return EntryEnvelope(entry=entry)


@router.patch(
    "/{entry_id}",
    operation_id="update_entry",
    response_model=EntryEnvelope,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def update_user_entry(
    entry_id: UUID,
    payload: EntryUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    clock: Annotated[Clock, Depends(get_clock)],
    trusted_origin: Annotated[None, Depends(enforce_trusted_origin)],
) -> EntryEnvelope:
    """Update the core details of one owned waiting entry."""
    del trusted_origin
    entry = await update_entry(
        db,
        user=user,
        entry_id=entry_id,
        payload=payload,
        clock=clock,
    )
    return EntryEnvelope(entry=entry)


@router.delete(
    "/{entry_id}",
    operation_id="delete_entry",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def delete_user_entry(
    entry_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    trusted_origin: Annotated[None, Depends(enforce_trusted_origin)],
) -> Response:
    """Delete one owned entry whose stored status remains waiting."""
    del trusted_origin
    await delete_entry(db, user=user, entry_id=entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{entry_id}/check-in",
    operation_id="check_in_entry",
    response_model=EntryEnvelope,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def check_in_user_entry(
    entry_id: UUID,
    payload: EntryCheckInRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    clock: Annotated[Clock, Depends(get_clock)],
    trusted_origin: Annotated[None, Depends(enforce_trusted_origin)],
) -> EntryEnvelope:
    """Resolve one eligible owned waiting entry as saved or purchased."""
    del trusted_origin
    entry = await check_in_entry(
        db,
        user=user,
        entry_id=entry_id,
        payload=payload,
        clock=clock,
    )
    return EntryEnvelope(entry=entry)
