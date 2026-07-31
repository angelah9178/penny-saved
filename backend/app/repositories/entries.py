"""Authenticated-user-scoped impulse-purchase entry persistence operations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from app.models.entry import EntryStatus, ImpulsePurchaseEntry
from sqlalchemy import case, literal, select
from sqlalchemy.ext.asyncio import AsyncSession


def add_entry(
    db: AsyncSession,
    *,
    user_id: UUID,
    item_name: str,
    price_cents: int,
    reason_wanted: str,
    created_at: datetime,
    entry_id: UUID | None = None,
) -> ImpulsePurchaseEntry:
    """Stage a new waiting entry owned by the authenticated user."""
    entry = ImpulsePurchaseEntry(
        id=entry_id or uuid4(),
        user_id=user_id,
        item_name=item_name,
        price_cents=price_cents,
        reason_wanted=reason_wanted,
        status=EntryStatus.WAITING,
        comment=None,
        created_at=created_at,
        checked_in_at=None,
        updated_at=created_at,
    )
    db.add(entry)
    return entry


async def list_entries_by_user(
    db: AsyncSession,
    *,
    user_id: UUID,
) -> list[ImpulsePurchaseEntry]:
    """Return only one user's entries in stable per-dashboard-bucket order."""
    waiting_created_at = case(
        (ImpulsePurchaseEntry.status == EntryStatus.WAITING, ImpulsePurchaseEntry.created_at)
    )
    resolved_checked_in_at = case(
        (
            ImpulsePurchaseEntry.status.in_((EntryStatus.SAVED, EntryStatus.PURCHASED)),
            ImpulsePurchaseEntry.checked_in_at,
        )
    )
    waiting_id = case((ImpulsePurchaseEntry.status == EntryStatus.WAITING, ImpulsePurchaseEntry.id))
    resolved_id = case(
        (
            ImpulsePurchaseEntry.status.in_((EntryStatus.SAVED, EntryStatus.PURCHASED)),
            ImpulsePurchaseEntry.id,
        )
    )
    statement = (
        select(ImpulsePurchaseEntry)
        .where(ImpulsePurchaseEntry.user_id == user_id)
        .order_by(
            waiting_created_at.asc().nulls_last(),
            resolved_checked_in_at.desc().nulls_last(),
            waiting_id.asc().nulls_last(),
            resolved_id.desc().nulls_last(),
        )
    )
    return list((await db.scalars(statement)).all())


async def get_entry_by_id(
    db: AsyncSession,
    *,
    user_id: UUID,
    entry_id: UUID,
) -> ImpulsePurchaseEntry | None:
    """Return an entry only when it belongs to the authenticated user."""
    statement = select(ImpulsePurchaseEntry).where(
        ImpulsePurchaseEntry.id == entry_id,
        ImpulsePurchaseEntry.user_id == user_id,
    )
    return await db.scalar(statement)


async def get_entry_for_update(
    db: AsyncSession,
    *,
    user_id: UUID,
    entry_id: UUID,
) -> ImpulsePurchaseEntry | None:
    """Lock and return an entry only when it belongs to the authenticated user."""
    statement = (
        select(ImpulsePurchaseEntry)
        .where(
            ImpulsePurchaseEntry.id == entry_id,
            ImpulsePurchaseEntry.user_id == user_id,
        )
        .with_for_update()
    )
    return await db.scalar(statement)


async def entry_id_exists(db: AsyncSession, *, entry_id: UUID) -> bool:
    """Check only ID existence after an owned lookup misses, without loading entry data."""
    statement = select(literal(True)).where(
        select(ImpulsePurchaseEntry.id).where(ImpulsePurchaseEntry.id == entry_id).exists()
    )
    return bool(await db.scalar(statement))


def update_owned_entry_details(
    *,
    entry: ImpulsePurchaseEntry,
    user_id: UUID,
    item_name: str,
    price_cents: int,
    reason_wanted: str,
    updated_at: datetime,
) -> None:
    """Stage core detail changes after the service has locked and validated the entry."""
    _require_entry_owner(entry, user_id)
    entry.item_name = item_name
    entry.price_cents = price_cents
    entry.reason_wanted = reason_wanted
    entry.updated_at = updated_at


def check_in_owned_entry(
    *,
    entry: ImpulsePurchaseEntry,
    user_id: UUID,
    result: EntryStatus,
    comment: str | None,
    checked_in_at: datetime,
) -> None:
    """Stage an owned entry's already-validated saved or purchased transition."""
    _require_entry_owner(entry, user_id)
    if result not in (EntryStatus.SAVED, EntryStatus.PURCHASED):
        raise ValueError("check-in result must be saved or purchased")

    entry.status = result
    entry.comment = comment
    entry.checked_in_at = checked_in_at
    entry.updated_at = checked_in_at


async def delete_owned_entry(
    db: AsyncSession,
    *,
    entry: ImpulsePurchaseEntry,
    user_id: UUID,
) -> None:
    """Stage deletion after the service has locked and validated the owned entry."""
    _require_entry_owner(entry, user_id)
    await db.delete(entry)


def _require_entry_owner(entry: ImpulsePurchaseEntry, user_id: UUID) -> None:
    if entry.user_id != user_id:
        raise ValueError("entry does not belong to the authenticated user")
