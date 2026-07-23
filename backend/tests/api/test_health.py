"""Tests for the FastAPI factory and health contracts."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from app.api.routes.health import READINESS_TIMEOUT_SECONDS
from app.core.config import AppEnvironment, Settings
from app.core.logging import REQUEST_ID_HEADER
from app.db.session import get_db_session
from app.main import create_app
from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

DATABASE_URL = "postgresql+psycopg://app:secret@localhost:5432/penny_saved"
FRONTEND_ORIGIN = "http://localhost:5173"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.DEVELOPMENT,
        database_url=DATABASE_URL,
        frontend_origin=FRONTEND_ORIGIN,
    )


@asynccontextmanager
async def no_database_lifespan(app: FastAPI) -> AsyncIterator[None]:
    del app
    yield


@asynccontextmanager
async def api_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def app_with_session(settings: Settings, session: AsyncSession) -> FastAPI:
    app = create_app(settings, lifespan=no_database_lifespan)

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_db_session] = override_db_session
    return app


@pytest.mark.asyncio
async def test_factory_registers_database_lifespan(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    @asynccontextmanager
    async def tracked_lifespan(app: FastAPI) -> AsyncIterator[None]:
        del app
        events.append("started")
        yield
        events.append("stopped")

    lifespan_builder = MagicMock(return_value=tracked_lifespan)
    monkeypatch.setattr("app.main.create_database_lifespan", lifespan_builder)

    app = create_app(settings)
    async with app.router.lifespan_context(app):
        assert events == ["started"]

    lifespan_builder.assert_called_once_with(settings)
    assert events == ["started", "stopped"]
    assert app.state.settings is settings


@pytest.mark.asyncio
async def test_health_returns_explicit_liveness_contract(settings: Settings) -> None:
    app = create_app(settings, lifespan=no_database_lifespan)

    async with api_client(app) as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readiness_executes_bounded_database_probe(settings: Settings) -> None:
    session = AsyncMock(spec=AsyncSession)
    app = app_with_session(settings, session)

    async with api_client(app) as client:
        response = await client.get("/api/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    statement = session.execute.await_args.args[0]
    assert str(statement) == "SELECT 1"


@pytest.mark.asyncio
async def test_readiness_returns_safe_unavailable_response(
    settings: Settings,
) -> None:
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = SQLAlchemyError("database connection details")
    app = app_with_session(settings, session)

    async with api_client(app) as client:
        response = await client.get("/api/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert "connection details" not in response.text


@pytest.mark.asyncio
async def test_readiness_times_out_slow_database_probe(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def slow_execute(*args: object) -> None:
        del args
        await asyncio.sleep(READINESS_TIMEOUT_SECONDS * 2)

    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = slow_execute
    app = app_with_session(settings, session)
    monkeypatch.setattr("app.api.routes.health.READINESS_TIMEOUT_SECONDS", 0.001)

    async with api_client(app) as client:
        response = await client.get("/api/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


@pytest.mark.asyncio
async def test_api_routes_use_api_prefix(settings: Settings) -> None:
    app = create_app(settings, lifespan=no_database_lifespan)

    async with api_client(app) as client:
        prefixed = await client.get("/api/health")
        unprefixed = await client.get("/health")

    assert prefixed.status_code == 200
    assert unprefixed.status_code == 404


@pytest.mark.asyncio
async def test_cors_allows_only_configured_credentialed_origin(
    settings: Settings,
) -> None:
    app = create_app(settings, lifespan=no_database_lifespan)

    async with api_client(app) as client:
        allowed = await client.options(
            "/api/health",
            headers={
                "Origin": FRONTEND_ORIGIN,
                "Access-Control-Request-Method": "GET",
            },
        )
        disallowed = await client.options(
            "/api/health",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        simple_response = await client.get(
            "/api/health",
            headers={"Origin": FRONTEND_ORIGIN},
        )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == FRONTEND_ORIGIN
    assert allowed.headers["access-control-allow-credentials"] == "true"
    assert simple_response.headers["access-control-expose-headers"] == REQUEST_ID_HEADER
    assert "access-control-allow-origin" not in disallowed.headers


@pytest.mark.asyncio
async def test_non_production_exposes_openapi_with_stable_operations(
    settings: Settings,
) -> None:
    app = create_app(settings, lifespan=no_database_lifespan)

    async with api_client(app) as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    operations = response.json()["paths"]
    assert operations["/api/health"]["get"]["operationId"] == "get_health"
    assert operations["/api/ready"]["get"]["operationId"] == "get_readiness"


@pytest.mark.asyncio
async def test_production_hides_interactive_api_documentation() -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.PRODUCTION,
        database_url=DATABASE_URL,
        frontend_origin="https://stopimpulsebuying.us",
        session_cookie_secure=True,
    )
    app = create_app(settings, lifespan=no_database_lifespan)

    async with api_client(app) as client:
        openapi = await client.get("/openapi.json")
        docs = await client.get("/docs")
        redoc = await client.get("/redoc")

    assert openapi.status_code == 404
    assert docs.status_code == 404
    assert redoc.status_code == 404
