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
from app.services.entries import create_entry, get_entry_detail, list_dashboard_entries
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
    user_id = user.id
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_url="postgresql+psycopg://app:secret@localhost/penny_saved_test",
        frontend_origin=frontend_origin,
    )
    app = create_app(settings, lifespan=no_database_lifespan)

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_current_user() -> User:
        current_user = await db.get(User, user_id)
        assert current_user is not None
        return current_user

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_current_user] = override_current_user
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
async def test_entry_api_requires_authentication_for_every_entry_action(
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
        entry_id = UUID("70000000-0000-4000-8000-000000000099")
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
            detail = await client.get(f"/api/entries/{entry_id}")
            updated = await client.patch(
                f"/api/entries/{entry_id}",
                json={
                    "item_name": "Headphones",
                    "price_cents": 9_000,
                    "reason_wanted": "Updated reason",
                },
            )
            deleted = await client.delete(f"/api/entries/{entry_id}")

        for response in (created, listed, detail, updated, deleted):
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "unauthorized"


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


@pytest.mark.asyncio
async def test_entry_detail_api_returns_complete_owned_entry(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    entry_id = UUID("70000000-0000-4000-8000-000000000001")
    async with factory() as db:
        user = make_user()
        db.add_all([user, make_entry(entry_id=entry_id, created_at=NOW)])
        await db.commit()
        app = entry_app(db=db, user=user)

        async with api_client(app) as client:
            response = await client.get(f"/api/entries/{entry_id}")

        assert response.status_code == 200
        assert response.json()["entry"]["id"] == str(entry_id)
        assert response.json()["entry"]["status"] == "waiting"
        assert "updated_at" in response.json()["entry"]
        assert "user_id" not in response.text


@pytest.mark.asyncio
async def test_entry_detail_service_uses_current_clock_for_eligible_waiting_entry(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    entry_id = UUID("70000000-0000-4000-8000-000000000002")
    async with factory() as db:
        user = make_user()
        db.add_all(
            [
                user,
                make_entry(
                    entry_id=entry_id,
                    created_at=NOW - timedelta(hours=48),
                ),
            ]
        )
        await db.commit()

        response = await get_entry_detail(
            db,
            user=user,
            entry_id=entry_id,
            clock=FixedClock(NOW),
        )

        assert response.status is EntryStatus.WAITING
        assert response.dashboard_bucket == "needs_check_in"


@pytest.mark.asyncio
@pytest.mark.parametrize("age", [timedelta(hours=1), timedelta(hours=48)])
async def test_entry_update_api_edits_waiting_and_eligible_waiting_entries(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    age: timedelta,
) -> None:
    _, factory = entry_database
    entry_id = UUID("70000000-0000-4000-8000-000000000003")
    async with factory() as db:
        user = make_user()
        original = make_entry(entry_id=entry_id, created_at=NOW - age)
        original_created_at = original.created_at
        db.add_all([user, original])
        await db.commit()
        app = entry_app(db=db, user=user)

        async with api_client(app) as client:
            response = await client.patch(
                f"/api/entries/{entry_id}",
                json={
                    "item_name": " Updated headphones ",
                    "price_cents": 9_000,
                    "reason_wanted": " Updated reason ",
                },
            )

        assert response.status_code == 200
        body = response.json()["entry"]
        assert body["item_name"] == "Updated headphones"
        assert body["price_cents"] == 9_000
        assert body["reason_wanted"] == "Updated reason"
        assert body["status"] == "waiting"
        assert body["created_at"] == original_created_at.isoformat().replace("+00:00", "Z")
        assert body["updated_at"] == NOW.isoformat().replace("+00:00", "Z")
        persisted = await db.get(ImpulsePurchaseEntry, entry_id)
        assert persisted is not None
        assert persisted.user_id == USER_ID
        assert persisted.comment is None
        assert persisted.checked_in_at is None


@pytest.mark.asyncio
@pytest.mark.parametrize("stored_status", [EntryStatus.SAVED, EntryStatus.PURCHASED])
async def test_entry_update_rejects_resolved_status_without_changes(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    stored_status: EntryStatus,
) -> None:
    _, factory = entry_database
    entry_id = UUID("70000000-0000-4000-8000-000000000004")
    async with factory() as db:
        user = make_user()
        resolved = make_entry(
            entry_id=entry_id,
            status=stored_status,
            created_at=NOW - timedelta(days=3),
            checked_in_at=NOW - timedelta(hours=1),
        )
        original_name = resolved.item_name
        db.add_all([user, resolved])
        await db.commit()
        app = entry_app(db=db, user=user)

        async with api_client(app) as client:
            response = await client.patch(
                f"/api/entries/{entry_id}",
                json={
                    "item_name": "Forbidden update",
                    "price_cents": 9_000,
                    "reason_wanted": "Must not change",
                },
            )

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "invalid_entry_status"
        await db.refresh(resolved)
        assert resolved.item_name == original_name


@pytest.mark.asyncio
async def test_entry_detail_and_update_distinguish_forbidden_from_not_found_safely(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    other_entry_id = UUID("70000000-0000-4000-8000-000000000005")
    unknown_entry_id = UUID("70000000-0000-4000-8000-000000000099")
    async with factory() as db:
        user = make_user()
        other_user = make_user(user_id=OTHER_USER_ID, email="other-detail@example.com")
        other_entry = make_entry(
            entry_id=other_entry_id,
            user_id=OTHER_USER_ID,
            created_at=NOW,
        )
        db.add_all([user, other_user, other_entry])
        await db.commit()
        app = entry_app(db=db, user=user)
        payload = {
            "item_name": "Forbidden update",
            "price_cents": 9_000,
            "reason_wanted": "Must not change",
        }

        async with api_client(app) as client:
            forbidden_detail = await client.get(f"/api/entries/{other_entry_id}")
            missing_detail = await client.get(f"/api/entries/{unknown_entry_id}")
            forbidden_update = await client.patch(f"/api/entries/{other_entry_id}", json=payload)
            missing_update = await client.patch(f"/api/entries/{unknown_entry_id}", json=payload)

        for response in (forbidden_detail, forbidden_update):
            assert response.status_code == 403
            assert response.json()["error"]["code"] == "forbidden"
            assert "other-detail@example.com" not in response.text
            assert str(OTHER_USER_ID) not in response.text
        for response in (missing_detail, missing_update):
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "not_found"
        await db.refresh(other_entry)
        assert other_entry.item_name != "Forbidden update"


@pytest.mark.asyncio
async def test_entry_detail_and_update_reject_malformed_uuid(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    async with factory() as db:
        user = make_user()
        db.add(user)
        await db.commit()
        app = entry_app(db=db, user=user)

        async with api_client(app) as client:
            detail = await client.get("/api/entries/not-a-uuid")
            update = await client.patch(
                "/api/entries/not-a-uuid",
                json={
                    "item_name": "Headphones",
                    "price_cents": 9_000,
                    "reason_wanted": "Updated reason",
                },
            )

        assert detail.status_code == 422
        assert update.status_code == 422
        assert detail.json()["error"]["code"] == "validation_error"
        assert update.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_entry_update_rejects_invalid_fields_and_untrusted_origin(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    entry_id = UUID("70000000-0000-4000-8000-000000000006")
    async with factory() as db:
        user = make_user()
        entry = make_entry(entry_id=entry_id, created_at=NOW)
        original_name = entry.item_name
        db.add_all([user, entry])
        await db.commit()
        app = entry_app(db=db, user=user, frontend_origin="https://penny-saved.example")

        async with api_client(app) as client:
            invalid = await client.patch(
                f"/api/entries/{entry_id}",
                json={
                    "item_name": " ",
                    "price_cents": 19.99,
                    "reason_wanted": "Reason",
                    "status": "saved",
                },
            )
            untrusted = await client.patch(
                f"/api/entries/{entry_id}",
                headers={"Origin": "https://evil.example"},
                json={
                    "item_name": "Forbidden update",
                    "price_cents": 9_000,
                    "reason_wanted": "Must not change",
                },
            )

        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "validation_error"
        assert untrusted.status_code == 403
        assert untrusted.json()["error"]["code"] == "forbidden"
        await db.refresh(entry)
        assert entry.item_name == original_name


@pytest.mark.asyncio
@pytest.mark.parametrize("age", [timedelta(hours=1), timedelta(hours=48)])
async def test_entry_delete_removes_waiting_and_eligible_waiting_entries(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    age: timedelta,
) -> None:
    _, factory = entry_database
    entry_id = UUID("80000000-0000-4000-8000-000000000001")
    async with factory() as db:
        user = make_user()
        db.add_all([user, make_entry(entry_id=entry_id, created_at=NOW - age)])
        await db.commit()
        app = entry_app(db=db, user=user)

        async with api_client(app) as client:
            response = await client.delete(f"/api/entries/{entry_id}")

        assert response.status_code == 204
        assert response.content == b""
        assert "content-type" not in response.headers
        assert await db.get(ImpulsePurchaseEntry, entry_id) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("stored_status", [EntryStatus.SAVED, EntryStatus.PURCHASED])
async def test_entry_delete_rejects_resolved_entries_and_preserves_history(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    stored_status: EntryStatus,
) -> None:
    _, factory = entry_database
    entry_id = UUID("80000000-0000-4000-8000-000000000002")
    async with factory() as db:
        user = make_user()
        resolved = make_entry(
            entry_id=entry_id,
            status=stored_status,
            created_at=NOW - timedelta(days=3),
            checked_in_at=NOW - timedelta(hours=1),
        )
        db.add_all([user, resolved])
        await db.commit()
        app = entry_app(db=db, user=user)

        async with api_client(app) as client:
            response = await client.delete(f"/api/entries/{entry_id}")

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "invalid_entry_status"
        assert await db.get(ImpulsePurchaseEntry, entry_id) is not None


@pytest.mark.asyncio
async def test_entry_delete_distinguishes_forbidden_from_not_found_safely(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    other_entry_id = UUID("80000000-0000-4000-8000-000000000003")
    unknown_entry_id = UUID("80000000-0000-4000-8000-000000000099")
    async with factory() as db:
        user = make_user()
        other_user = make_user(user_id=OTHER_USER_ID, email="other-delete@example.com")
        other_entry = make_entry(
            entry_id=other_entry_id,
            user_id=OTHER_USER_ID,
            created_at=NOW,
        )
        db.add_all([user, other_user, other_entry])
        await db.commit()
        app = entry_app(db=db, user=user)

        async with api_client(app) as client:
            forbidden = await client.delete(f"/api/entries/{other_entry_id}")
            missing = await client.delete(f"/api/entries/{unknown_entry_id}")

        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "forbidden"
        assert "other-delete@example.com" not in forbidden.text
        assert str(OTHER_USER_ID) not in forbidden.text
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "not_found"
        assert await db.get(ImpulsePurchaseEntry, other_entry_id) is not None


@pytest.mark.asyncio
async def test_entry_delete_rejects_malformed_uuid_and_untrusted_origin(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    entry_id = UUID("80000000-0000-4000-8000-000000000004")
    async with factory() as db:
        user = make_user()
        db.add_all([user, make_entry(entry_id=entry_id, created_at=NOW)])
        await db.commit()
        app = entry_app(db=db, user=user, frontend_origin="https://penny-saved.example")

        async with api_client(app) as client:
            malformed = await client.delete("/api/entries/not-a-uuid")
            untrusted = await client.delete(
                f"/api/entries/{entry_id}",
                headers={"Origin": "https://evil.example"},
            )

        assert malformed.status_code == 422
        assert malformed.json()["error"]["code"] == "validation_error"
        assert untrusted.status_code == 403
        assert untrusted.json()["error"]["code"] == "forbidden"
        assert await db.get(ImpulsePurchaseEntry, entry_id) is not None


@pytest.mark.asyncio
async def test_entry_delete_rolls_back_when_repository_delete_fails(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, factory = entry_database
    entry_id = UUID("80000000-0000-4000-8000-000000000005")
    async with factory() as db:
        user = make_user()
        entry = make_entry(entry_id=entry_id, created_at=NOW)
        db.add_all([user, entry])
        await db.commit()
        app = entry_app(db=db, user=user)

        async def fail_delete(*args: object, **kwargs: object) -> None:
            del args, kwargs
            raise RuntimeError("injected delete failure")

        monkeypatch.setattr("app.services.entries.delete_owned_entry", fail_delete)
        with pytest.raises(RuntimeError, match="injected delete failure"):
            async with api_client(app) as client:
                await client.delete(f"/api/entries/{entry_id}")

        assert await db.get(ImpulsePurchaseEntry, entry_id) is not None


@pytest.mark.asyncio
async def test_entry_endpoints_share_one_complete_public_representation(
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
                    "item_name": "Headphones",
                    "price_cents": 8_500,
                    "reason_wanted": "Better noise cancellation",
                },
            )
            entry_id = created.json()["entry"]["id"]
            listed = await client.get("/api/entries")
            detailed = await client.get(f"/api/entries/{entry_id}")
            updated = await client.patch(
                f"/api/entries/{entry_id}",
                json={
                    "item_name": "Updated headphones",
                    "price_cents": 9_000,
                    "reason_wanted": "Updated reason",
                },
            )

        representations = [
            created.json()["entry"],
            listed.json()["waiting"][0],
            detailed.json()["entry"],
            updated.json()["entry"],
        ]
        expected_fields = {
            "id",
            "item_name",
            "price_cents",
            "reason_wanted",
            "status",
            "dashboard_bucket",
            "comment",
            "created_at",
            "eligible_for_check_in_at",
            "checked_in_at",
            "updated_at",
        }
        assert all(set(representation) == expected_fields for representation in representations)
        assert representations[0] == representations[1] == representations[2]
        assert all("user_id" not in representation for representation in representations)
