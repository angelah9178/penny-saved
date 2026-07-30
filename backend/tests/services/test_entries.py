"""PostgreSQL service and API integration tests for entry creation and listing."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import pytest
from app.api.dependencies import get_current_user
from app.core.config import AppEnvironment, Settings
from app.core.time import FixedClock, get_clock
from app.db.session import get_db_session
from app.main import create_app
from app.models.entry import EntryStatus, ImpulsePurchaseEntry
from app.models.session import Session
from app.models.user import User
from app.schemas.entry import EntryCreateRequest
from app.services.entries import create_entry, list_dashboard_entries
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

USER_ID = UUID("50000000-0000-4000-8000-000000000001")
OTHER_USER_ID = UUID("50000000-0000-4000-8000-000000000002")
NOW = datetime(2026, 7, 30, 12, tzinfo=UTC)


def make_user(*, user_id: UUID = USER_ID, email: str = "entries@example.com") -> User:
    return User(
        id=user_id,
        email=email,
        password_hash="argon2-hash-placeholder",
        created_at=NOW,
        updated_at=NOW,
    )


def make_entry(
    *,
    entry_id: UUID,
    user_id: UUID = USER_ID,
    status: EntryStatus = EntryStatus.WAITING,
    created_at: datetime,
    checked_in_at: datetime | None = None,
) -> ImpulsePurchaseEntry:
    return ImpulsePurchaseEntry(
        id=entry_id,
        user_id=user_id,
        item_name=f"Entry {entry_id}",
        price_cents=1_000,
        reason_wanted="Entry service test",
        status=status,
        comment=None,
        created_at=created_at,
        checked_in_at=checked_in_at,
        updated_at=checked_in_at or created_at,
    )


@pytest.fixture
async def entry_database(
    test_database_url: URL,
) -> AsyncIterator[tuple[AsyncEngine, async_sessionmaker[AsyncSession]]]:
    engine = create_async_engine(test_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(Session.__table__.delete())
        await db.execute(ImpulsePurchaseEntry.__table__.delete())
        await db.execute(User.__table__.delete())
        await db.commit()
    try:
        yield engine, factory
    finally:
        async with factory() as db:
            await db.execute(Session.__table__.delete())
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


def entry_app(*, db: AsyncSession, user: User, frontend_origin: str | None = None) -> FastAPI:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_url="postgresql+psycopg://app:secret@localhost/penny_saved_test",
        frontend_origin=frontend_origin,
    )
    app = create_app(settings, lifespan=no_database_lifespan)

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_clock] = lambda: FixedClock(NOW)
    return app


@pytest.mark.asyncio
async def test_create_entry_assigns_owner_waiting_state_and_one_clock_time(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    async with factory() as db:
        user = make_user()
        db.add(user)
        await db.commit()

        response = await create_entry(
            db,
            user=user,
            payload=EntryCreateRequest(
                item_name="  New headphones ",
                price_cents=8_500,
                reason_wanted=" Better noise cancellation ",
            ),
            clock=FixedClock(NOW),
        )

        persisted = await db.get(ImpulsePurchaseEntry, response.id)
        assert persisted is not None
        assert persisted.user_id == USER_ID
        assert persisted.status is EntryStatus.WAITING
        assert persisted.comment is None
        assert persisted.checked_in_at is None
        assert persisted.created_at == persisted.updated_at == NOW
        assert response.item_name == "New headphones"
        assert response.reason_wanted == "Better noise cancellation"
        assert response.dashboard_bucket == "waiting"


@pytest.mark.asyncio
async def test_create_entry_rolls_back_when_persistence_fails(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, factory = entry_database
    async with factory() as db:
        user = make_user()
        db.add(user)
        await db.commit()

        def fail_add(*args: object, **kwargs: object) -> None:
            del args, kwargs
            raise RuntimeError("injected entry failure")

        monkeypatch.setattr("app.services.entries.add_entry", fail_add)
        with pytest.raises(RuntimeError, match="injected entry failure"):
            await create_entry(
                db,
                user=user,
                payload=EntryCreateRequest(
                    item_name="Headphones",
                    price_cents=8_500,
                    reason_wanted="Better noise cancellation",
                ),
                clock=FixedClock(NOW),
            )

        assert await db.scalar(select(func.count()).select_from(ImpulsePurchaseEntry)) == 0


@dataclass
class CountingClock:
    calls: int = 0

    def now(self) -> datetime:
        self.calls += 1
        return NOW


@pytest.mark.asyncio
async def test_list_partitions_only_owned_entries_with_one_clock_read(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    async with factory() as db:
        user = make_user()
        other_user = make_user(user_id=OTHER_USER_ID, email="other-entries@example.com")
        db.add_all(
            [
                user,
                other_user,
                make_entry(
                    entry_id=UUID("60000000-0000-4000-8000-000000000001"),
                    created_at=NOW - timedelta(hours=48, microseconds=-1),
                ),
                make_entry(
                    entry_id=UUID("60000000-0000-4000-8000-000000000002"),
                    created_at=NOW - timedelta(hours=48),
                ),
                make_entry(
                    entry_id=UUID("60000000-0000-4000-8000-000000000003"),
                    status=EntryStatus.SAVED,
                    created_at=NOW - timedelta(days=3),
                    checked_in_at=NOW - timedelta(hours=1),
                ),
                make_entry(
                    entry_id=UUID("60000000-0000-4000-8000-000000000004"),
                    status=EntryStatus.PURCHASED,
                    created_at=NOW - timedelta(days=3),
                    checked_in_at=NOW - timedelta(minutes=30),
                ),
                make_entry(
                    entry_id=UUID("60000000-0000-4000-8000-000000000005"),
                    user_id=OTHER_USER_ID,
                    created_at=NOW - timedelta(days=5),
                ),
            ]
        )
        await db.commit()
        clock = CountingClock()

        response = await list_dashboard_entries(db, user=user, clock=clock)

        assert clock.calls == 1
        assert len(response.waiting) == 1
        assert len(response.needs_check_in) == 1
        assert len(response.saved) == 1
        assert len(response.purchased) == 1
        returned_ids = {
            entry.id
            for bucket in (
                response.waiting,
                response.needs_check_in,
                response.saved,
                response.purchased,
            )
            for entry in bucket
        }
        assert UUID("60000000-0000-4000-8000-000000000005") not in returned_ids


@pytest.mark.asyncio
async def test_list_returns_all_empty_arrays_for_user_without_entries(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    async with factory() as db:
        user = make_user()
        db.add(user)
        await db.commit()

        response = await list_dashboard_entries(db, user=user, clock=FixedClock(NOW))

        assert response.model_dump() == {
            "needs_check_in": [],
            "waiting": [],
            "saved": [],
            "purchased": [],
        }


@pytest.mark.asyncio
async def test_entry_api_creates_then_lists_entry_without_changing_status(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    async with factory() as db:
        user = make_user()
        db.add(user)
        await db.commit()
        app = entry_app(db=db, user=user)

        async with api_client(app) as client:
            created = await client.post(
                "/api/entries",
                json={
                    "item_name": " New headphones ",
                    "price_cents": 8_500,
                    "reason_wanted": " Better noise cancellation ",
                },
            )
            listed = await client.get("/api/entries")

        assert created.status_code == 201
        assert created.json()["entry"]["status"] == "waiting"
        assert created.json()["entry"]["dashboard_bucket"] == "waiting"
        assert listed.status_code == 200
        assert listed.json()["waiting"] == [created.json()["entry"]]
        assert listed.json()["needs_check_in"] == []
        assert listed.json()["saved"] == []
        assert listed.json()["purchased"] == []


@pytest.mark.asyncio
async def test_entry_api_rejects_invalid_payload_without_persistence(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    async with factory() as db:
        user = make_user()
        db.add(user)
        await db.commit()
        app = entry_app(db=db, user=user)

        async with api_client(app) as client:
            response = await client.post(
                "/api/entries",
                json={
                    "item_name": " ",
                    "price_cents": 19.99,
                    "reason_wanted": "Reason",
                    "status": "saved",
                },
            )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
        assert await db.scalar(select(func.count()).select_from(ImpulsePurchaseEntry)) == 0


@pytest.mark.asyncio
async def test_entry_api_requires_authentication_for_create_and_list(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    async with factory() as db:
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_url="postgresql+psycopg://app:secret@localhost/penny_saved_test",
        )
        app = create_app(settings, lifespan=no_database_lifespan)

        async def override_db_session() -> AsyncIterator[AsyncSession]:
            yield db

        app.dependency_overrides[get_db_session] = override_db_session
        app.dependency_overrides[get_clock] = lambda: FixedClock(NOW)
        async with api_client(app) as client:
            created = await client.post(
                "/api/entries",
                json={
                    "item_name": "Headphones",
                    "price_cents": 8_500,
                    "reason_wanted": "Better noise cancellation",
                },
            )
            listed = await client.get("/api/entries")

        assert created.status_code == 401
        assert listed.status_code == 401
        assert created.json()["error"]["code"] == "unauthorized"
        assert listed.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_entry_create_rejects_untrusted_browser_origin(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    async with factory() as db:
        user = make_user()
        db.add(user)
        await db.commit()
        app = entry_app(db=db, user=user, frontend_origin="https://penny-saved.example")

        async with api_client(app) as client:
            response = await client.post(
                "/api/entries",
                headers={"Origin": "https://evil.example"},
                json={
                    "item_name": "Headphones",
                    "price_cents": 8_500,
                    "reason_wanted": "Better noise cancellation",
                },
            )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "forbidden"
        assert await db.scalar(select(func.count()).select_from(ImpulsePurchaseEntry)) == 0
