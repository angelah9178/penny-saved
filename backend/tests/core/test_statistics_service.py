"""Unit tests for the statistics summary service orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from app.repositories.statistics import StatisticsAggregate
from app.schemas.statistics import StatisticsRange
from app.services import statistics as statistics_service

USER_ID = UUID("10000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 8, 5, 14, 30, tzinfo=UTC)


class CountingClock:
    """Deterministic clock that records service reads."""

    def __init__(self, value: datetime) -> None:
        self.value = value
        self.reads = 0

    def now(self) -> datetime:
        self.reads += 1
        return self.value


@pytest.mark.asyncio
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
async def test_summary_connects_each_range_to_the_repository_with_one_clock_read(
    monkeypatch: pytest.MonkeyPatch,
    selected_range: StatisticsRange,
    expected_start: datetime | None,
) -> None:
    repository = AsyncMock(return_value=StatisticsAggregate(25_000, 4, 1))
    monkeypatch.setattr(statistics_service, "aggregate_statistics", repository)
    clock = CountingClock(NOW)
    db = object()

    response = await statistics_service.get_statistics_summary(  # type: ignore[arg-type]
        db,
        user_id=USER_ID,
        selected_range=selected_range,
        clock=clock,
    )

    assert clock.reads == 1
    repository.assert_awaited_once_with(
        db,
        user_id=USER_ID,
        range_start=expected_start,
        range_end=NOW,
    )
    assert response.model_dump(mode="json") == {
        "range": selected_range.value,
        "total_saved_cents": 25_000,
        "avoided_purchase_count": 4,
        "purchased_count": 1,
        "opportunity_costs": [],
    }


@pytest.mark.asyncio
async def test_summary_preserves_zero_and_large_integer_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = AsyncMock(return_value=StatisticsAggregate(2**63, 0, 2**32))
    monkeypatch.setattr(statistics_service, "aggregate_statistics", repository)

    response = await statistics_service.get_statistics_summary(  # type: ignore[arg-type]
        object(),
        user_id=USER_ID,
        selected_range=StatisticsRange.ALL_TIME,
        clock=CountingClock(NOW),
    )

    assert response.total_saved_cents == 2**63
    assert response.avoided_purchase_count == 0
    assert response.purchased_count == 2**32
    assert response.opportunity_costs == []


@pytest.mark.asyncio
async def test_summary_propagates_repository_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = AsyncMock(side_effect=RuntimeError("database unavailable"))
    monkeypatch.setattr(statistics_service, "aggregate_statistics", repository)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await statistics_service.get_statistics_summary(  # type: ignore[arg-type]
            object(),
            user_id=USER_ID,
            selected_range=StatisticsRange.THIS_MONTH,
            clock=CountingClock(NOW),
        )
