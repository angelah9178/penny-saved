"""Unit tests for the statistics summary service orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest
from app.models.opportunity_cost_example import OpportunityCostExample
from app.repositories.statistics import StatisticsAggregate
from app.schemas.statistics import StatisticsRange
from app.services import statistics as statistics_service

USER_ID = UUID("10000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 8, 5, 14, 30, tzinfo=UTC)
EXAMPLE_ID = UUID("20000000-0000-4000-8000-000000000001")


class CountingClock:
    """Deterministic clock that records service reads."""

    def __init__(self, value: datetime) -> None:
        self.value = value
        self.reads = 0

    def now(self) -> datetime:
        self.reads += 1
        return self.value


def make_example(
    *,
    example_id: UUID = EXAMPLE_ID,
    label: str = "hours worked",
    unit_name: str = "hours",
    dollar_value_cents: int = 1_000,
) -> OpportunityCostExample:
    return OpportunityCostExample(
        id=example_id,
        user_id=USER_ID,
        label=label,
        unit_name=unit_name,
        dollar_value_cents=dollar_value_cents,
        created_at=NOW,
        updated_at=NOW,
    )


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
    examples_repository = AsyncMock(return_value=[])
    monkeypatch.setattr(statistics_service, "aggregate_statistics", repository)
    monkeypatch.setattr(
        statistics_service,
        "list_opportunity_cost_examples_by_user",
        examples_repository,
    )
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
    examples_repository.assert_awaited_once_with(db, user_id=USER_ID)
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
    monkeypatch.setattr(
        statistics_service,
        "list_opportunity_cost_examples_by_user",
        AsyncMock(return_value=[]),
    )

    db = object()
    response = await statistics_service.get_statistics_summary(  # type: ignore[arg-type]
        db,
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
    examples_repository = AsyncMock()
    monkeypatch.setattr(statistics_service, "aggregate_statistics", repository)
    monkeypatch.setattr(
        statistics_service,
        "list_opportunity_cost_examples_by_user",
        examples_repository,
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        await statistics_service.get_statistics_summary(  # type: ignore[arg-type]
            object(),
            user_id=USER_ID,
            selected_range=StatisticsRange.THIS_MONTH,
            clock=CountingClock(NOW),
        )

    examples_repository.assert_not_awaited()


@pytest.mark.asyncio
async def test_summary_calculates_owned_equivalents_in_repository_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    examples = [
        make_example(),
        make_example(
            example_id=UUID("20000000-0000-4000-8000-000000000002"),
            label="coffee",
            unit_name="cups",
            dollar_value_cents=3_000,
        ),
        make_example(
            example_id=UUID("20000000-0000-4000-8000-000000000003"),
            label="hours worked",
            unit_name="hours",
            dollar_value_cents=2_000,
        ),
    ]
    monkeypatch.setattr(
        statistics_service,
        "aggregate_statistics",
        AsyncMock(return_value=StatisticsAggregate(25_000, 4, 1)),
    )
    examples_repository = AsyncMock(return_value=examples)
    monkeypatch.setattr(
        statistics_service,
        "list_opportunity_cost_examples_by_user",
        examples_repository,
    )

    db = object()
    response = await statistics_service.get_statistics_summary(  # type: ignore[arg-type]
        db,
        user_id=USER_ID,
        selected_range=StatisticsRange.THIS_MONTH,
        clock=CountingClock(NOW),
    )

    examples_repository.assert_awaited_once_with(db, user_id=USER_ID)
    assert [item.example_id for item in response.opportunity_costs] == [
        example.id for example in examples
    ]
    assert [item.equivalent_units for item in response.opportunity_costs] == [25, 8.3, 12.5]
    assert response.opportunity_costs[2].label == "hours worked"


@pytest.mark.asyncio
async def test_summary_rounds_exact_halves_up_with_decimal_arithmetic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        statistics_service,
        "aggregate_statistics",
        AsyncMock(return_value=StatisticsAggregate(105, 1, 0)),
    )
    monkeypatch.setattr(
        statistics_service,
        "list_opportunity_cost_examples_by_user",
        AsyncMock(return_value=[make_example(dollar_value_cents=100)]),
    )

    response = await statistics_service.get_statistics_summary(  # type: ignore[arg-type]
        object(),
        user_id=USER_ID,
        selected_range=StatisticsRange.ALL_TIME,
        clock=CountingClock(NOW),
    )

    assert response.opportunity_costs[0].equivalent_units == 1.1


@pytest.mark.asyncio
async def test_summary_returns_zero_equivalents_for_zero_saved_total(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        statistics_service,
        "aggregate_statistics",
        AsyncMock(return_value=StatisticsAggregate(0, 0, 2)),
    )
    monkeypatch.setattr(
        statistics_service,
        "list_opportunity_cost_examples_by_user",
        AsyncMock(return_value=[make_example()]),
    )

    response = await statistics_service.get_statistics_summary(  # type: ignore[arg-type]
        object(),
        user_id=USER_ID,
        selected_range=StatisticsRange.ALL_TIME,
        clock=CountingClock(NOW),
    )

    assert response.opportunity_costs[0].equivalent_units == 0


@pytest.mark.asyncio
async def test_summary_skips_and_logs_defensive_zero_divisor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        statistics_service,
        "aggregate_statistics",
        AsyncMock(return_value=StatisticsAggregate(10_000, 1, 0)),
    )
    monkeypatch.setattr(
        statistics_service,
        "list_opportunity_cost_examples_by_user",
        AsyncMock(return_value=[make_example(dollar_value_cents=0), make_example()]),
    )
    warning = Mock()
    monkeypatch.setattr(statistics_service.logger, "warning", warning)

    response = await statistics_service.get_statistics_summary(  # type: ignore[arg-type]
        object(),
        user_id=USER_ID,
        selected_range=StatisticsRange.ALL_TIME,
        clock=CountingClock(NOW),
    )

    assert [item.equivalent_units for item in response.opportunity_costs] == [10]
    warning.assert_called_once_with(
        "statistics.invalid_zero_opportunity_cost_skipped",
        extra={"user_id": str(USER_ID)},
    )


@pytest.mark.asyncio
async def test_summary_propagates_example_repository_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        statistics_service,
        "aggregate_statistics",
        AsyncMock(return_value=StatisticsAggregate(0, 0, 0)),
    )
    monkeypatch.setattr(
        statistics_service,
        "list_opportunity_cost_examples_by_user",
        AsyncMock(side_effect=RuntimeError("examples unavailable")),
    )

    with pytest.raises(RuntimeError, match="examples unavailable"):
        await statistics_service.get_statistics_summary(  # type: ignore[arg-type]
            object(),
            user_id=USER_ID,
            selected_range=StatisticsRange.THIS_MONTH,
            clock=CountingClock(NOW),
        )
