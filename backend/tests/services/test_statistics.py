"""PostgreSQL cross-layer verification for the statistics summary API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from app.api.dependencies import get_current_user
from app.core.config import AppEnvironment, Settings
from app.core.time import FixedClock, get_clock
from app.db.session import get_db_session
from app.main import create_app
from app.models.entry import EntryStatus, ImpulsePurchaseEntry
from app.models.user import User
from fastapi import FastAPI
from sqlalchemy import event
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

USER_ID = UUID("62000000-0000-4000-8000-000000000001")
OTHER_USER_ID = UUID("62000000-0000-4000-8000-000000000002")
NOW = datetime(2026, 8, 5, 14, 30, tzinfo=UTC)
RANGE_START = datetime(2026, 5, 5, 14, 30, tzinfo=UTC)


@pytest.fixture
async def statistics_database(
    test_database_url: URL,
) -> AsyncIterator[tuple[AsyncEngine, async_sessionmaker[AsyncSession]]]:
    engine = create_async_engine(test_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(ImpulsePurchaseEntry.__table__.delete())
        await db.execute(User.__table__.delete())
        await db.commit()
    try:
        yield engine, factory
    finally:
        async with factory() as db:
            await db.execute(ImpulsePurchaseEntry.__table__.delete())
            await db.execute(User.__table__.delete())
            await db.commit()
        await engine.dispose()


@asynccontextmanager
async def no_database_lifespan(app: FastAPI) -> AsyncIterator[None]:
    del app
    yield


@asynccontextmanager
async def api_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def make_user(*, user_id: UUID, email: str) -> User:
    created_at = RANGE_START - timedelta(days=365)
    return User(
        id=user_id,
        email=email,
        password_hash="argon2-hash-placeholder",
        created_at=created_at,
        updated_at=created_at,
    )


def make_entry(
    *,
    status: EntryStatus,
    checked_in_at: datetime | None,
    price_cents: int = 1_000,
    user_id: UUID = USER_ID,
) -> ImpulsePurchaseEntry:
    created_at = checked_in_at - timedelta(days=2) if checked_in_at else NOW - timedelta(days=3)
    return ImpulsePurchaseEntry(
        id=uuid4(),
        user_id=user_id,
        item_name="Statistics integration entry",
        price_cents=price_cents,
        reason_wanted="Verify complete statistics behavior",
        status=status,
        comment=None,
        created_at=created_at,
        checked_in_at=checked_in_at,
        updated_at=checked_in_at or created_at,
    )


def statistics_app(*, db: AsyncSession, user: User) -> FastAPI:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_url="postgresql+psycopg://app:secret@localhost/penny_saved_test",
    )
    app = create_app(settings, lifespan=no_database_lifespan)

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_current_user() -> User:
        return user

    async def override_clock() -> FixedClock:
        return FixedClock(NOW)

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_clock] = override_clock
    return app


@pytest.mark.asyncio
async def test_summary_api_combines_boundaries_statuses_ownership_and_one_query(
    statistics_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    engine, factory = statistics_database
    async with factory() as db:
        user = make_user(user_id=USER_ID, email="statistics-integration@example.com")
        db.add_all(
            [
                user,
                make_user(user_id=OTHER_USER_ID, email="other-statistics@example.com"),
            ]
        )
        await db.flush()
        db.add_all(
            [
                make_entry(
                    status=EntryStatus.SAVED,
                    checked_in_at=RANGE_START,
                    price_cents=2**31,
                ),
                make_entry(
                    status=EntryStatus.SAVED,
                    checked_in_at=NOW - timedelta(microseconds=1),
                ),
                make_entry(status=EntryStatus.PURCHASED, checked_in_at=RANGE_START),
                make_entry(
                    status=EntryStatus.SAVED,
                    checked_in_at=RANGE_START - timedelta(microseconds=1),
                    price_cents=9_999,
                ),
                make_entry(status=EntryStatus.PURCHASED, checked_in_at=NOW),
                make_entry(
                    status=EntryStatus.SAVED,
                    checked_in_at=RANGE_START,
                    price_cents=9_999,
                    user_id=OTHER_USER_ID,
                ),
                make_entry(status=EntryStatus.WAITING, checked_in_at=None, price_cents=9_999),
            ]
        )
        await db.commit()

        entry_selects: list[str] = []

        def record_entry_select(
            connection: object,
            cursor: object,
            statement: str,
            parameters: object,
            context: object,
            executemany: bool,
        ) -> None:
            del connection, cursor, parameters, context, executemany
            if (
                statement.lstrip().upper().startswith("SELECT")
                and "impulse_purchase_entries" in statement
            ):
                entry_selects.append(statement)

        event.listen(engine.sync_engine, "before_cursor_execute", record_entry_select)
        try:
            async with api_client(statistics_app(db=db, user=user)) as client:
                response = await client.get("/api/stats/summary?range=last_3_months")
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", record_entry_select)

    assert response.status_code == 200
    assert response.json() == {
        "range": "last_3_months",
        "total_saved_cents": 2**31 + 1_000,
        "avoided_purchase_count": 2,
        "purchased_count": 1,
        "opportunity_costs": [],
    }
    assert len(entry_selects) == 1
    assert "sum(" in entry_selects[0].lower()
    assert "count(" in entry_selects[0].lower()


@pytest.mark.asyncio
async def test_summary_api_serializes_empty_statistics_as_json_zeros(
    statistics_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = statistics_database
    async with factory() as db:
        user = make_user(user_id=USER_ID, email="empty-statistics@example.com")
        db.add(user)
        await db.commit()

        async with api_client(statistics_app(db=db, user=user)) as client:
            response = await client.get("/api/stats/summary?range=all_time")

    assert response.status_code == 200
    assert response.json() == {
        "range": "all_time",
        "total_saved_cents": 0,
        "avoided_purchase_count": 0,
        "purchased_count": 0,
        "opportunity_costs": [],
    }
