"""Impulse-purchase entry creation and dashboard-list workflows."""

from __future__ import annotations

from uuid import UUID

from app.api.errors import ApplicationError
from app.core.time import Clock, normalize_utc
from app.models.entry import EntryStatus
from app.models.user import User
from app.repositories.entries import (
    add_entry,
    check_in_owned_entry,
    delete_owned_entry,
    entry_id_exists,
    get_entry_by_id,
    get_entry_for_update,
    list_entries_by_user,
    update_owned_entry_comment,
    update_owned_entry_details,
)
from app.schemas.entry import (
    ENTRY_WAIT_PERIOD,
    DashboardBucket,
    DashboardEntriesResponse,
    EntryCheckInRequest,
    EntryCommentUpdateRequest,
    EntryCreateRequest,
    EntryResponse,
    EntryUpdateRequest,
    to_entry_response,
)
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

ENTRY_NOT_FOUND_MESSAGE = "Entry not found."
ENTRY_FORBIDDEN_MESSAGE = "You do not have access to this entry."
INVALID_ENTRY_STATUS_MESSAGE = "Only waiting entries can be edited."
INVALID_DELETE_STATUS_MESSAGE = "Only waiting entries can be deleted."
INVALID_CHECK_IN_STATUS_MESSAGE = "Only waiting entries can be checked in."
INVALID_COMMENT_UPDATE_STATUS_MESSAGE = "Only saved or purchased entry comments can be edited."
EARLY_CHECK_IN_MESSAGE = "This entry is not eligible for check-in yet."


async def create_entry(
    db: AsyncSession,
    *,
    user: User,
    payload: EntryCreateRequest,
    clock: Clock,
) -> EntryResponse:
    """Create and commit one waiting entry owned by the authenticated user."""
    try:
        now = normalize_utc(clock.now())
        entry = add_entry(
            db,
            user_id=user.id,
            item_name=payload.item_name,
            price_cents=payload.price_cents,
            reason_wanted=payload.reason_wanted,
            created_at=now,
        )
        await db.commit()
        return to_entry_response(entry, now)
    except BaseException:
        await db.rollback()
        raise


async def list_dashboard_entries(
    db: AsyncSession,
    *,
    user: User,
    clock: Clock,
) -> DashboardEntriesResponse:
    """Return one user's entries partitioned with one request-scoped clock value."""
    now = normalize_utc(clock.now())
    entries = await list_entries_by_user(db, user_id=user.id)
    buckets: dict[DashboardBucket, list[EntryResponse]] = {bucket: [] for bucket in DashboardBucket}
    for entry in entries:
        response = to_entry_response(entry, now)
        buckets[response.dashboard_bucket].append(response)

    return DashboardEntriesResponse(
        needs_check_in=buckets[DashboardBucket.NEEDS_CHECK_IN],
        waiting=buckets[DashboardBucket.WAITING],
        saved=buckets[DashboardBucket.SAVED],
        purchased=buckets[DashboardBucket.PURCHASED],
    )


async def get_entry_detail(
    db: AsyncSession,
    *,
    user: User,
    entry_id: UUID,
    clock: Clock,
) -> EntryResponse:
    """Return one owned entry or the contractually required safe access error."""
    entry = await get_entry_by_id(db, user_id=user.id, entry_id=entry_id)
    if entry is None:
        await _raise_entry_access_error(db, entry_id=entry_id)
    return to_entry_response(entry, normalize_utc(clock.now()))


async def update_entry(
    db: AsyncSession,
    *,
    user: User,
    entry_id: UUID,
    payload: EntryUpdateRequest,
    clock: Clock,
) -> EntryResponse:
    """Lock and update one owned entry whose stored status remains waiting."""
    try:
        entry = await get_entry_for_update(db, user_id=user.id, entry_id=entry_id)
        if entry is None:
            await _raise_entry_access_error(db, entry_id=entry_id)
        if entry.status is not EntryStatus.WAITING:
            raise _invalid_entry_status_error()

        now = normalize_utc(clock.now())
        update_owned_entry_details(
            entry=entry,
            user_id=user.id,
            item_name=payload.item_name,
            price_cents=payload.price_cents,
            reason_wanted=payload.reason_wanted,
            updated_at=now,
        )
        await db.commit()
        return to_entry_response(entry, now)
    except BaseException:
        await db.rollback()
        raise


