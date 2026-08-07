"""PostgreSQL service and API integration tests for login."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from app.api.dependencies import get_rate_limit_store
from app.api.errors import ApplicationError
from app.core.config import AppEnvironment, Settings
from app.core.rate_limits import InMemoryRateLimitStore
from app.core.security import verify_and_update_password, verify_password
from app.core.time import FixedClock, get_clock
from app.db.session import get_db_session
from app.main import create_app
from app.models.session import Session
from app.models.user import User
from app.schemas.auth import AuthRequest
from app.services.auth import DUMMY_PASSWORD_HASH, login, signup
from fastapi import FastAPI
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlalchemy import func, select
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
LOGIN_TIME = NOW + timedelta(days=1)
PASSWORD = "password123"
INVALID_RESPONSE = {
    "error": {
        "code": "invalid_credentials",
        "message": "Email or password is incorrect.",
    }
}


def _settings(test_database_url: URL) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_url=test_database_url.render_as_string(hide_password=False),
        session_cookie_name="login_session",
        session_ttl_seconds=2_592_000,
    )


@pytest.fixture
async def login_database(
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


def login_app(*, settings: Settings, db: AsyncSession) -> FastAPI:
    app = create_app(settings, lifespan=no_database_lifespan)

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_clock] = lambda: FixedClock(LOGIN_TIME)
    app.dependency_overrides[get_rate_limit_store] = InMemoryRateLimitStore
    return app


async def create_account(
    db: AsyncSession,
    *,
    settings: Settings,
    email: str = "person@example.com",
    password: str = PASSWORD,
) -> User:
    result = await signup(
        db,
        credentials=AuthRequest(email=email, password=password),
        clock=FixedClock(NOW),
        settings=settings,
    )
    return result.user


@pytest.mark.asyncio
async def test_login_normalizes_email_and_creates_an_independent_session(
    login_database: async_sessionmaker[AsyncSession],
    test_database_url: URL,
) -> None:
    settings = _settings(test_database_url)
    async with login_database() as db:
        user = await create_account(db, settings=settings)

        result = await login(
            db,
            credentials=AuthRequest(email=" PERSON@EXAMPLE.COM ", password=PASSWORD),
            clock=FixedClock(LOGIN_TIME),
            settings=settings,
        )

        assert result.user.id == user.id
        assert result.user.email == "person@example.com"
        assert result.issued_session.session.user_id == user.id
        assert await db.scalar(select(func.count()).select_from(Session)) == 2


@pytest.mark.asyncio
async def test_unknown_email_uses_fixed_dummy_hash_and_safe_error(
    login_database: async_sessionmaker[AsyncSession],
    test_database_url: URL,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    def tracked_verify(password: str, password_hash: str) -> tuple[bool, str | None]:
        calls.append((password, password_hash))
        return verify_and_update_password(password, password_hash)

    monkeypatch.setattr("app.services.auth.verify_and_update_password", tracked_verify)
    async with login_database() as db:
        with pytest.raises(ApplicationError) as raised:
            await login(
                db,
                credentials=AuthRequest(email="missing@example.com", password=PASSWORD),
                clock=FixedClock(LOGIN_TIME),
                settings=_settings(test_database_url),
            )

        assert raised.value.status_code == 401
        assert raised.value.code == "invalid_credentials"
        assert calls == [(PASSWORD, DUMMY_PASSWORD_HASH)]
        assert await db.scalar(select(func.count()).select_from(Session)) == 0


@pytest.mark.asyncio
async def test_wrong_password_returns_same_safe_error_without_session(
    login_database: async_sessionmaker[AsyncSession],
    test_database_url: URL,
) -> None:
    settings = _settings(test_database_url)
    async with login_database() as db:
        await create_account(db, settings=settings)

        with pytest.raises(ApplicationError) as raised:
            await login(
                db,
                credentials=AuthRequest(
                    email="person@example.com",
                    password="wrong-password",
                ),
                clock=FixedClock(LOGIN_TIME),
                settings=settings,
            )

        assert raised.value.status_code == 401
        assert raised.value.code == "invalid_credentials"
        assert await db.scalar(select(func.count()).select_from(Session)) == 1


@pytest.mark.asyncio
async def test_malformed_stored_hash_returns_invalid_credentials(
    login_database: async_sessionmaker[AsyncSession],
    test_database_url: URL,
) -> None:
    async with login_database() as db:
        db.add(
            User(
                email="broken@example.com",
                password_hash="not-a-password-hash",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        await db.commit()

        with pytest.raises(ApplicationError) as raised:
            await login(
                db,
                credentials=AuthRequest(email="broken@example.com", password=PASSWORD),
                clock=FixedClock(LOGIN_TIME),
                settings=_settings(test_database_url),
            )

        assert raised.value.code == "invalid_credentials"
        assert await db.scalar(select(func.count()).select_from(Session)) == 0


@pytest.mark.asyncio
async def test_login_upgrades_outdated_argon2_hash_in_same_transaction(
    login_database: async_sessionmaker[AsyncSession],
    test_database_url: URL,
) -> None:
    outdated_hasher = PasswordHash((Argon2Hasher(time_cost=1, memory_cost=8_192, parallelism=1),))
    outdated_hash = outdated_hasher.hash(PASSWORD)
    async with login_database() as db:
        user = User(
            email="upgrade@example.com",
            password_hash=outdated_hash,
            created_at=NOW,
            updated_at=NOW,
        )
        db.add(user)
        await db.commit()

        await login(
            db,
            credentials=AuthRequest(email=user.email, password=PASSWORD),
            clock=FixedClock(LOGIN_TIME),
            settings=_settings(test_database_url),
        )

        await db.refresh(user)
        assert user.password_hash != outdated_hash
        assert verify_password(PASSWORD, user.password_hash)
        assert user.updated_at == LOGIN_TIME
        assert await db.scalar(select(func.count()).select_from(Session)) == 1


@pytest.mark.asyncio
async def test_session_failure_rolls_back_password_hash_upgrade(
    login_database: async_sessionmaker[AsyncSession],
    test_database_url: URL,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outdated_hasher = PasswordHash((Argon2Hasher(time_cost=1, memory_cost=8_192, parallelism=1),))
    outdated_hash = outdated_hasher.hash(PASSWORD)
    async with login_database() as db:
        user = User(
            email="rollback@example.com",
            password_hash=outdated_hash,
            created_at=NOW,
            updated_at=NOW,
        )
        db.add(user)
        await db.commit()

        async def fail_session(*args: object, **kwargs: object) -> None:
            del args, kwargs
            raise RuntimeError("injected session failure")

        monkeypatch.setattr("app.services.auth.stage_session", fail_session)
        with pytest.raises(RuntimeError, match="injected session failure"):
            await login(
                db,
                credentials=AuthRequest(email=user.email, password=PASSWORD),
                clock=FixedClock(LOGIN_TIME),
                settings=_settings(test_database_url),
            )

        await db.refresh(user)
        assert user.password_hash == outdated_hash
        assert user.updated_at == NOW
        assert await db.scalar(select(func.count()).select_from(Session)) == 0


@pytest.mark.asyncio
async def test_login_api_returns_public_user_and_new_cookie(
    login_database: async_sessionmaker[AsyncSession],
    test_database_url: URL,
) -> None:
    settings = _settings(test_database_url)
    async with login_database() as db:
        user = await create_account(db, settings=settings)
        app = login_app(settings=settings, db=db)

        async with api_client(app) as client:
            response = await client.post(
                "/api/auth/login",
                json={"email": " PERSON@EXAMPLE.COM ", "password": PASSWORD},
            )

        assert response.status_code == 200
        assert response.json() == {
            "user": {
                "id": str(user.id),
                "email": "person@example.com",
            }
        }
        assert PASSWORD not in response.text
        assert "login_session=" in response.headers["set-cookie"]
        assert "HttpOnly" in response.headers["set-cookie"]
        assert await db.scalar(select(func.count()).select_from(Session)) == 2


@pytest.mark.asyncio
async def test_login_api_unknown_email_and_wrong_password_are_equivalent(
    login_database: async_sessionmaker[AsyncSession],
    test_database_url: URL,
) -> None:
    settings = _settings(test_database_url)
    async with login_database() as db:
        await create_account(db, settings=settings)
        app = login_app(settings=settings, db=db)

        async with api_client(app) as client:
            unknown = await client.post(
                "/api/auth/login",
                json={"email": "unknown@example.com", "password": PASSWORD},
            )
            wrong = await client.post(
                "/api/auth/login",
                json={"email": "person@example.com", "password": "wrong-password"},
            )

        assert unknown.status_code == wrong.status_code == 401
        assert unknown.json() == wrong.json() == INVALID_RESPONSE
        assert "set-cookie" not in unknown.headers
        assert "set-cookie" not in wrong.headers
        assert PASSWORD not in unknown.text
        assert "wrong-password" not in wrong.text
        assert await db.scalar(select(func.count()).select_from(Session)) == 1
