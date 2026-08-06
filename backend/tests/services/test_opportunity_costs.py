"""PostgreSQL cross-layer verification for opportunity-cost create and list APIs."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from app.api.dependencies import get_current_user
from app.api.routes import opportunity_costs as opportunity_cost_routes
from app.core.config import AppEnvironment, Settings
from app.core.time import FixedClock, get_clock
from app.db.session import get_db_session
from app.main import create_app
from app.models.opportunity_cost_example import OpportunityCostExample
from app.models.user import User
from app.schemas.opportunity_cost import (
    OpportunityCostCreateRequest,
    OpportunityCostUpdateRequest,
)
from app.services.opportunity_costs import (
    create_opportunity_cost_example,
    update_opportunity_cost_example,
)
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

USER_ID = UUID("70000000-0000-4000-8000-000000000001")
OTHER_USER_ID = UUID("70000000-0000-4000-8000-000000000002")
OLDER_ID = UUID("80000000-0000-4000-8000-000000000001")
TIE_LOW_ID = UUID("80000000-0000-4000-8000-000000000002")
TIE_HIGH_ID = UUID("80000000-0000-4000-8000-000000000003")
OTHER_ID = UUID("80000000-0000-4000-8000-000000000004")
NOW = datetime(2026, 8, 5, 16, tzinfo=UTC)
FRONTEND_ORIGIN = "http://frontend.test"


@pytest.fixture
async def opportunity_cost_database(
    test_database_url: URL,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(test_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(OpportunityCostExample.__table__.delete())
        await db.execute(User.__table__.delete())
        await db.commit()
    try:
        yield factory
    finally:
        async with factory() as db:
            await db.execute(OpportunityCostExample.__table__.delete())
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


def make_user(*, user_id: UUID = USER_ID, email: str = "examples@example.com") -> User:
    return User(
        id=user_id,
        email=email,
        password_hash="argon2-hash-placeholder",
        created_at=NOW,
        updated_at=NOW,
    )


def make_example(
    *,
    example_id: UUID,
    user_id: UUID = USER_ID,
    created_at: datetime = NOW,
) -> OpportunityCostExample:
    return OpportunityCostExample(
        id=example_id,
        user_id=user_id,
        label="Coffee",
        unit_name="cups",
        dollar_value_cents=500,
        created_at=created_at,
        updated_at=created_at,
    )


def opportunity_cost_app(
    *,
    db: AsyncSession,
    user: User | None,
) -> FastAPI:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_url="postgresql+psycopg://app:secret@localhost/penny_saved_test",
        frontend_origin=FRONTEND_ORIGIN,
    )
    app = create_app(settings, lifespan=no_database_lifespan)

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_clock() -> FixedClock:
        return FixedClock(NOW)

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_clock] = override_clock
    if user is not None:

        async def override_current_user() -> User:
            return user

        app.dependency_overrides[get_current_user] = override_current_user
    return app


@pytest.mark.asyncio
async def test_post_normalizes_persists_and_returns_owned_example(
    opportunity_cost_database: async_sessionmaker[AsyncSession],
) -> None:
    async with opportunity_cost_database() as db:
        user = make_user()
        db.add(user)
        await db.commit()

        async with api_client(opportunity_cost_app(db=db, user=user)) as client:
            response = await client.post(
                "/api/opportunity-cost-examples",
                headers={"origin": FRONTEND_ORIGIN},
                json={
                    "label": "  hours worked ",
                    "unit_name": " hours\n",
                    "dollar_value_cents": 1_000,
                },
            )

        persisted = await db.scalar(select(OpportunityCostExample))

    assert response.status_code == 201
    assert persisted is not None
    assert persisted.user_id == USER_ID
    assert persisted.label == "hours worked"
    assert persisted.unit_name == "hours"
    assert persisted.created_at == persisted.updated_at == NOW
    assert response.json() == {
        "example": {
            "id": str(persisted.id),
            "label": "hours worked",
            "unit_name": "hours",
            "dollar_value_cents": 1_000,
            "created_at": "2026-08-05T16:00:00Z",
            "updated_at": "2026-08-05T16:00:00Z",
        }
    }


@pytest.mark.asyncio
async def test_get_returns_only_owned_examples_in_stable_order_with_duplicates(
    opportunity_cost_database: async_sessionmaker[AsyncSession],
) -> None:
    async with opportunity_cost_database() as db:
        user = make_user()
        db.add_all(
            [
                user,
                make_user(user_id=OTHER_USER_ID, email="other-examples@example.com"),
            ]
        )
        await db.flush()
        db.add_all(
            [
                make_example(example_id=TIE_HIGH_ID),
                make_example(example_id=OLDER_ID, created_at=NOW - timedelta(days=1)),
                make_example(example_id=TIE_LOW_ID),
                make_example(example_id=OTHER_ID, user_id=OTHER_USER_ID),
            ]
        )
        await db.commit()

        async with api_client(opportunity_cost_app(db=db, user=user)) as client:
            response = await client.get(
                "/api/opportunity-cost-examples",
                headers={"origin": "http://untrusted.test"},
            )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["examples"]] == [
        str(OLDER_ID),
        str(TIE_LOW_ID),
        str(TIE_HIGH_ID),
    ]
    assert all(item["label"] == "Coffee" for item in response.json()["examples"])


@pytest.mark.asyncio
async def test_get_returns_empty_list_for_user_without_examples(
    opportunity_cost_database: async_sessionmaker[AsyncSession],
) -> None:
    async with opportunity_cost_database() as db:
        user = make_user()
        db.add(user)
        await db.commit()
        async with api_client(opportunity_cost_app(db=db, user=user)) as client:
            response = await client.get("/api/opportunity-cost-examples")

    assert response.status_code == 200
    assert response.json() == {"examples": []}


@pytest.mark.asyncio
async def test_both_endpoints_require_authentication(
    opportunity_cost_database: async_sessionmaker[AsyncSession],
) -> None:
    async with (
        opportunity_cost_database() as db,
        api_client(opportunity_cost_app(db=db, user=None)) as client,
    ):
        get_response = await client.get("/api/opportunity-cost-examples")
        post_response = await client.post(
            "/api/opportunity-cost-examples",
            json={"label": "Coffee", "unit_name": "cups", "dollar_value_cents": 500},
        )

    assert get_response.status_code == 401
    assert post_response.status_code == 401
    assert get_response.json()["error"]["code"] == "unauthorized"
    assert post_response.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_post_rejects_invalid_fields_and_untrusted_origin(
    opportunity_cost_database: async_sessionmaker[AsyncSession],
) -> None:
    async with opportunity_cost_database() as db:
        user = make_user()
        db.add(user)
        await db.commit()
        async with api_client(opportunity_cost_app(db=db, user=user)) as client:
            invalid = await client.post(
                "/api/opportunity-cost-examples",
                json={"label": "Coffee", "unit_name": "cups", "dollar_value_cents": 0},
            )
            untrusted = await client.post(
                "/api/opportunity-cost-examples",
                headers={"origin": "http://untrusted.test"},
                json={"label": "Coffee", "unit_name": "cups", "dollar_value_cents": 500},
            )
        count = len((await db.scalars(select(OpportunityCostExample))).all())

    assert invalid.status_code == 422
    assert untrusted.status_code == 403
    assert count == 0


@pytest.mark.asyncio
async def test_create_service_rolls_back_failed_commit() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.commit.side_effect = RuntimeError("database write failed")
    user = make_user()
    payload = OpportunityCostCreateRequest(
        label="Coffee",
        unit_name="cups",
        dollar_value_cents=500,
    )

    with pytest.raises(RuntimeError, match="database write failed"):
        await create_opportunity_cost_example(
            db,
            user=user,
            payload=payload,
            clock=FixedClock(NOW),
        )

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_patch_normalizes_updates_and_preserves_protected_fields(
    opportunity_cost_database: async_sessionmaker[AsyncSession],
) -> None:
    async with opportunity_cost_database() as db:
        user = make_user()
        example = make_example(example_id=OLDER_ID, created_at=NOW - timedelta(days=1))
        db.add_all([user, example])
        await db.commit()
        protected = (example.id, example.user_id, example.created_at)

        async with api_client(opportunity_cost_app(db=db, user=user)) as client:
            response = await client.patch(
                f"/api/opportunity-cost-examples/{OLDER_ID}",
                headers={"origin": FRONTEND_ORIGIN},
                json={
                    "label": "  Lunch out ",
                    "unit_name": " meals\n",
                    "dollar_value_cents": 1_500,
                },
            )
        await db.refresh(example)

    assert response.status_code == 200
    assert (example.label, example.unit_name, example.dollar_value_cents) == (
        "Lunch out",
        "meals",
        1_500,
    )
    assert example.updated_at == NOW
    assert (example.id, example.user_id, example.created_at) == protected
    assert response.json()["example"]["label"] == "Lunch out"


@pytest.mark.asyncio
async def test_delete_removes_owned_example_and_returns_empty_204(
    opportunity_cost_database: async_sessionmaker[AsyncSession],
) -> None:
    async with opportunity_cost_database() as db:
        user = make_user()
        db.add_all([user, make_example(example_id=OLDER_ID)])
        await db.commit()

        async with api_client(opportunity_cost_app(db=db, user=user)) as client:
            response = await client.delete(
                f"/api/opportunity-cost-examples/{OLDER_ID}",
                headers={"origin": FRONTEND_ORIGIN},
            )
        persisted = await db.get(OpportunityCostExample, OLDER_ID)

    assert response.status_code == 204
    assert response.content == b""
    assert persisted is None


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["patch", "delete"])
async def test_mutations_distinguish_other_owner_from_missing_id(
    method: str,
    opportunity_cost_database: async_sessionmaker[AsyncSession],
) -> None:
    async with opportunity_cost_database() as db:
        user = make_user()
        db.add_all(
            [
                user,
                make_user(user_id=OTHER_USER_ID, email="other-examples@example.com"),
                make_example(example_id=OTHER_ID, user_id=OTHER_USER_ID),
            ]
        )
        await db.commit()
        async with api_client(opportunity_cost_app(db=db, user=user)) as client:
            kwargs: dict[str, object] = {"headers": {"origin": FRONTEND_ORIGIN}}
            if method == "patch":
                kwargs["json"] = {
                    "label": "Lunch",
                    "unit_name": "meals",
                    "dollar_value_cents": 1_500,
                }
            forbidden = await client.request(
                method,
                f"/api/opportunity-cost-examples/{OTHER_ID}",
                **kwargs,
            )
            await db.refresh(user)
            missing = await client.request(
                method,
                f"/api/opportunity-cost-examples/{TIE_HIGH_ID}",
                **kwargs,
            )

    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["patch", "delete"])
async def test_mutations_reject_malformed_id_and_untrusted_origin(
    method: str,
    opportunity_cost_database: async_sessionmaker[AsyncSession],
) -> None:
    async with opportunity_cost_database() as db:
        user = make_user()
        db.add_all([user, make_example(example_id=OLDER_ID)])
        await db.commit()
        async with api_client(opportunity_cost_app(db=db, user=user)) as client:
            kwargs: dict[str, object] = {"headers": {"origin": FRONTEND_ORIGIN}}
            if method == "patch":
                kwargs["json"] = {
                    "label": "Lunch",
                    "unit_name": "meals",
                    "dollar_value_cents": 1_500,
                }
            malformed = await client.request(
                method,
                "/api/opportunity-cost-examples/not-a-uuid",
                **kwargs,
            )
            kwargs["headers"] = {"origin": "http://untrusted.test"}
            untrusted = await client.request(
                method,
                f"/api/opportunity-cost-examples/{OLDER_ID}",
                **kwargs,
            )

    assert malformed.status_code == 422
    assert malformed.json()["error"]["code"] == "validation_error"
    assert untrusted.status_code == 403
    assert untrusted.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_update_service_rolls_back_failed_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    db = AsyncMock(spec=AsyncSession)
    db.commit.side_effect = RuntimeError("database write failed")
    user = make_user()
    example = make_example(example_id=OLDER_ID)
    locked_lookup = AsyncMock(return_value=example)
    monkeypatch.setattr(
        "app.services.opportunity_costs.get_opportunity_cost_example_for_update",
        locked_lookup,
    )

    with pytest.raises(RuntimeError, match="database write failed"):
        await update_opportunity_cost_example(
            db,
            user=user,
            example_id=OLDER_ID,
            payload=OpportunityCostUpdateRequest(
                label="Lunch",
                unit_name="meals",
                dollar_value_cents=1_500,
            ),
            clock=FixedClock(NOW),
        )

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_complete_create_list_update_delete_api_flow(
    opportunity_cost_database: async_sessionmaker[AsyncSession],
) -> None:
    async with opportunity_cost_database() as db:
        user = make_user()
        db.add(user)
        await db.commit()
        async with api_client(opportunity_cost_app(db=db, user=user)) as client:
            created = await client.post(
                "/api/opportunity-cost-examples",
                headers={"origin": FRONTEND_ORIGIN},
                json={"label": "Coffee", "unit_name": "cups", "dollar_value_cents": 500},
            )
            example_id = created.json()["example"]["id"]
            listed = await client.get("/api/opportunity-cost-examples")
            updated = await client.patch(
                f"/api/opportunity-cost-examples/{example_id}",
                headers={"origin": FRONTEND_ORIGIN},
                json={"label": "Lunch", "unit_name": "meals", "dollar_value_cents": 1_500},
            )
            deleted = await client.delete(
                f"/api/opportunity-cost-examples/{example_id}",
                headers={"origin": FRONTEND_ORIGIN},
            )
            final_list = await client.get("/api/opportunity-cost-examples")

    assert created.status_code == 201
    assert [item["id"] for item in listed.json()["examples"]] == [example_id]
    assert updated.status_code == 200
    assert updated.json()["example"]["label"] == "Lunch"
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert final_list.json() == {"examples": []}


@pytest.mark.asyncio
async def test_concurrent_deletes_produce_one_delete_and_one_not_found(
    opportunity_cost_database: async_sessionmaker[AsyncSession],
) -> None:
    async with opportunity_cost_database() as setup_db:
        setup_db.add_all([make_user(), make_example(example_id=OLDER_ID)])
        await setup_db.commit()

    async with opportunity_cost_database() as first_db, opportunity_cost_database() as second_db:
        first_user = await first_db.get(User, USER_ID)
        second_user = await second_db.get(User, USER_ID)
        assert first_user is not None and second_user is not None
        async with (
            api_client(opportunity_cost_app(db=first_db, user=first_user)) as first_client,
            api_client(opportunity_cost_app(db=second_db, user=second_user)) as second_client,
        ):
            responses = await asyncio.gather(
                first_client.delete(
                    f"/api/opportunity-cost-examples/{OLDER_ID}",
                    headers={"origin": FRONTEND_ORIGIN},
                ),
                second_client.delete(
                    f"/api/opportunity-cost-examples/{OLDER_ID}",
                    headers={"origin": FRONTEND_ORIGIN},
                ),
            )

    assert sorted(response.status_code for response in responses) == [204, 404]
    not_found = next(response for response in responses if response.status_code == 404)
    assert not_found.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "status_code", "code"),
    [
        (
            OperationalError("SELECT secret", {"secret": "value"}, RuntimeError("driver")),
            503,
            "service_unavailable",
        ),
        (RuntimeError("private implementation detail"), 500, "internal_error"),
    ],
)
async def test_list_endpoint_returns_safe_failure_envelopes(
    failure: Exception,
    status_code: int,
    code: str,
    opportunity_cost_database: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with opportunity_cost_database() as db:
        user = make_user()
        service = AsyncMock(side_effect=failure)
        monkeypatch.setattr(
            opportunity_cost_routes,
            "list_opportunity_cost_examples",
            service,
        )
        app = opportunity_cost_app(db=db, user=user)
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/opportunity-cost-examples")

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == code
    assert "secret" not in response.text
    assert "private implementation detail" not in response.text


def test_openapi_documents_complete_opportunity_cost_contract() -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_url="postgresql+psycopg://app:secret@localhost/penny_saved_test",
    )
    document = create_app(settings, lifespan=no_database_lifespan).openapi()
    paths = document["paths"]
    collection = paths["/api/opportunity-cost-examples"]
    detail = paths["/api/opportunity-cost-examples/{example_id}"]

    assert collection["post"]["operationId"] == "create_opportunity_cost_example"
    assert collection["get"]["operationId"] == "list_opportunity_cost_examples"
    assert detail["patch"]["operationId"] == "update_opportunity_cost_example"
    assert detail["delete"]["operationId"] == "delete_opportunity_cost_example"
    assert set(collection["post"]["responses"]) >= {"201", "401", "403", "422", "500", "503"}
    assert set(collection["get"]["responses"]) >= {"200", "401", "500", "503"}
    assert set(detail["patch"]["responses"]) >= {
        "200",
        "401",
        "403",
        "404",
        "422",
        "500",
        "503",
    }
    assert set(detail["delete"]["responses"]) >= {
        "204",
        "401",
        "403",
        "404",
        "422",
        "500",
        "503",
    }
    schemas = document["components"]["schemas"]
    mutable_fields = {"label", "unit_name", "dollar_value_cents"}
    assert set(schemas["OpportunityCostCreateRequest"]["properties"]) == mutable_fields
    assert set(schemas["OpportunityCostUpdateRequest"]["properties"]) == mutable_fields
    assert "user_id" not in schemas["OpportunityCostExampleResponse"]["properties"]
    assert detail["delete"]["responses"]["204"] == {"description": "Successful Response"}
