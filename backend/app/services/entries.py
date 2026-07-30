"""Impulse-purchase entry creation and dashboard-list workflows."""

from __future__ import annotations

from app.core.time import Clock, normalize_utc
from app.models.user import User
from app.repositories.entries import add_entry, list_entries_by_user
from app.schemas.entry import (
    DashboardBucket,
    DashboardEntriesResponse,
    EntryCreateRequest,
    EntryResponse,
    to_entry_response,
)
from sqlalchemy.ext.asyncio import AsyncSession


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
