"""PostgreSQL service and API integration tests for entry creation and listing."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import pytest
from app.api.dependencies import get_current_user
from app.api.errors import ApplicationError
from app.core.config import AppEnvironment, Settings
from app.core.time import FixedClock, get_clock
from app.db.session import get_db_session
from app.main import create_app
from app.models.entry import EntryStatus, ImpulsePurchaseEntry
from app.models.session import Session
from app.models.user import User
from app.repositories.entries import get_entry_for_update as repository_get_entry_for_update
from app.schemas.entry import EntryCheckInRequest, EntryCommentUpdateRequest, EntryCreateRequest
from app.services.entries import (
    check_in_entry,
    create_entry,
    get_entry_detail,
    list_dashboard_entries,
    update_entry_comment,
)
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
            checked_in = await client.post(
                f"/api/entries/{entry_id}/check-in",
                json={"result": "saved"},
            )
            comment_updated = await client.patch(
                f"/api/entries/{entry_id}/comment",
                json={"comment": "Updated reflection"},
            )

        for response in (
            created,
            listed,
            detail,
            updated,
            deleted,
            checked_in,
            comment_updated,
        ):
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


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [EntryStatus.SAVED, EntryStatus.PURCHASED])
async def test_check_in_service_resolves_at_exact_boundary_with_one_clock_read(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    result: EntryStatus,
) -> None:
    _, factory = entry_database
    entry_id = UUID("90000000-0000-4000-8000-000000000001")
    async with factory() as db:
        user = make_user()
        entry = make_entry(
            entry_id=entry_id,
            created_at=NOW - timedelta(hours=48),
        )
        original_core_fields = (
            entry.user_id,
            entry.item_name,
            entry.price_cents,
            entry.reason_wanted,
            entry.created_at,
        )
        db.add_all([user, entry])
        await db.commit()
        clock = CountingClock()

        response = await check_in_entry(
            db,
            user=user,
            entry_id=entry_id,
            payload=EntryCheckInRequest(
                result=result.value,
                comment="  I made a decision.  ",
            ),
            clock=clock,
        )

        assert clock.calls == 1
        assert response.status is result
        assert response.dashboard_bucket == result.value
        assert response.comment == "I made a decision."
        assert response.checked_in_at == response.updated_at == NOW
        persisted = await db.get(ImpulsePurchaseEntry, entry_id)
        assert persisted is not None
        assert persisted.status is result
        assert persisted.comment == "I made a decision."
        assert persisted.checked_in_at == persisted.updated_at == NOW
        assert (
            persisted.user_id,
            persisted.item_name,
            persisted.price_cents,
            persisted.reason_wanted,
            persisted.created_at,
        ) == original_core_fields


@pytest.mark.asyncio
async def test_check_in_service_rejects_one_microsecond_early_without_mutation(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    entry_id = UUID("90000000-0000-4000-8000-000000000002")
    async with factory() as db:
        user = make_user()
        db.add_all(
            [
                user,
                make_entry(
                    entry_id=entry_id,
                    created_at=NOW - timedelta(hours=48) + timedelta(microseconds=1),
                ),
            ]
        )
        await db.commit()

        with pytest.raises(ApplicationError) as raised:
            await check_in_entry(
                db,
                user=user,
                entry_id=entry_id,
                payload=EntryCheckInRequest(result="saved", comment="Too early"),
                clock=FixedClock(NOW),
            )

        assert raised.value.status_code == 409
        assert raised.value.code == "early_check_in"
        persisted = await db.get(ImpulsePurchaseEntry, entry_id)
        assert persisted is not None
        assert persisted.status is EntryStatus.WAITING
        assert persisted.comment is None
        assert persisted.checked_in_at is None


@pytest.mark.asyncio
@pytest.mark.parametrize("stored_status", [EntryStatus.SAVED, EntryStatus.PURCHASED])
async def test_check_in_service_rejects_an_already_resolved_entry(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    stored_status: EntryStatus,
) -> None:
    _, factory = entry_database
    entry_id = UUID("90000000-0000-4000-8000-000000000003")
    original_checked_in_at = NOW - timedelta(hours=1)
    async with factory() as db:
        user = make_user()
        db.add_all(
            [
                user,
                make_entry(
                    entry_id=entry_id,
                    status=stored_status,
                    created_at=NOW - timedelta(days=3),
                    checked_in_at=original_checked_in_at,
                ),
            ]
        )
        await db.commit()

        with pytest.raises(ApplicationError) as raised:
            await check_in_entry(
                db,
                user=user,
                entry_id=entry_id,
                payload=EntryCheckInRequest(result="saved", comment="Second decision"),
                clock=FixedClock(NOW),
            )

        assert raised.value.status_code == 409
        assert raised.value.code == "invalid_entry_status"
        persisted = await db.get(ImpulsePurchaseEntry, entry_id)
        assert persisted is not None
        assert persisted.status is stored_status
        assert persisted.comment is None
        assert persisted.checked_in_at == original_checked_in_at


@pytest.mark.asyncio
async def test_check_in_service_distinguishes_forbidden_from_not_found(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    other_entry_id = UUID("90000000-0000-4000-8000-000000000004")
    unknown_entry_id = UUID("90000000-0000-4000-8000-000000000099")
    async with factory() as db:
        user = make_user()
        other_user = make_user(user_id=OTHER_USER_ID, email="other-check-in@example.com")
        db.add_all(
            [
                user,
                other_user,
                make_entry(
                    entry_id=other_entry_id,
                    user_id=OTHER_USER_ID,
                    created_at=NOW - timedelta(days=3),
                ),
            ]
        )
        await db.commit()
        payload = EntryCheckInRequest(result="saved")

        with pytest.raises(ApplicationError) as forbidden:
            await check_in_entry(
                db,
                user=user,
                entry_id=other_entry_id,
                payload=payload,
                clock=FixedClock(NOW),
            )
        await db.refresh(user)
        with pytest.raises(ApplicationError) as missing:
            await check_in_entry(
                db,
                user=user,
                entry_id=unknown_entry_id,
                payload=payload,
                clock=FixedClock(NOW),
            )

        assert (forbidden.value.status_code, forbidden.value.code) == (403, "forbidden")
        assert (missing.value.status_code, missing.value.code) == (404, "not_found")
        other_entry = await db.get(ImpulsePurchaseEntry, other_entry_id)
        assert other_entry is not None
        assert other_entry.status is EntryStatus.WAITING


@pytest.mark.asyncio
async def test_check_in_service_rolls_back_a_failed_repository_update(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, factory = entry_database
    entry_id = UUID("90000000-0000-4000-8000-000000000005")
    async with factory() as db:
        user = make_user()
        db.add_all(
            [
                user,
                make_entry(entry_id=entry_id, created_at=NOW - timedelta(days=3)),
            ]
        )
        await db.commit()

        def fail_after_partial_update(**kwargs: object) -> None:
            entry = kwargs["entry"]
            assert isinstance(entry, ImpulsePurchaseEntry)
            entry.status = EntryStatus.SAVED
            entry.comment = "Partial change"
            entry.checked_in_at = NOW
            entry.updated_at = NOW
            raise RuntimeError("injected check-in failure")

        monkeypatch.setattr(
            "app.services.entries.check_in_owned_entry",
            fail_after_partial_update,
        )
        with pytest.raises(RuntimeError, match="injected check-in failure"):
            await check_in_entry(
                db,
                user=user,
                entry_id=entry_id,
                payload=EntryCheckInRequest(result="saved"),
                clock=FixedClock(NOW),
            )

        persisted = await db.get(ImpulsePurchaseEntry, entry_id)
        assert persisted is not None
        assert persisted.status is EntryStatus.WAITING
        assert persisted.comment is None
        assert persisted.checked_in_at is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result", "submitted_comment", "expected_comment"),
    [
        ("saved", "  I no longer wanted it.  ", "I no longer wanted it."),
        ("purchased", None, None),
    ],
)
async def test_check_in_api_returns_the_resolved_entry(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    result: str,
    submitted_comment: str | None,
    expected_comment: str | None,
) -> None:
    _, factory = entry_database
    entry_id = UUID("91000000-0000-4000-8000-000000000001")
    async with factory() as db:
        user = make_user()
        db.add_all(
            [
                user,
                make_entry(entry_id=entry_id, created_at=NOW - timedelta(hours=48)),
            ]
        )
        await db.commit()
        app = entry_app(db=db, user=user)
        payload: dict[str, str | None] = {"result": result}
        if submitted_comment is not None:
            payload["comment"] = submitted_comment

        async with api_client(app) as client:
            response = await client.post(
                f"/api/entries/{entry_id}/check-in",
                json=payload,
            )

        assert response.status_code == 200
        body = response.json()["entry"]
        assert body["id"] == str(entry_id)
        assert body["status"] == result
        assert body["dashboard_bucket"] == result
        assert body["comment"] == expected_comment
        assert body["checked_in_at"] == body["updated_at"] == "2026-07-30T12:00:00Z"
        assert "user_id" not in body


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("age", "stored_status", "expected_code"),
    [
        (timedelta(hours=47), EntryStatus.WAITING, "early_check_in"),
        (timedelta(days=3), EntryStatus.SAVED, "invalid_entry_status"),
        (timedelta(days=3), EntryStatus.PURCHASED, "invalid_entry_status"),
    ],
)
async def test_check_in_api_returns_lifecycle_conflicts_without_mutation(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    age: timedelta,
    stored_status: EntryStatus,
    expected_code: str,
) -> None:
    _, factory = entry_database
    entry_id = UUID("91000000-0000-4000-8000-000000000002")
    original_checked_in_at = (
        None if stored_status is EntryStatus.WAITING else NOW - timedelta(hours=1)
    )
    async with factory() as db:
        user = make_user()
        db.add_all(
            [
                user,
                make_entry(
                    entry_id=entry_id,
                    status=stored_status,
                    created_at=NOW - age,
                    checked_in_at=original_checked_in_at,
                ),
            ]
        )
        await db.commit()
        app = entry_app(db=db, user=user)

        async with api_client(app) as client:
            response = await client.post(
                f"/api/entries/{entry_id}/check-in",
                json={"result": "saved", "comment": "Must not persist"},
            )

        assert response.status_code == 409
        assert response.json()["error"]["code"] == expected_code
        persisted = await db.get(ImpulsePurchaseEntry, entry_id)
        assert persisted is not None
        assert persisted.status is stored_status
        assert persisted.comment is None
        assert persisted.checked_in_at == original_checked_in_at


@pytest.mark.asyncio
async def test_check_in_api_distinguishes_forbidden_from_not_found_safely(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    other_entry_id = UUID("91000000-0000-4000-8000-000000000003")
    unknown_entry_id = UUID("91000000-0000-4000-8000-000000000099")
    async with factory() as db:
        user = make_user()
        other_user = make_user(user_id=OTHER_USER_ID, email="private-owner@example.com")
        db.add_all(
            [
                user,
                other_user,
                make_entry(
                    entry_id=other_entry_id,
                    user_id=OTHER_USER_ID,
                    created_at=NOW - timedelta(days=3),
                ),
            ]
        )
        await db.commit()
        app = entry_app(db=db, user=user)

        async with api_client(app) as client:
            forbidden = await client.post(
                f"/api/entries/{other_entry_id}/check-in",
                json={"result": "saved"},
            )
            missing = await client.post(
                f"/api/entries/{unknown_entry_id}/check-in",
                json={"result": "saved"},
            )

        assert (forbidden.status_code, forbidden.json()["error"]["code"]) == (
            403,
            "forbidden",
        )
        assert (missing.status_code, missing.json()["error"]["code"]) == (404, "not_found")
        assert "private-owner@example.com" not in forbidden.text
        assert str(OTHER_USER_ID) not in forbidden.text


@pytest.mark.asyncio
async def test_check_in_api_rejects_invalid_input_and_untrusted_origin(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    entry_id = UUID("91000000-0000-4000-8000-000000000004")
    async with factory() as db:
        user = make_user()
        db.add_all(
            [
                user,
                make_entry(entry_id=entry_id, created_at=NOW - timedelta(days=3)),
            ]
        )
        await db.commit()
        app = entry_app(
            db=db,
            user=user,
            frontend_origin="https://penny-saved.example",
        )

        async with api_client(app) as client:
            malformed_uuid = await client.post(
                "/api/entries/not-a-uuid/check-in",
                json={"result": "saved"},
            )
            invalid_body = await client.post(
                f"/api/entries/{entry_id}/check-in",
                json={"result": "waiting", "status": "saved"},
            )
            untrusted = await client.post(
                f"/api/entries/{entry_id}/check-in",
                headers={"Origin": "https://evil.example"},
                json={"result": "saved"},
            )

        for response in (malformed_uuid, invalid_body):
            assert response.status_code == 422
            assert response.json()["error"]["code"] == "validation_error"
        assert untrusted.status_code == 403
        assert untrusted.json()["error"]["code"] == "forbidden"
        persisted = await db.get(ImpulsePurchaseEntry, entry_id)
        assert persisted is not None
        assert persisted.status is EntryStatus.WAITING


@pytest.mark.asyncio
async def test_concurrent_check_in_requests_produce_one_complete_outcome(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, factory = entry_database
    entry_id = UUID("92000000-0000-4000-8000-000000000001")
    async with factory() as setup_db:
        setup_db.add_all(
            [
                make_user(),
                make_entry(entry_id=entry_id, created_at=NOW - timedelta(days=3)),
            ]
        )
        await setup_db.commit()

    both_requests_ready = asyncio.Event()
    arrived = 0

    async def synchronize_before_row_lock(
        db: AsyncSession,
        *,
        user_id: UUID,
        entry_id: UUID,
    ) -> ImpulsePurchaseEntry | None:
        nonlocal arrived
        arrived += 1
        if arrived == 2:
            both_requests_ready.set()
        await asyncio.wait_for(both_requests_ready.wait(), timeout=2)
        return await repository_get_entry_for_update(
            db,
            user_id=user_id,
            entry_id=entry_id,
        )

    monkeypatch.setattr(
        "app.services.entries.get_entry_for_update",
        synchronize_before_row_lock,
    )

    async with factory() as saved_db, factory() as purchased_db:
        saved_app = entry_app(db=saved_db, user=make_user())
        purchased_app = entry_app(db=purchased_db, user=make_user())
        async with (
            api_client(saved_app) as saved_client,
            api_client(purchased_app) as purchased_client,
        ):
            saved_response, purchased_response = await asyncio.gather(
                saved_client.post(
                    f"/api/entries/{entry_id}/check-in",
                    json={"result": "saved", "comment": "Saved request won."},
                ),
                purchased_client.post(
                    f"/api/entries/{entry_id}/check-in",
                    json={"result": "purchased", "comment": "Purchased request won."},
                ),
            )

    responses = [saved_response, purchased_response]
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response for response in responses if response.status_code == 200)
    loser = next(response for response in responses if response.status_code == 409)
    assert loser.json()["error"]["code"] == "invalid_entry_status"

    winner_entry = winner.json()["entry"]
    expected_comments = {
        "saved": "Saved request won.",
        "purchased": "Purchased request won.",
    }
    assert winner_entry["comment"] == expected_comments[winner_entry["status"]]
    assert winner_entry["checked_in_at"] == winner_entry["updated_at"]

    async with factory() as verification_db:
        persisted = await verification_db.get(ImpulsePurchaseEntry, entry_id)
        assert persisted is not None
        assert persisted.status.value == winner_entry["status"]
        assert persisted.comment == winner_entry["comment"]
        assert persisted.checked_in_at == persisted.updated_at == NOW
        assert persisted.checked_in_at > persisted.created_at


@pytest.mark.asyncio
@pytest.mark.parametrize("result", ["saved", "purchased"])
async def test_resolved_check_in_is_consistent_across_entry_endpoints(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    result: str,
) -> None:
    _, factory = entry_database
    entry_id = UUID("93000000-0000-4000-8000-000000000001")
    async with factory() as db:
        user = make_user()
        db.add_all(
            [
                user,
                make_entry(entry_id=entry_id, created_at=NOW - timedelta(days=3)),
            ]
        )
        await db.commit()
        app = entry_app(db=db, user=user)

        async with api_client(app) as client:
            checked_in = await client.post(
                f"/api/entries/{entry_id}/check-in",
                json={"result": result, "comment": "Final decision"},
            )
            dashboard = await client.get("/api/entries")
            detail = await client.get(f"/api/entries/{entry_id}")
            rejected_update = await client.patch(
                f"/api/entries/{entry_id}",
                json={
                    "item_name": "Must not change",
                    "price_cents": 2_000,
                    "reason_wanted": "Resolved history is immutable",
                },
            )
            rejected_delete = await client.delete(f"/api/entries/{entry_id}")
            detail_after_rollbacks = await client.get(f"/api/entries/{entry_id}")

        assert checked_in.status_code == 200
        expected_entry = checked_in.json()["entry"]
        assert set(expected_entry) == {
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
        assert "user_id" not in checked_in.text
        assert dashboard.status_code == detail.status_code == 200
        assert dashboard.json()[result] == [expected_entry]
        other_buckets = {"needs_check_in", "waiting", "saved", "purchased"} - {result}
        assert all(dashboard.json()[bucket] == [] for bucket in other_buckets)
        assert detail.json()["entry"] == expected_entry

        for response in (rejected_update, rejected_delete):
            assert response.status_code == 409
            assert set(response.json()) == {"error"}
            assert set(response.json()["error"]) == {"code", "message"}
            assert response.json()["error"]["code"] == "invalid_entry_status"

        assert detail_after_rollbacks.status_code == 200
        assert detail_after_rollbacks.json()["entry"] == expected_entry


@pytest.mark.asyncio
@pytest.mark.parametrize("stored_status", [EntryStatus.SAVED, EntryStatus.PURCHASED])
async def test_comment_update_service_changes_only_resolved_comment_and_timestamp(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    stored_status: EntryStatus,
) -> None:
    _, factory = entry_database
    entry_id = UUID("90000000-0000-4000-8000-000000000020")
    checked_in_at = NOW - timedelta(hours=2)
    async with factory() as db:
        user = make_user()
        entry = make_entry(
            entry_id=entry_id,
            status=stored_status,
            created_at=NOW - timedelta(days=3),
            checked_in_at=checked_in_at,
        )
        entry.comment = "Original reflection"
        db.add_all([user, entry])
        await db.commit()
        protected_fields = (
            entry.user_id,
            entry.item_name,
            entry.price_cents,
            entry.reason_wanted,
            entry.status,
            entry.created_at,
            entry.checked_in_at,
        )
        clock = CountingClock()

        response = await update_entry_comment(
            db,
            user=user,
            entry_id=entry_id,
            payload=EntryCommentUpdateRequest(comment="  I borrowed one instead.  "),
            clock=clock,
        )

        assert clock.calls == 1
        assert response.comment == "I borrowed one instead."
        assert response.updated_at == NOW
        assert response.status is stored_status
        persisted = await db.get(ImpulsePurchaseEntry, entry_id)
        assert persisted is not None
        assert persisted.comment == "I borrowed one instead."
        assert persisted.updated_at == NOW
        assert (
            persisted.user_id,
            persisted.item_name,
            persisted.price_cents,
            persisted.reason_wanted,
            persisted.status,
            persisted.created_at,
            persisted.checked_in_at,
        ) == protected_fields


@pytest.mark.asyncio
async def test_comment_update_service_clears_resolved_comment_to_null(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    entry_id = UUID("90000000-0000-4000-8000-000000000021")
    async with factory() as db:
        user = make_user()
        entry = make_entry(
            entry_id=entry_id,
            status=EntryStatus.SAVED,
            created_at=NOW - timedelta(days=3),
            checked_in_at=NOW - timedelta(hours=1),
        )
        entry.comment = "Remove this"
        db.add_all([user, entry])
        await db.commit()

        response = await update_entry_comment(
            db,
            user=user,
            entry_id=entry_id,
            payload=EntryCommentUpdateRequest(comment="  "),
            clock=FixedClock(NOW),
        )

        assert response.comment is None
        persisted = await db.get(ImpulsePurchaseEntry, entry_id)
        assert persisted is not None
        assert persisted.comment is None


@pytest.mark.asyncio
async def test_comment_update_service_rejects_waiting_without_mutation(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    entry_id = UUID("90000000-0000-4000-8000-000000000022")
    async with factory() as db:
        user = make_user()
        entry = make_entry(entry_id=entry_id, created_at=NOW - timedelta(days=3))
        db.add_all([user, entry])
        await db.commit()
        original_updated_at = entry.updated_at

        with pytest.raises(ApplicationError) as raised:
            await update_entry_comment(
                db,
                user=user,
                entry_id=entry_id,
                payload=EntryCommentUpdateRequest(comment="Not resolved"),
                clock=FixedClock(NOW),
            )

        assert (raised.value.status_code, raised.value.code) == (409, "invalid_entry_status")
        persisted = await db.get(ImpulsePurchaseEntry, entry_id)
        assert persisted is not None
        assert persisted.comment is None
        assert persisted.updated_at == original_updated_at


@pytest.mark.asyncio
async def test_comment_update_service_distinguishes_forbidden_from_not_found(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    other_entry_id = UUID("90000000-0000-4000-8000-000000000023")
    missing_entry_id = UUID("90000000-0000-4000-8000-000000000099")
    async with factory() as db:
        user = make_user()
        other_user = make_user(user_id=OTHER_USER_ID, email="other-comment@example.com")
        other_entry = make_entry(
            entry_id=other_entry_id,
            user_id=OTHER_USER_ID,
            status=EntryStatus.PURCHASED,
            created_at=NOW - timedelta(days=3),
            checked_in_at=NOW - timedelta(hours=1),
        )
        db.add_all([user, other_user, other_entry])
        await db.commit()
        payload = EntryCommentUpdateRequest(comment="Forbidden reflection")

        with pytest.raises(ApplicationError) as forbidden:
            await update_entry_comment(
                db,
                user=user,
                entry_id=other_entry_id,
                payload=payload,
                clock=FixedClock(NOW),
            )
        await db.refresh(user)
        with pytest.raises(ApplicationError) as missing:
            await update_entry_comment(
                db,
                user=user,
                entry_id=missing_entry_id,
                payload=payload,
                clock=FixedClock(NOW),
            )

        assert (forbidden.value.status_code, forbidden.value.code) == (403, "forbidden")
        assert (missing.value.status_code, missing.value.code) == (404, "not_found")
        persisted = await db.get(ImpulsePurchaseEntry, other_entry_id)
        assert persisted is not None
        assert persisted.comment is None


@pytest.mark.asyncio
async def test_comment_update_service_rolls_back_partial_repository_failure(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, factory = entry_database
    entry_id = UUID("90000000-0000-4000-8000-000000000024")
    checked_in_at = NOW - timedelta(hours=1)
    original_updated_at = checked_in_at
    async with factory() as db:
        user = make_user()
        entry = make_entry(
            entry_id=entry_id,
            status=EntryStatus.SAVED,
            created_at=NOW - timedelta(days=3),
            checked_in_at=checked_in_at,
        )
        entry.comment = "Original reflection"
        db.add_all([user, entry])
        await db.commit()

        def fail_after_partial_update(**kwargs: object) -> None:
            target = kwargs["entry"]
            assert isinstance(target, ImpulsePurchaseEntry)
            target.comment = "Partial reflection"
            target.updated_at = NOW
            raise RuntimeError("injected comment update failure")

        monkeypatch.setattr(
            "app.services.entries.update_owned_entry_comment",
            fail_after_partial_update,
        )
        with pytest.raises(RuntimeError, match="injected comment update failure"):
            await update_entry_comment(
                db,
                user=user,
                entry_id=entry_id,
                payload=EntryCommentUpdateRequest(comment="New reflection"),
                clock=FixedClock(NOW),
            )

        persisted = await db.get(ImpulsePurchaseEntry, entry_id)
        assert persisted is not None
        assert persisted.comment == "Original reflection"
        assert persisted.updated_at == original_updated_at


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stored_status", "submitted_comment", "expected_comment"),
    [
        (EntryStatus.SAVED, "  I borrowed one instead.  ", "I borrowed one instead."),
        (EntryStatus.PURCHASED, "   ", None),
    ],
)
async def test_comment_update_api_returns_complete_server_confirmed_entry(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    stored_status: EntryStatus,
    submitted_comment: str,
    expected_comment: str | None,
) -> None:
    _, factory = entry_database
    entry_id = UUID("92000000-0000-4000-8000-000000000001")
    checked_in_at = NOW - timedelta(hours=1)
    async with factory() as db:
        user = make_user()
        entry = make_entry(
            entry_id=entry_id,
            status=stored_status,
            created_at=NOW - timedelta(days=3),
            checked_in_at=checked_in_at,
        )
        entry.comment = "Original reflection"
        db.add_all([user, entry])
        await db.commit()
        original_core = (
            entry.item_name,
            entry.price_cents,
            entry.reason_wanted,
            entry.status,
            entry.created_at,
            entry.checked_in_at,
        )
        app = entry_app(db=db, user=user)

        async with api_client(app) as client:
            response = await client.patch(
                f"/api/entries/{entry_id}/comment",
                json={"comment": submitted_comment},
            )

        assert response.status_code == 200
        body = response.json()["entry"]
        assert set(body) == {
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
        assert body["comment"] == expected_comment
        assert body["status"] == body["dashboard_bucket"] == stored_status.value
        assert body["checked_in_at"] == "2026-07-30T11:00:00Z"
        assert body["updated_at"] == "2026-07-30T12:00:00Z"
        assert "user_id" not in response.text
        persisted = await db.get(ImpulsePurchaseEntry, entry_id)
        assert persisted is not None
        assert (
            persisted.item_name,
            persisted.price_cents,
            persisted.reason_wanted,
            persisted.status,
            persisted.created_at,
            persisted.checked_in_at,
        ) == original_core


@pytest.mark.asyncio
async def test_comment_update_api_returns_waiting_conflict_without_mutation(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    entry_id = UUID("92000000-0000-4000-8000-000000000002")
    async with factory() as db:
        user = make_user()
        entry = make_entry(entry_id=entry_id, created_at=NOW - timedelta(days=3))
        db.add_all([user, entry])
        await db.commit()
        app = entry_app(db=db, user=user)

        async with api_client(app) as client:
            response = await client.patch(
                f"/api/entries/{entry_id}/comment",
                json={"comment": "Not resolved"},
            )

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "invalid_entry_status"
        persisted = await db.get(ImpulsePurchaseEntry, entry_id)
        assert persisted is not None
        assert persisted.comment is None
        assert persisted.updated_at == entry.created_at


@pytest.mark.asyncio
async def test_comment_update_api_distinguishes_forbidden_from_not_found_safely(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    other_entry_id = UUID("92000000-0000-4000-8000-000000000003")
    missing_entry_id = UUID("92000000-0000-4000-8000-000000000099")
    async with factory() as db:
        user = make_user()
        other_user = make_user(user_id=OTHER_USER_ID, email="private-comment@example.com")
        other_entry = make_entry(
            entry_id=other_entry_id,
            user_id=OTHER_USER_ID,
            status=EntryStatus.SAVED,
            created_at=NOW - timedelta(days=3),
            checked_in_at=NOW - timedelta(hours=1),
        )
        db.add_all([user, other_user, other_entry])
        await db.commit()
        app = entry_app(db=db, user=user)

        async with api_client(app) as client:
            forbidden = await client.patch(
                f"/api/entries/{other_entry_id}/comment",
                json={"comment": "Forbidden reflection"},
            )
            missing = await client.patch(
                f"/api/entries/{missing_entry_id}/comment",
                json={"comment": "Missing reflection"},
            )

        assert (forbidden.status_code, forbidden.json()["error"]["code"]) == (
            403,
            "forbidden",
        )
        assert (missing.status_code, missing.json()["error"]["code"]) == (404, "not_found")
        persisted = await db.get(ImpulsePurchaseEntry, other_entry_id)
        assert persisted is not None
        assert persisted.comment is None


@pytest.mark.asyncio
async def test_comment_update_api_rejects_invalid_input_and_untrusted_origin(
    entry_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = entry_database
    entry_id = UUID("92000000-0000-4000-8000-000000000004")
    async with factory() as db:
        user = make_user()
        entry = make_entry(
            entry_id=entry_id,
            status=EntryStatus.PURCHASED,
            created_at=NOW - timedelta(days=3),
            checked_in_at=NOW - timedelta(hours=1),
        )
        db.add_all([user, entry])
        await db.commit()
        app = entry_app(
            db=db,
            user=user,
            frontend_origin="https://penny-saved.example",
        )

        async with api_client(app) as client:
            malformed_uuid = await client.patch(
                "/api/entries/not-a-uuid/comment",
                json={"comment": "Reflection"},
            )
            missing_comment = await client.patch(
                f"/api/entries/{entry_id}/comment",
                json={},
            )
            protected_field = await client.patch(
                f"/api/entries/{entry_id}/comment",
                json={"comment": "Reflection", "status": "saved"},
            )
            malformed_json = await client.patch(
                f"/api/entries/{entry_id}/comment",
                content=b'{"comment":',
                headers={"Content-Type": "application/json"},
            )
            untrusted = await client.patch(
                f"/api/entries/{entry_id}/comment",
                headers={"Origin": "https://evil.example"},
                json={"comment": "Reflection"},
            )

        for response in (malformed_uuid, missing_comment, protected_field):
            assert response.status_code == 422
            assert response.json()["error"]["code"] == "validation_error"
        assert malformed_json.status_code == 400
        assert malformed_json.json()["error"]["code"] == "malformed_json"
        assert untrusted.status_code == 403
        assert untrusted.json()["error"]["code"] == "forbidden"
        persisted = await db.get(ImpulsePurchaseEntry, entry_id)
        assert persisted is not None
        assert persisted.comment is None
