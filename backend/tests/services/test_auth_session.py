"""PostgreSQL API integration tests for current-session resolution and logout."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from app.api.dependencies import get_rate_limit_store
from app.core.config import AppEnvironment, Settings
from app.core.rate_limits import InMemoryRateLimitStore
from app.core.security import digest_session_token, generate_session_token
from app.core.time import FixedClock, get_clock
from app.db.session import get_db_session
from app.main import create_app
from app.models.session import Session
from app.models.user import User
from app.schemas.auth import AuthRequest
from app.services.auth import signup
from app.services.sessions import create_session
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
PASSWORD = "password123"
UNAUTHORIZED_RESPONSE = {
    "error": {
        "code": "unauthorized",
        "message": "Authentication is required.",
    }
}


def _settings(test_database_url: URL, *, ttl_seconds: int = 2_592_000) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_url=test_database_url.render_as_string(hide_password=False),
        frontend_origin="http://localhost:5173",
        session_cookie_name="current_session",
        session_ttl_seconds=ttl_seconds,
    )


@pytest.fixture
async def session_database(
    test_database_url: URL,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(test_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(Session.__table__.delete())
        await db.execute(User.__table__.delete())
        await db.commit()
    try:
        yield factory
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


def session_app(
    *,
    settings: Settings,
    db: AsyncSession,
    current_time: datetime,
) -> FastAPI:
    app = create_app(settings, lifespan=no_database_lifespan)

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_clock] = lambda: FixedClock(current_time)
    app.dependency_overrides[get_rate_limit_store] = InMemoryRateLimitStore
    return app


async def create_account_session(
    db: AsyncSession,
    *,
    settings: Settings,
) -> tuple[User, str]:
    result = await signup(
        db,
        credentials=AuthRequest(email="person@example.com", password=PASSWORD),
        clock=FixedClock(NOW),
        settings=settings,
    )
    return result.user, result.issued_session.raw_token


@pytest.mark.asyncio
async def test_me_returns_public_user_for_valid_session(
    session_database: async_sessionmaker[AsyncSession],
    test_database_url: URL,
) -> None:
    settings = _settings(test_database_url)
    async with session_database() as db:
        user, raw_token = await create_account_session(db, settings=settings)
        app = session_app(settings=settings, db=db, current_time=NOW)

        async with api_client(app) as client:
            client.cookies.set(settings.session_cookie_name, raw_token)
            response = await client.get("/api/auth/me")

        assert response.status_code == 200
        assert response.json() == {
            "user": {
                "id": str(user.id),
                "email": user.email,
            }
        }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw_token",
    [
        None,
        "malformed token",
        generate_session_token(),
    ],
    ids=["missing", "malformed", "unknown"],
)
async def test_me_returns_same_safe_unauthorized_for_invalid_session_classes(
    session_database: async_sessionmaker[AsyncSession],
    test_database_url: URL,
    raw_token: str | None,
) -> None:
    settings = _settings(test_database_url)
    async with session_database() as db:
        app = session_app(settings=settings, db=db, current_time=NOW)

        async with api_client(app) as client:
            if raw_token is not None:
                client.cookies.set(settings.session_cookie_name, raw_token)
            response = await client.get("/api/auth/me")

        assert response.status_code == 401
        assert response.json() == UNAUTHORIZED_RESPONSE


@pytest.mark.asyncio
async def test_me_rejects_and_deletes_session_at_exact_expiry(
    session_database: async_sessionmaker[AsyncSession],
    test_database_url: URL,
) -> None:
    settings = _settings(test_database_url, ttl_seconds=60)
    async with session_database() as db:
        _, raw_token = await create_account_session(db, settings=settings)
        app = session_app(
            settings=settings,
            db=db,
            current_time=NOW + timedelta(seconds=60),
        )

        async with api_client(app) as client:
            client.cookies.set(settings.session_cookie_name, raw_token)
            response = await client.get("/api/auth/me")

        assert response.status_code == 401
        assert response.json() == UNAUTHORIZED_RESPONSE
        assert await db.scalar(select(func.count()).select_from(Session)) == 0


@pytest.mark.asyncio
async def test_me_updates_last_used_at_at_hour_boundary_without_extending_expiry(
    session_database: async_sessionmaker[AsyncSession],
    test_database_url: URL,
) -> None:
    settings = _settings(test_database_url)
    async with session_database() as db:
        _, raw_token = await create_account_session(db, settings=settings)
        original_expiry = await db.scalar(
            select(Session.expires_at).where(
                Session.session_token_hash == digest_session_token(raw_token)
            )
        )
        activity_time = NOW + timedelta(hours=1)
        app = session_app(settings=settings, db=db, current_time=activity_time)

        async with api_client(app) as client:
            client.cookies.set(settings.session_cookie_name, raw_token)
            response = await client.get("/api/auth/me")

        session = await db.scalar(
            select(Session).where(Session.session_token_hash == digest_session_token(raw_token))
        )
        assert response.status_code == 200
        assert session is not None
        assert session.last_used_at == activity_time
        assert session.expires_at == original_expiry


@pytest.mark.asyncio
async def test_logout_revokes_only_presented_session_and_clears_cookie(
    session_database: async_sessionmaker[AsyncSession],
    test_database_url: URL,
) -> None:
    settings = _settings(test_database_url)
    async with session_database() as db:
        user, first_token = await create_account_session(db, settings=settings)
        second = await create_session(
            db,
            user_id=user.id,
            clock=FixedClock(NOW),
            ttl_seconds=settings.session_ttl_seconds,
        )
        app = session_app(settings=settings, db=db, current_time=NOW)

        async with api_client(app) as client:
            client.cookies.set(settings.session_cookie_name, first_token)
            response = await client.post("/api/auth/logout")

        assert response.status_code == 200
        assert response.content == b""
        clear_cookie = response.headers["set-cookie"]
        assert "current_session=" in clear_cookie
        assert "Max-Age=0" in clear_cookie
        assert "HttpOnly" in clear_cookie
        assert "Path=/" in clear_cookie
        assert "SameSite=lax" in clear_cookie
        assert await db.scalar(select(func.count()).select_from(Session)) == 1
        remaining_digest = await db.scalar(select(Session.session_token_hash))
        assert remaining_digest == digest_session_token(second.raw_token)


@pytest.mark.asyncio
async def test_logout_is_idempotent_for_repeated_missing_and_malformed_cookies(
    session_database: async_sessionmaker[AsyncSession],
    test_database_url: URL,
) -> None:
    settings = _settings(test_database_url)
    async with session_database() as db:
        app = session_app(settings=settings, db=db, current_time=NOW)

        async with api_client(app) as client:
            missing = await client.post("/api/auth/logout")
            client.cookies.set(settings.session_cookie_name, "malformed token")
            malformed = await client.post("/api/auth/logout")
            client.cookies.clear()
            repeated = await client.post("/api/auth/logout")

        assert missing.status_code == malformed.status_code == repeated.status_code == 200
        assert "Max-Age=0" in missing.headers["set-cookie"]
        assert "Max-Age=0" in malformed.headers["set-cookie"]
        assert "Max-Age=0" in repeated.headers["set-cookie"]
        assert await db.scalar(select(func.count()).select_from(Session)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("origin", "expected_status"),
    [
        ("http://localhost:5173", 200),
        (None, 200),
        ("https://untrusted.example", 403),
        ("not-an-origin", 403),
    ],
    ids=["allowed", "missing", "mismatched", "malformed"],
)
async def test_logout_enforces_exact_browser_origin_before_mutation(
    session_database: async_sessionmaker[AsyncSession],
    test_database_url: URL,
    origin: str | None,
    expected_status: int,
) -> None:
    settings = _settings(test_database_url)
    async with session_database() as db:
        _, raw_token = await create_account_session(db, settings=settings)
        app = session_app(settings=settings, db=db, current_time=NOW)
        headers = {"Origin": origin} if origin is not None else {}

        async with api_client(app) as client:
            client.cookies.set(settings.session_cookie_name, raw_token)
            response = await client.post("/api/auth/logout", headers=headers)

        assert response.status_code == expected_status
        expected_sessions = 0 if expected_status == 200 else 1
        assert await db.scalar(select(func.count()).select_from(Session)) == expected_sessions
        if expected_status == 403:
            assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_complete_authentication_lifecycle(
    session_database: async_sessionmaker[AsyncSession],
    test_database_url: URL,
) -> None:
    settings = _settings(test_database_url)
    async with session_database() as db:
        app = session_app(settings=settings, db=db, current_time=NOW)

        async with api_client(app) as client:
            signup_response = await client.post(
                "/api/auth/signup",
                json={"email": " Lifecycle@Example.COM ", "password": PASSWORD},
            )
            signed_up_me = await client.get("/api/auth/me")
            logout_response = await client.post("/api/auth/logout")
            logged_out_me = await client.get("/api/auth/me")
            login_response = await client.post(
                "/api/auth/login",
                json={"email": "lifecycle@example.com", "password": PASSWORD},
            )
            logged_in_me = await client.get("/api/auth/me")

        assert signup_response.status_code == 201
        assert signed_up_me.status_code == 200
        assert logout_response.status_code == 200
        assert logged_out_me.status_code == 401
        assert logged_out_me.json() == UNAUTHORIZED_RESPONSE
        assert login_response.status_code == 200
        assert logged_in_me.status_code == 200
        assert signed_up_me.json() == login_response.json() == logged_in_me.json()
