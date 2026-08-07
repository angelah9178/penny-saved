"""PostgreSQL service and API integration tests for signup."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx
import pytest
from app.api.dependencies import get_rate_limit_store
from app.api.errors import ApplicationError
from app.core.config import AppEnvironment, Settings
from app.core.rate_limits import InMemoryRateLimitStore
from app.core.security import verify_password
from app.core.time import FixedClock, get_clock
from app.db.session import get_db_session
from app.main import create_app
from app.models.session import Session
from app.models.user import User
from app.schemas.auth import AuthRequest
from app.services.auth import signup
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
PASSWORD = "password123"


def _settings(test_database_url: URL) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_url=test_database_url.render_as_string(hide_password=False),
        session_cookie_name="signup_session",
        session_ttl_seconds=2_592_000,
    )


@pytest.fixture
async def signup_database(
    test_database_url: URL,
) -> AsyncIterator[tuple[AsyncEngine, async_sessionmaker[AsyncSession]]]:
    engine = create_async_engine(test_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(Session.__table__.delete())
        await db.execute(User.__table__.delete())
        await db.commit()
    try:
        yield engine, factory
    finally:
        async with factory() as db:
            await db.execute(Session.__table__.delete())
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


def signup_app(
    *,
    settings: Settings,
    db: AsyncSession,
) -> FastAPI:
    app = create_app(settings, lifespan=no_database_lifespan)

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_clock] = lambda: FixedClock(NOW)
    app.dependency_overrides[get_rate_limit_store] = InMemoryRateLimitStore
    return app


@pytest.mark.asyncio
async def test_signup_creates_normalized_user_and_initial_session_atomically(
    signup_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    test_database_url: URL,
) -> None:
    _, factory = signup_database
    settings = _settings(test_database_url)
    async with factory() as db:
        result = await signup(
            db,
            credentials=AuthRequest(
                email="  Person@Example.COM  ",
                password=PASSWORD,
            ),
            clock=FixedClock(NOW),
            settings=settings,
        )

        assert result.user.email == "person@example.com"
        assert result.user.password_hash != PASSWORD
        assert verify_password(PASSWORD, result.user.password_hash)
        assert result.issued_session.session.user_id == result.user.id
        assert await db.scalar(select(func.count()).select_from(User)) == 1
        assert await db.scalar(select(func.count()).select_from(Session)) == 1


@pytest.mark.asyncio
async def test_signup_rejects_duplicate_normalized_email_without_second_session(
    signup_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    test_database_url: URL,
) -> None:
    _, factory = signup_database
    settings = _settings(test_database_url)
    async with factory() as db:
        await signup(
            db,
            credentials=AuthRequest(email="person@example.com", password=PASSWORD),
            clock=FixedClock(NOW),
            settings=settings,
        )

        with pytest.raises(ApplicationError) as raised:
            await signup(
                db,
                credentials=AuthRequest(
                    email=" PERSON@EXAMPLE.COM ",
                    password="different-password",
                ),
                clock=FixedClock(NOW),
                settings=settings,
            )

        assert raised.value.status_code == 409
        assert raised.value.code == "duplicate_email"
        assert await db.scalar(select(func.count()).select_from(User)) == 1
        assert await db.scalar(select(func.count()).select_from(Session)) == 1


@pytest.mark.asyncio
async def test_concurrent_duplicate_signup_creates_exactly_one_account(
    signup_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    test_database_url: URL,
) -> None:
    _, factory = signup_database
    settings = _settings(test_database_url)

    async def attempt(email: str) -> object:
        async with factory() as db:
            return await signup(
                db,
                credentials=AuthRequest(email=email, password=PASSWORD),
                clock=FixedClock(NOW),
                settings=settings,
            )

    results = await asyncio.gather(
        attempt("race@example.com"),
        attempt(" RACE@EXAMPLE.COM "),
        return_exceptions=True,
    )

    failures = [result for result in results if isinstance(result, ApplicationError)]
    assert len(failures) == 1
    assert failures[0].code == "duplicate_email"
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(User)) == 1
        assert await db.scalar(select(func.count()).select_from(Session)) == 1


@pytest.mark.asyncio
async def test_signup_rolls_back_user_when_session_creation_fails(
    signup_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    test_database_url: URL,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, factory = signup_database

    async def fail_session_creation(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError("injected session failure")

    monkeypatch.setattr("app.services.auth.stage_session", fail_session_creation)
    async with factory() as db:
        with pytest.raises(RuntimeError, match="injected session failure"):
            await signup(
                db,
                credentials=AuthRequest(email="rollback@example.com", password=PASSWORD),
                clock=FixedClock(NOW),
                settings=_settings(test_database_url),
            )

        assert await db.scalar(select(func.count()).select_from(User)) == 0
        assert await db.scalar(select(func.count()).select_from(Session)) == 0


@pytest.mark.asyncio
async def test_signup_api_returns_public_user_and_login_cookie(
    signup_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    test_database_url: URL,
) -> None:
    _, factory = signup_database
    settings = _settings(test_database_url)
    async with factory() as db:
        app = signup_app(settings=settings, db=db)
        async with api_client(app) as client:
            response = await client.post(
                "/api/auth/signup",
                json={"email": " Person@Example.COM ", "password": PASSWORD},
            )

        assert response.status_code == 201
        body = response.json()
        assert body["user"]["email"] == "person@example.com"
        assert set(body["user"]) == {"id", "email"}
        assert PASSWORD not in response.text
        cookie = response.headers["set-cookie"]
        assert "signup_session=" in cookie
        assert "HttpOnly" in cookie
        assert "SameSite=lax" in cookie


@pytest.mark.asyncio
async def test_signup_api_returns_safe_duplicate_email_error(
    signup_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    test_database_url: URL,
) -> None:
    _, factory = signup_database
    settings = _settings(test_database_url)
    async with factory() as db:
        app = signup_app(settings=settings, db=db)
        async with api_client(app) as client:
            first = await client.post(
                "/api/auth/signup",
                json={"email": "duplicate@example.com", "password": PASSWORD},
            )
            duplicate = await client.post(
                "/api/auth/signup",
                json={"email": " DUPLICATE@EXAMPLE.COM ", "password": PASSWORD},
            )

        assert first.status_code == 201
        assert duplicate.status_code == 409
        assert duplicate.json() == {
            "error": {
                "code": "duplicate_email",
                "message": "An account with this email already exists.",
            }
        }
        assert PASSWORD not in duplicate.text


@pytest.mark.asyncio
async def test_signup_api_rejects_invalid_and_unknown_fields_safely(
    signup_database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    test_database_url: URL,
) -> None:
    _, factory = signup_database
    async with factory() as db:
        app = signup_app(settings=_settings(test_database_url), db=db)
        async with api_client(app) as client:
            response = await client.post(
                "/api/auth/signup",
                json={
                    "email": "invalid-email",
                    "password": "short",
                    "is_admin": True,
                },
            )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
        assert "short" not in response.text
        assert await db.scalar(select(func.count()).select_from(User)) == 0
