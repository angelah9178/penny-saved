"""Tests for pure statistics interval calculations."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from app.schemas.statistics import StatisticsRange
from app.services.statistics import StatisticsInterval, statistics_interval_for


@pytest.mark.parametrize(
    ("selected_range", "expected_start"),
    [
        (StatisticsRange.THIS_MONTH, datetime(2026, 8, 1, tzinfo=UTC)),
        (StatisticsRange.LAST_3_MONTHS, datetime(2026, 5, 5, 14, 30, tzinfo=UTC)),
        (StatisticsRange.LAST_6_MONTHS, datetime(2026, 2, 5, 14, 30, tzinfo=UTC)),
        (StatisticsRange.LAST_YEAR, datetime(2025, 8, 5, 14, 30, tzinfo=UTC)),
        (StatisticsRange.ALL_TIME, None),
    ],
)
def test_statistics_interval_calculates_every_supported_range(
    selected_range: StatisticsRange,
    expected_start: datetime | None,
) -> None:
    now = datetime(2026, 8, 5, 14, 30, tzinfo=UTC)

    assert statistics_interval_for(selected_range, now=now) == StatisticsInterval(
        start=expected_start,
        end=now,
    )


@pytest.mark.parametrize(
    ("now", "selected_range", "expected_start"),
    [
        (
            datetime(2026, 1, 15, 9, 45, tzinfo=UTC),
            StatisticsRange.LAST_3_MONTHS,
            datetime(2025, 10, 15, 9, 45, tzinfo=UTC),
        ),
        (
            datetime(2026, 7, 31, 9, 45, tzinfo=UTC),
            StatisticsRange.LAST_3_MONTHS,
            datetime(2026, 4, 30, 9, 45, tzinfo=UTC),
        ),
        (
            datetime(2026, 5, 31, 9, 45, tzinfo=UTC),
            StatisticsRange.LAST_3_MONTHS,
            datetime(2026, 2, 28, 9, 45, tzinfo=UTC),
        ),
        (
            datetime(2024, 2, 29, 9, 45, tzinfo=UTC),
            StatisticsRange.LAST_YEAR,
            datetime(2023, 2, 28, 9, 45, tzinfo=UTC),
        ),
    ],
)
def test_statistics_interval_clamps_calendar_month_subtraction(
    now: datetime,
    selected_range: StatisticsRange,
    expected_start: datetime,
) -> None:
    interval = statistics_interval_for(selected_range, now=now)

    assert interval.start == expected_start
    assert interval.end == now


def test_this_month_at_month_start_has_equal_half_open_boundaries() -> None:
    now = datetime(2026, 8, 1, tzinfo=UTC)

    assert statistics_interval_for(StatisticsRange.THIS_MONTH, now=now) == StatisticsInterval(
        start=now,
        end=now,
    )


def test_statistics_interval_normalizes_non_utc_time_first() -> None:
    eastern_daylight_time = timezone(timedelta(hours=-4))
    local_time = datetime(2026, 8, 1, 0, 30, tzinfo=eastern_daylight_time)

    assert statistics_interval_for(
        StatisticsRange.THIS_MONTH,
        now=local_time,
    ) == StatisticsInterval(
        start=datetime(2026, 8, 1, tzinfo=UTC),
        end=datetime(2026, 8, 1, 4, 30, tzinfo=UTC),
    )


def test_statistics_interval_rejects_naive_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        statistics_interval_for(
            StatisticsRange.THIS_MONTH,
            now=datetime(2026, 8, 5, 14, 30),
        )


def test_statistics_interval_rejects_unrecognized_runtime_value() -> None:
    with pytest.raises(ValueError, match="Unsupported statistics range"):
        statistics_interval_for(
            "quarter",  # type: ignore[arg-type]
            now=datetime(2026, 8, 5, tzinfo=UTC),
        )
