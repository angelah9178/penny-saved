"""PostgreSQL integration tests for shared atomic rate-limit counters."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from app.core.rate_limits import PostgresRateLimitStore
from app.models.rate_limit_counter import RateLimitCounter
from sqlalchemy import select
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

NOW = datetime(2026, 8, 7, 12, tzinfo=UTC)
DIGEST = "c" * 64


@pytest.mark.asyncio
async def test_postgres_store_is_shared_atomic_and_resets_at_expiry(
    test_database_url: URL,
) -> None:
    engine = create_async_engine(test_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    store_a = PostgresRateLimitStore(factory)
    store_b = PostgresRateLimitStore(factory)
    try:
        async with factory.begin() as db:
            await db.execute(RateLimitCounter.__table__.delete())

        decisions = await asyncio.gather(
            *(
                (store_a if index % 2 == 0 else store_b).consume(
                    bucket="login.account",
                    key_digest=DIGEST,
                    limit=5,
                    window_seconds=60,
                    now=NOW,
                )
                for index in range(12)
            )
        )

        assert sorted(decision.attempt_count for decision in decisions) == list(range(1, 13))
        assert sum(decision.allowed for decision in decisions) == 5
        assert {decision.retry_after_seconds for decision in decisions if not decision.allowed} == {
            60
        }

        reset = await store_b.consume(
            bucket="login.account",
            key_digest=DIGEST,
            limit=5,
            window_seconds=60,
            now=NOW + timedelta(seconds=60),
        )
        assert reset.allowed is True
        assert reset.attempt_count == 1

        async with factory() as db:
            rows = (await db.scalars(select(RateLimitCounter))).all()
        assert len(rows) == 1
        assert rows[0].key_digest == DIGEST
        assert "@" not in rows[0].key_digest
    finally:
        async with factory.begin() as db:
            await db.execute(RateLimitCounter.__table__.delete())
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_store_keeps_buckets_and_keys_independent(
    test_database_url: URL,
) -> None:
    engine = create_async_engine(test_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    store = PostgresRateLimitStore(factory)
    try:
        async with factory.begin() as db:
            await db.execute(RateLimitCounter.__table__.delete())

        decisions = await asyncio.gather(
            store.consume(
                bucket="login.ip",
                key_digest=DIGEST,
                limit=1,
                window_seconds=60,
                now=NOW,
            ),
            store.consume(
                bucket="signup.ip",
                key_digest=DIGEST,
                limit=1,
                window_seconds=60,
                now=NOW,
            ),
            store.consume(
                bucket="login.ip",
                key_digest="d" * 64,
                limit=1,
                window_seconds=60,
                now=NOW,
            ),
        )
        assert all(decision.allowed for decision in decisions)
        assert all(decision.attempt_count == 1 for decision in decisions)
    finally:
        async with factory.begin() as db:
            await db.execute(RateLimitCounter.__table__.delete())
        await engine.dispose()
