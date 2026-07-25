"""PostgreSQL integration tests for login-session lifecycle services."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from app.core.security import digest_session_token
from app.core.time import FixedClock
from app.models.session import Session
from app.models.user import User
from app.services.sessions import (
    SessionTokenCollisionError,
    create_session,
    resolve_session,
    revoke_session,
    stage_session,
)
from sqlalchemy import func, select
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

USER_ID = UUID("20000000-0000-4000-8000-000000000001")
OTHER_USER_ID = UUID("20000000-0000-4000-8000-000000000002")
NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
TTL_SECONDS = 2_592_000


@pytest.fixture
async def db(test_database_url: URL) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(test_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(Session.__table__.delete())
        await session.execute(User.__table__.delete())
        session.add_all(
            [
                User(
                    id=USER_ID,
                    email="user@example.com",
                    password_hash="argon2-hash-placeholder",
                    created_at=NOW,
                    updated_at=NOW,
                ),
                User(
                    id=OTHER_USER_ID,
                    email="other@example.com",
                    password_hash="argon2-hash-placeholder",
                    created_at=NOW,
                    updated_at=NOW,
                ),
            ]
        )
        await session.commit()
        try:
            yield session
        finally:
            await session.rollback()
            await session.execute(Session.__table__.delete())
            await session.execute(User.__table__.delete())
            await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_session_persists_only_digest_with_absolute_expiry(
    db: AsyncSession,
) -> None:
    raw_token = "raw-browser-token"

    issued = await create_session(
        db,
        user_id=USER_ID,
        clock=FixedClock(NOW),
        ttl_seconds=TTL_SECONDS,
        token_factory=lambda size: raw_token,
    )

    persisted = await db.scalar(select(Session))
    assert persisted is issued.session
    assert persisted is not None
    assert persisted.session_token_hash == digest_session_token(raw_token)
    assert persisted.session_token_hash != raw_token
    assert persisted.created_at == NOW
    assert persisted.last_used_at == NOW
    assert persisted.expires_at == NOW + timedelta(seconds=TTL_SECONDS)
    assert raw_token not in repr(issued)


@pytest.mark.asyncio
async def test_stage_session_rejects_invalid_ttl_without_writing(db: AsyncSession) -> None:
    with pytest.raises(ValueError, match="positive"):
        await stage_session(db, user_id=USER_ID, now=NOW, ttl_seconds=0)

    assert await db.scalar(select(func.count()).select_from(Session)) == 0


@pytest.mark.asyncio
async def test_token_collision_retries_without_discarding_outer_work(
    db: AsyncSession,
) -> None:
    first_raw_token = "existing-token"
    await create_session(
        db,
        user_id=USER_ID,
        clock=FixedClock(NOW),
        ttl_seconds=TTL_SECONDS,
        token_factory=lambda size: first_raw_token,
    )
    generated = iter([first_raw_token, "replacement-token"])
    staged_user = User(
        id=UUID("20000000-0000-4000-8000-000000000003"),
        email="staged@example.com",
        password_hash="argon2-hash-placeholder",
        created_at=NOW,
        updated_at=NOW,
    )
    db.add(staged_user)

    issued = await stage_session(
        db,
        user_id=staged_user.id,
        now=NOW,
        ttl_seconds=TTL_SECONDS,
        token_factory=lambda size: next(generated),
    )
    await db.commit()

    assert issued.raw_token == "replacement-token"
    assert await db.get(User, staged_user.id) is not None
    assert await db.scalar(select(func.count()).select_from(Session)) == 2


@pytest.mark.asyncio
async def test_repeated_token_collisions_fail_without_partial_session(
    db: AsyncSession,
) -> None:
    raw_token = "always-the-same"
    await create_session(
        db,
        user_id=USER_ID,
        clock=FixedClock(NOW),
        ttl_seconds=TTL_SECONDS,
        token_factory=lambda size: raw_token,
    )

    with pytest.raises(SessionTokenCollisionError):
        await stage_session(
            db,
            user_id=OTHER_USER_ID,
            now=NOW,
            ttl_seconds=TTL_SECONDS,
            token_factory=lambda size: raw_token,
        )

    assert await db.scalar(select(func.count()).select_from(Session)) == 1


@pytest.mark.asyncio
async def test_resolve_session_returns_user_without_early_last_used_write(
    db: AsyncSession,
) -> None:
    issued = await create_session(
        db,
        user_id=USER_ID,
        clock=FixedClock(NOW),
        ttl_seconds=TTL_SECONDS,
        token_factory=lambda size: "valid-token",
    )

    resolved = await resolve_session(
        db,
        raw_token=issued.raw_token,
        clock=FixedClock(NOW + timedelta(minutes=59, seconds=59)),
    )

    assert resolved is not None
    assert resolved.user.id == USER_ID
    assert resolved.session.last_used_at == NOW


@pytest.mark.asyncio
async def test_resolve_session_updates_last_used_at_at_one_hour_boundary(
    db: AsyncSession,
) -> None:
    issued = await create_session(
        db,
        user_id=USER_ID,
        clock=FixedClock(NOW),
        ttl_seconds=TTL_SECONDS,
        token_factory=lambda size: "active-token",
    )
    activity_time = NOW + timedelta(hours=1)

    resolved = await resolve_session(
        db,
        raw_token=issued.raw_token,
        clock=FixedClock(activity_time),
    )

    assert resolved is not None
    assert resolved.session.last_used_at == activity_time
    assert resolved.session.expires_at == NOW + timedelta(seconds=TTL_SECONDS)


@pytest.mark.asyncio
async def test_exact_expiry_is_rejected_and_deleted(db: AsyncSession) -> None:
    issued = await create_session(
        db,
        user_id=USER_ID,
        clock=FixedClock(NOW),
        ttl_seconds=TTL_SECONDS,
        token_factory=lambda size: "expiring-token",
    )

    resolved = await resolve_session(
        db,
        raw_token=issued.raw_token,
        clock=FixedClock(NOW + timedelta(seconds=TTL_SECONDS)),
    )

    assert resolved is None
    assert await db.scalar(select(func.count()).select_from(Session)) == 0


@pytest.mark.asyncio
async def test_unknown_session_returns_none_without_mutation(db: AsyncSession) -> None:
    assert (
        await resolve_session(
            db,
            raw_token="unknown-token",
            clock=FixedClock(NOW),
        )
        is None
    )
    assert await db.scalar(select(func.count()).select_from(Session)) == 0


@pytest.mark.asyncio
async def test_revoke_session_deletes_only_presented_session(db: AsyncSession) -> None:
    first = await create_session(
        db,
        user_id=USER_ID,
        clock=FixedClock(NOW),
        ttl_seconds=TTL_SECONDS,
        token_factory=lambda size: "first-token",
    )
    second = await create_session(
        db,
        user_id=USER_ID,
        clock=FixedClock(NOW),
        ttl_seconds=TTL_SECONDS,
        token_factory=lambda size: "second-token",
    )

    assert await revoke_session(db, raw_token=first.raw_token)
    assert not await revoke_session(db, raw_token=first.raw_token)
    assert await db.scalar(select(func.count()).select_from(Session)) == 1
    assert await resolve_session(
        db,
        raw_token=second.raw_token,
        clock=FixedClock(NOW),
    )
