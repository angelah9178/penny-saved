"""UTC clock tests."""

from datetime import UTC

from app.core.time import UtcClock


def test_utc_clock_returns_aware_utc_time() -> None:
    now = UtcClock().now()

    assert now.tzinfo is UTC
