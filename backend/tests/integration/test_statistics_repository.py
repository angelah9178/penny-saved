"""PostgreSQL integration tests for the statistics aggregate repository."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from app.models.entry import EntryStatus, ImpulsePurchaseEntry
from app.models.user import User
from app.repositories.statistics import StatisticsAggregate, aggregate_statistics
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

USER_ID = UUID("51000000-0000-4000-8000-000000000001")
OTHER_USER_ID = UUID("51000000-0000-4000-8000-000000000002")
START = datetime(2026, 5, 1, 12, tzinfo=UTC)
END = datetime(2026, 8, 1, 12, tzinfo=UTC)


@pytest.fixture
async def db(test_database_url: URL) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(test_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(ImpulsePurchaseEntry.__table__.delete())
        await session.execute(User.__table__.delete())
        session.add_all(
            [
                User(
                    id=USER_ID,
                    email="statistics-owner@example.com",
                    password_hash="argon2-hash-placeholder",
                    created_at=START,
                    updated_at=START,
                ),
                User(
                    id=OTHER_USER_ID,
                    email="other-statistics-owner@example.com",
                    password_hash="argon2-hash-placeholder",
                    created_at=START,
                    updated_at=START,
                ),
            ]
        )
        await session.commit()
        try:
            yield session
        finally:
            await session.rollback()
            await session.execute(ImpulsePurchaseEntry.__table__.delete())
            await session.execute(User.__table__.delete())
            await session.commit()
    await engine.dispose()


def make_entry(
    *,
    status: EntryStatus,
    checked_in_at: datetime | None,
    price_cents: int = 1_000,
    user_id: UUID = USER_ID,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> ImpulsePurchaseEntry:
    created = created_at or START - timedelta(days=30)
    return ImpulsePurchaseEntry(
        id=uuid4(),
        user_id=user_id,
        item_name="Statistics test entry",
        price_cents=price_cents,
        reason_wanted="Verify aggregate behavior",
        status=status,
        comment=None,
        created_at=created,
        checked_in_at=checked_in_at,
        updated_at=updated_at or checked_in_at or created,
    )


@pytest.mark.asyncio
async def test_empty_statistics_aggregate_returns_zeros(db: AsyncSession) -> None:
    result = await aggregate_statistics(
        db,
        user_id=USER_ID,
        range_start=START,
        range_end=END,
    )

    assert result == StatisticsAggregate(0, 0, 0)


@pytest.mark.asyncio
async def test_aggregate_applies_status_ownership_and_half_open_boundaries(
    db: AsyncSession,
) -> None:
    db.add_all(
        [
            make_entry(status=EntryStatus.SAVED, checked_in_at=START, price_cents=2**31),
            make_entry(status=EntryStatus.SAVED, checked_in_at=END - timedelta(microseconds=1)),
            make_entry(status=EntryStatus.PURCHASED, checked_in_at=START),
            make_entry(status=EntryStatus.SAVED, checked_in_at=START - timedelta(microseconds=1)),
            make_entry(status=EntryStatus.PURCHASED, checked_in_at=END),
            make_entry(
                status=EntryStatus.SAVED,
                checked_in_at=START,
                price_cents=9_999,
                user_id=OTHER_USER_ID,
            ),
            make_entry(status=EntryStatus.WAITING, checked_in_at=None, price_cents=9_999),
        ]
    )
    await db.flush()

    result = await aggregate_statistics(
        db,
        user_id=USER_ID,
        range_start=START,
        range_end=END,
    )

    assert result == StatisticsAggregate(2**31 + 1_000, 2, 1)


@pytest.mark.asyncio
async def test_aggregate_uses_checked_in_at_instead_of_other_timestamps(
    db: AsyncSession,
) -> None:
    db.add_all(
        [
            make_entry(
                status=EntryStatus.SAVED,
                checked_in_at=START + timedelta(days=1),
                created_at=START - timedelta(days=365),
                updated_at=END + timedelta(days=365),
            ),
            make_entry(
                status=EntryStatus.SAVED,
                checked_in_at=START - timedelta(days=1),
                created_at=START - timedelta(days=365),
                updated_at=START + timedelta(hours=1),
            ),
        ]
    )
    await db.flush()

    assert await aggregate_statistics(
        db,
        user_id=USER_ID,
        range_start=START,
        range_end=END,
    ) == StatisticsAggregate(1_000, 1, 0)


@pytest.mark.asyncio
async def test_all_time_has_no_start_but_still_excludes_the_end(db: AsyncSession) -> None:
    db.add_all(
        [
            make_entry(
                status=EntryStatus.SAVED,
                checked_in_at=START - timedelta(days=365),
                created_at=START - timedelta(days=730),
            ),
            make_entry(status=EntryStatus.PURCHASED, checked_in_at=END),
        ]
    )
    await db.flush()

    assert await aggregate_statistics(
        db,
        user_id=USER_ID,
        range_start=None,
        range_end=END,
    ) == StatisticsAggregate(1_000, 1, 0)
