"""Tests for statistics API response contracts."""

import pytest
from app.schemas.statistics import StatisticsRange, StatisticsSummaryResponse
from pydantic import ValidationError


def test_statistics_range_exposes_only_supported_query_values() -> None:
    assert [item.value for item in StatisticsRange] == [
        "this_month",
        "last_3_months",
        "last_6_months",
        "last_year",
        "all_time",
    ]


def test_statistics_summary_serializes_exact_contract() -> None:
    response = StatisticsSummaryResponse(
        range=StatisticsRange.THIS_MONTH,
        total_saved_cents=25_000,
        avoided_purchase_count=4,
        purchased_count=1,
    )

    assert response.model_dump(mode="json") == {
        "range": "this_month",
        "total_saved_cents": 25_000,
        "avoided_purchase_count": 4,
        "purchased_count": 1,
        "opportunity_costs": [],
    }


def test_statistics_summary_preserves_totals_above_32_bit_range() -> None:
    response = StatisticsSummaryResponse(
        range=StatisticsRange.ALL_TIME,
        total_saved_cents=2**63,
        avoided_purchase_count=2**32,
        purchased_count=0,
    )

    assert response.total_saved_cents == 2**63
    assert response.avoided_purchase_count == 2**32


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("total_saved_cents", -1),
        ("avoided_purchase_count", -1),
        ("purchased_count", -1),
        ("total_saved_cents", 1.5),
        ("total_saved_cents", "100"),
        ("total_saved_cents", True),
    ],
)
def test_statistics_summary_rejects_invalid_numeric_values(field: str, value: object) -> None:
    payload = {
        "range": "this_month",
        "total_saved_cents": 0,
        "avoided_purchase_count": 0,
        "purchased_count": 0,
        field: value,
    }

    with pytest.raises(ValidationError):
        StatisticsSummaryResponse.model_validate(payload)


def test_statistics_summary_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        StatisticsSummaryResponse.model_validate(
            {
                "range": "this_month",
                "total_saved_cents": 0,
                "avoided_purchase_count": 0,
                "purchased_count": 0,
                "unknown": "value",
            }
        )


def test_statistics_summary_keeps_opportunity_costs_empty_until_dev_018() -> None:
    with pytest.raises(ValidationError):
        StatisticsSummaryResponse(
            range=StatisticsRange.THIS_MONTH,
            total_saved_cents=0,
            avoided_purchase_count=0,
            purchased_count=0,
            opportunity_costs=[{"label": "hours worked"}],
        )
