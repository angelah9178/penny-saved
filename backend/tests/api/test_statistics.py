"""Tests for the protected statistics summary API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from app.api.dependencies import get_current_user
from app.api.routes import statistics as statistics_routes
from app.core.config import AppEnvironment, Settings
from app.core.time import FixedClock, get_clock
from app.db.session import get_db_session
from app.main import create_app
from app.models.user import User
from app.schemas.statistics import StatisticsRange, StatisticsSummaryResponse
from fastapi import FastAPI
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

USER_ID = UUID("61000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 8, 5, 14, 30, tzinfo=UTC)
DATABASE_URL = "postgresql+psycopg://app:secret@localhost:5432/penny_saved"


@asynccontextmanager
async def no_database_lifespan(app: FastAPI) -> AsyncIterator[None]:
    del app
    yield


@asynccontextmanager
async def api_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_url=DATABASE_URL,
    )


@pytest.fixture
def user() -> User:
    return User(
        id=USER_ID,
        email="statistics@example.com",
        password_hash="argon2-hash-placeholder",
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def protected_app(settings: Settings, user: User) -> FastAPI:
    app = create_app(settings, lifespan=no_database_lifespan)
    db = AsyncMock(spec=AsyncSession)

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
@pytest.mark.parametrize("selected_range", list(StatisticsRange))
async def test_statistics_api_exposes_every_range_and_authenticated_user(
    protected_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
    selected_range: StatisticsRange,
) -> None:
    service = AsyncMock(
        return_value=StatisticsSummaryResponse(
            range=selected_range,
            total_saved_cents=25_000,
            avoided_purchase_count=4,
            purchased_count=1,
        )
    )
    monkeypatch.setattr(statistics_routes, "get_statistics_summary", service)

    async with api_client(protected_app) as client:
        response = await client.get(
            "/api/stats/summary",
            params={"range": selected_range.value},
        )

    assert response.status_code == 200
    assert response.json() == {
        "range": selected_range.value,
        "total_saved_cents": 25_000,
        "avoided_purchase_count": 4,
        "purchased_count": 1,
        "opportunity_costs": [],
    }
    call = service.await_args
    assert call.kwargs["user_id"] == USER_ID
    assert call.kwargs["selected_range"] is selected_range
    assert call.kwargs["clock"].now() == NOW


@pytest.mark.asyncio
async def test_statistics_api_requires_authentication(settings: Settings) -> None:
    app = create_app(settings, lifespan=no_database_lifespan)
    db = AsyncMock(spec=AsyncSession)

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        yield db

    async def override_clock() -> FixedClock:
        return FixedClock(NOW)

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_clock] = override_clock

    async with api_client(app) as client:
        response = await client.get("/api/stats/summary?range=this_month")

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "unauthorized",
            "message": "Authentication is required.",
        }
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    ["", "?range=quarter", "?range=this_month&range=all_time"],
)
async def test_statistics_api_rejects_missing_unknown_and_repeated_ranges(
    protected_app: FastAPI,
    query: str,
) -> None:
    async with api_client(protected_app) as client:
        response = await client.get(f"/api/stats/summary{query}")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "statistics" not in response.text.lower()


@pytest.mark.asyncio
async def test_statistics_api_returns_safe_database_failure(
    protected_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=OperationalError("SELECT secret", {"password": "secret"}, Exception())
    )
    monkeypatch.setattr(statistics_routes, "get_statistics_summary", service)

    async with api_client(protected_app) as client:
        response = await client.get("/api/stats/summary?range=all_time")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "service_unavailable",
            "message": "The service is temporarily unavailable.",
        }
    }
    assert "secret" not in response.text


@pytest.mark.asyncio
async def test_statistics_api_returns_safe_unexpected_failure(
    protected_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(side_effect=RuntimeError("private implementation detail"))
    monkeypatch.setattr(statistics_routes, "get_statistics_summary", service)

    async with api_client(protected_app) as client:
        response = await client.get("/api/stats/summary?range=all_time")

    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "internal_error",
        "message": "An unexpected error occurred.",
    }
    assert "private implementation detail" not in response.text


def test_statistics_openapi_documents_enum_and_safe_responses(settings: Settings) -> None:
    app = create_app(settings, lifespan=no_database_lifespan)

    openapi = app.openapi()
    operation = openapi["paths"]["/api/stats/summary"]["get"]
    query_parameter = next(
        parameter for parameter in operation["parameters"] if parameter["name"] == "range"
    )

    assert operation["operationId"] == "get_statistics_summary"
    assert query_parameter["required"] is True
    schemas = openapi["components"]["schemas"]
    enum_schema = schemas["StatisticsRange"]
    assert enum_schema["enum"] == [item.value for item in StatisticsRange]
    summary_schema = schemas["StatisticsSummaryResponse"]
    assert summary_schema["properties"]["opportunity_costs"]["items"] == {
        "$ref": "#/components/schemas/OpportunityCostEquivalentResponse"
    }
    equivalent_schema = schemas["OpportunityCostEquivalentResponse"]
    assert set(equivalent_schema["required"]) == {
        "example_id",
        "label",
        "unit_name",
        "dollar_value_cents",
        "equivalent_units",
    }
    assert equivalent_schema["additionalProperties"] is False
    assert {"200", "401", "422", "500", "503"} <= set(operation["responses"])
