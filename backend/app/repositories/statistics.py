"""User-scoped statistics aggregate persistence operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.models.entry import EntryStatus, ImpulsePurchaseEntry
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class StatisticsAggregate:
    """Three statistics values calculated by one database statement."""

    total_saved_cents: int
    avoided_purchase_count: int
    purchased_count: int


async def aggregate_statistics(
    db: AsyncSession,
    *,
    user_id: UUID,
    range_start: datetime | None,
    range_end: datetime,
) -> StatisticsAggregate:
    """Aggregate one user's resolved entries within a half-open time range."""
    saved_filter = ImpulsePurchaseEntry.status == EntryStatus.SAVED
    purchased_filter = ImpulsePurchaseEntry.status == EntryStatus.PURCHASED
    statement = select(
        func.coalesce(func.sum(ImpulsePurchaseEntry.price_cents).filter(saved_filter), 0),
        func.count().filter(saved_filter),
        func.count().filter(purchased_filter),
    ).where(
        ImpulsePurchaseEntry.user_id == user_id,
        ImpulsePurchaseEntry.status.in_((EntryStatus.SAVED, EntryStatus.PURCHASED)),
        ImpulsePurchaseEntry.checked_in_at < range_end,
    )
    if range_start is not None:
        statement = statement.where(ImpulsePurchaseEntry.checked_in_at >= range_start)

    total_saved_cents, avoided_purchase_count, purchased_count = (await db.execute(statement)).one()
    return StatisticsAggregate(
        total_saved_cents=int(total_saved_cents),
        avoided_purchase_count=int(avoided_purchase_count),
        purchased_count=int(purchased_count),
    )
