"""Shared and isolated fixed-window rate-limit stores."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from app.core.time import normalize_utc
from app.db.session import SessionFactory
from app.models.rate_limit_counter import RateLimitCounter
from sqlalchemy import case, delete
from sqlalchemy.dialects.postgresql import insert

_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_BUCKET_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,63}$")
_STALE_RETENTION = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    """Result of atomically consuming one attempt from a fixed window."""

    allowed: bool
    attempt_count: int
    retry_after_seconds: int
    resets_at: datetime


class RateLimitStore(Protocol):
    """Storage contract shared by production and isolated tests."""

    async def consume(
        self,
        *,
        bucket: str,
        key_digest: str,
        limit: int,
        window_seconds: int,
        now: datetime,
    ) -> RateLimitDecision:
        """Atomically record one attempt and return the resulting decision."""
        ...


def digest_rate_limit_key(*, secret: bytes, domain: str, value: str) -> str:
    """Create a domain-separated irreversible key without retaining the raw value."""
    if len(secret) < 32:
        raise ValueError("Rate-limit digest secret must contain at least 32 bytes")
    if not _BUCKET_PATTERN.fullmatch(domain):
        raise ValueError("Rate-limit digest domain must be a stable identifier")
    if not value:
        raise ValueError("Rate-limit digest value must not be empty")
    return hmac.new(secret, f"{domain}\0{value}".encode(), hashlib.sha256).hexdigest()


def _validate_request(
    *,
    bucket: str,
    key_digest: str,
    limit: int,
    window_seconds: int,
    now: datetime,
) -> datetime:
    if not _BUCKET_PATTERN.fullmatch(bucket):
        raise ValueError("Rate-limit bucket must be a stable, non-secret identifier")
    if not _DIGEST_PATTERN.fullmatch(key_digest):
        raise ValueError("Rate-limit keys must be lowercase SHA-256 digests")
    if limit <= 0:
        raise ValueError("Rate limit must be positive")
    if window_seconds <= 0:
        raise ValueError("Rate-limit window must be positive")
    return normalize_utc(now)


def _decision(
    *, attempt_count: int, limit: int, now: datetime, expires_at: datetime
) -> RateLimitDecision:
    allowed = attempt_count <= limit
    retry_after = max(1, math.ceil((expires_at - now).total_seconds())) if not allowed else 0
    return RateLimitDecision(
        allowed=allowed,
        attempt_count=attempt_count,
        retry_after_seconds=retry_after,
        resets_at=expires_at,
    )


class PostgresRateLimitStore:
    """Atomic counter store shared by every worker using the same PostgreSQL database."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def consume(
        self,
        *,
        bucket: str,
        key_digest: str,
        limit: int,
        window_seconds: int,
        now: datetime,
    ) -> RateLimitDecision:
        now = _validate_request(
            bucket=bucket,
            key_digest=key_digest,
            limit=limit,
            window_seconds=window_seconds,
            now=now,
        )
        new_expiry = now + timedelta(seconds=window_seconds)
        table = RateLimitCounter.__table__
        expired = table.c.expires_at <= now
        statement = (
            insert(table)
            .values(
                bucket=bucket,
                key_digest=key_digest,
                attempt_count=1,
                window_started_at=now,
                expires_at=new_expiry,
            )
            .on_conflict_do_update(
                index_elements=[table.c.bucket, table.c.key_digest],
                set_={
                    "attempt_count": case((expired, 1), else_=table.c.attempt_count + 1),
                    "window_started_at": case(
                        (expired, now),
                        else_=table.c.window_started_at,
                    ),
                    "expires_at": case((expired, new_expiry), else_=table.c.expires_at),
                },
            )
            .returning(table.c.attempt_count, table.c.expires_at)
        )

        async with self._session_factory.begin() as db:
            await db.execute(delete(table).where(table.c.expires_at < now - _STALE_RETENTION))
            row = (await db.execute(statement)).one()

        return _decision(
            attempt_count=row.attempt_count,
            limit=limit,
            now=now,
            expires_at=normalize_utc(row.expires_at),
        )


class InMemoryRateLimitStore:
    """Deterministic isolated store for tests; never use it for deployment."""

    def __init__(self) -> None:
        self._counters: dict[tuple[str, str], tuple[int, datetime]] = {}
        self._lock = asyncio.Lock()

    async def consume(
        self,
        *,
        bucket: str,
        key_digest: str,
        limit: int,
        window_seconds: int,
        now: datetime,
    ) -> RateLimitDecision:
        now = _validate_request(
            bucket=bucket,
            key_digest=key_digest,
            limit=limit,
            window_seconds=window_seconds,
            now=now,
        )
        key = (bucket, key_digest)
        async with self._lock:
            current = self._counters.get(key)
            if current is None or current[1] <= now:
                attempt_count = 1
                expires_at = now + timedelta(seconds=window_seconds)
            else:
                attempt_count = current[0] + 1
                expires_at = current[1]
            self._counters[key] = (attempt_count, expires_at)
        return _decision(
            attempt_count=attempt_count,
            limit=limit,
            now=now,
            expires_at=expires_at,
        )
