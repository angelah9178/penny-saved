"""Tests for the isolated fixed-window rate-limit contract."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from app.core.rate_limits import InMemoryRateLimitStore, digest_rate_limit_key

NOW = datetime(2026, 8, 7, 12, tzinfo=UTC)
DIGEST = "a" * 64
SECRET = b"a-test-only-rate-limit-secret-32-bytes"


def test_key_digest_is_irreversible_and_domain_separated() -> None:
    email = "person@example.com"

    login_digest = digest_rate_limit_key(
        secret=SECRET,
        domain="login.account",
        value=email,
    )
    signup_digest = digest_rate_limit_key(
        secret=SECRET,
        domain="signup.account",
        value=email,
    )

    assert len(login_digest) == 64
    assert email not in login_digest
    assert login_digest != signup_digest


@pytest.mark.parametrize(
    "overrides",
    [
        {"secret": b"short"},
        {"domain": "contains a space"},
        {"value": ""},
    ],
)
def test_invalid_key_digest_input_is_rejected(overrides: dict[str, object]) -> None:
    values: dict[str, object] = {
        "secret": SECRET,
        "domain": "login.account",
        "value": "person@example.com",
    }
    values.update(overrides)

    with pytest.raises(ValueError):
        digest_rate_limit_key(**values)  # type: ignore[arg-type]


async def consume(
    store: InMemoryRateLimitStore,
    *,
    now: datetime = NOW,
    bucket: str = "login.ip",
    key_digest: str = DIGEST,
    limit: int = 3,
    window_seconds: int = 60,
):  # type: ignore[no-untyped-def]
    return await store.consume(
        bucket=bucket,
        key_digest=key_digest,
        limit=limit,
        window_seconds=window_seconds,
        now=now,
    )


@pytest.mark.asyncio
async def test_fixed_window_allows_limit_then_returns_retry_delay() -> None:
    store = InMemoryRateLimitStore()

    first, second, final_allowed, blocked = [await consume(store) for _ in range(4)]

    assert [first.attempt_count, second.attempt_count, final_allowed.attempt_count] == [
        1,
        2,
        3,
    ]
    assert first.allowed and second.allowed and final_allowed.allowed
    assert blocked.allowed is False
    assert blocked.attempt_count == 4
    assert blocked.retry_after_seconds == 60
    assert blocked.resets_at == NOW + timedelta(seconds=60)


@pytest.mark.asyncio
async def test_exact_expiry_starts_a_fresh_window() -> None:
    store = InMemoryRateLimitStore()
    await consume(store)

    reset = await consume(store, now=NOW + timedelta(seconds=60))

    assert reset.allowed is True
    assert reset.attempt_count == 1
    assert reset.resets_at == NOW + timedelta(seconds=120)


@pytest.mark.asyncio
async def test_buckets_and_digests_have_independent_counters() -> None:
    store = InMemoryRateLimitStore()
    await consume(store)

    other_bucket = await consume(store, bucket="signup.ip")
    other_digest = await consume(store, key_digest="b" * 64)

    assert other_bucket.attempt_count == 1
    assert other_digest.attempt_count == 1


@pytest.mark.asyncio
async def test_concurrent_attempts_are_not_lost() -> None:
    store = InMemoryRateLimitStore()

    decisions = await asyncio.gather(*(consume(store, limit=100) for _ in range(50)))

    assert sorted(decision.attempt_count for decision in decisions) == list(range(1, 51))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"bucket": ""},
        {"bucket": "contains secret"},
        {"key_digest": "plaintext@example.com"},
        {"key_digest": "A" * 64},
        {"limit": 0},
        {"window_seconds": 0},
        {"now": datetime(2026, 8, 7, 12)},
    ],
)
async def test_invalid_counter_request_is_rejected(overrides: dict[str, object]) -> None:
    store = InMemoryRateLimitStore()

    with pytest.raises(ValueError):
        await consume(store, **overrides)  # type: ignore[arg-type]