async def delete_entry(
    db: AsyncSession,
    *,
    user: User,
    entry_id: UUID,
) -> None:
    """Lock and delete one owned entry whose stored status remains waiting."""
    try:
        entry = await get_entry_for_update(db, user_id=user.id, entry_id=entry_id)
        if entry is None:
            await _raise_entry_access_error(db, entry_id=entry_id)
        if entry.status is not EntryStatus.WAITING:
            raise _invalid_delete_status_error()

        await delete_owned_entry(db, entry=entry, user_id=user.id)
        await db.commit()
    except BaseException:
        await db.rollback()
        raise


async def check_in_entry(
    db: AsyncSession,
    *,
    user: User,
    entry_id: UUID,
    payload: EntryCheckInRequest,
    clock: Clock,
) -> EntryResponse:
    """Atomically resolve one owned waiting entry after its 48-hour wait."""
    try:
        entry = await get_entry_for_update(db, user_id=user.id, entry_id=entry_id)
        if entry is None:
            await _raise_entry_access_error(db, entry_id=entry_id)
        if entry.status is not EntryStatus.WAITING:
            raise _invalid_check_in_status_error()

        now = normalize_utc(clock.now())
        if now < entry.created_at + ENTRY_WAIT_PERIOD:
            raise _early_check_in_error()

        check_in_owned_entry(
            entry=entry,
            user_id=user.id,
            result=EntryStatus(payload.result.value),
            comment=payload.comment,
            checked_in_at=now,
        )
        await db.commit()
        return to_entry_response(entry, now)
    except BaseException:
        await db.rollback()
        raise


async def update_entry_comment(
    db: AsyncSession,
    *,
    user: User,
    entry_id: UUID,
    payload: EntryCommentUpdateRequest,
    clock: Clock,
) -> EntryResponse:
    """Lock and revise only the comment on one owned resolved entry."""
    try:
        entry = await get_entry_for_update(db, user_id=user.id, entry_id=entry_id)
        if entry is None:
            await _raise_entry_access_error(db, entry_id=entry_id)
        if entry.status not in (EntryStatus.SAVED, EntryStatus.PURCHASED):
            raise _invalid_comment_update_status_error()

        now = normalize_utc(clock.now())
        update_owned_entry_comment(
            entry=entry,
            user_id=user.id,
            comment=payload.comment,
            updated_at=now,
        )
        await db.commit()
        return to_entry_response(entry, now)
    except BaseException:
        await db.rollback()
        raise


async def _raise_entry_access_error(db: AsyncSession, *, entry_id: UUID) -> None:
    if await entry_id_exists(db, entry_id=entry_id):
        raise ApplicationError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="forbidden",
            message=ENTRY_FORBIDDEN_MESSAGE,
        )
    raise ApplicationError(
        status_code=status.HTTP_404_NOT_FOUND,
        code="not_found",
        message=ENTRY_NOT_FOUND_MESSAGE,
    )


def _invalid_entry_status_error() -> ApplicationError:
    return ApplicationError(
        status_code=status.HTTP_409_CONFLICT,
        code="invalid_entry_status",
        message=INVALID_ENTRY_STATUS_MESSAGE,
    )


def _invalid_delete_status_error() -> ApplicationError:
    return ApplicationError(
        status_code=status.HTTP_409_CONFLICT,
        code="invalid_entry_status",
        message=INVALID_DELETE_STATUS_MESSAGE,
    )


def _invalid_check_in_status_error() -> ApplicationError:
    return ApplicationError(
        status_code=status.HTTP_409_CONFLICT,
        code="invalid_entry_status",
        message=INVALID_CHECK_IN_STATUS_MESSAGE,
    )


def _invalid_comment_update_status_error() -> ApplicationError:
    return ApplicationError(
        status_code=status.HTTP_409_CONFLICT,
        code="invalid_entry_status",
        message=INVALID_COMMENT_UPDATE_STATUS_MESSAGE,
    )


def _early_check_in_error() -> ApplicationError:
    return ApplicationError(
        status_code=status.HTTP_409_CONFLICT,
        code="early_check_in",
        message=EARLY_CHECK_IN_MESSAGE,
    )
