"""Tests for UTC clock behavior and dependency injection."""

from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated

import pytest
from app.core.time import (
    Clock,
    FixedClock,
    SystemClock,
    get_clock,
    normalize_utc,
)
from fastapi import Depends, FastAPI


def test_system_clock_returns_current_aware_utc_time() -> None:
    before = datetime.now(UTC)
    current_time = SystemClock().now()
    after = datetime.now(UTC)

    assert current_time.tzinfo is UTC
    assert before <= current_time <= after


def test_normalize_utc_converts_aware_non_utc_time() -> None:
    eastern_standard_time = timezone(timedelta(hours=-5))
    local_time = datetime(2026, 1, 15, 7, 30, tzinfo=eastern_standard_time)

    normalized = normalize_utc(local_time)

    assert normalized == datetime(2026, 1, 15, 12, 30, tzinfo=UTC)
    assert normalized.tzinfo is UTC


def test_normalize_utc_rejects_naive_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        normalize_utc(datetime(2026, 1, 15, 12, 30))


def test_fixed_clock_normalizes_and_repeats_configured_time() -> None:
    eastern_daylight_time = timezone(timedelta(hours=-4))
    clock = FixedClock(datetime(2026, 7, 23, 8, 15, tzinfo=eastern_daylight_time))

    expected = datetime(2026, 7, 23, 12, 15, tzinfo=UTC)
    assert clock.now() == expected
    assert clock.now() is clock.now()


def test_fixed_clock_rejects_naive_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        FixedClock(datetime(2026, 7, 23, 12, 15))


def test_get_clock_returns_production_clock() -> None:
    assert isinstance(get_clock(), SystemClock)


def test_fastapi_can_replace_clock_dependency() -> None:
    fixed_time = datetime(2026, 7, 23, 12, 15, tzinfo=UTC)
    fixed_clock = FixedClock(fixed_time)
    app = FastAPI()

    @app.get("/time")
    def read_time(clock: Annotated[Clock, Depends(get_clock)]) -> dict[str, str]:
        return {"now": clock.now().isoformat()}

    app.dependency_overrides[get_clock] = lambda: fixed_clock

    override = app.dependency_overrides[get_clock]
    assert override() is fixed_clock
