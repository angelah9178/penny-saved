"""Tests for statistics API response contracts."""

from uuid import UUID

import pytest
from app.models.opportunity_cost_example import MAX_DOLLAR_VALUE_CENTS
from app.schemas.statistics import (
    OpportunityCostEquivalentResponse,
    StatisticsRange,
    StatisticsSummaryResponse,
)
from pydantic import ValidationError

EXAMPLE_ID = UUID("10000000-0000-4000-8000-000000000001")


def test_statistics_range_exposes_only_supported_values() -> None:
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
        opportunity_costs=[
            OpportunityCostEquivalentResponse(
                example_id=EXAMPLE_ID,
                label="hours worked",
                unit_name="hours",
                dollar_value_cents=1_000,
                equivalent_units=25,
            )
        ],
    )

    assert response.model_dump(mode="json") == {
        "range": "this_month",
        "total_saved_cents": 25_000,
        "avoided_purchase_count": 4,
        "purchased_count": 1,
        "opportunity_costs": [
            {
                "example_id": str(EXAMPLE_ID),
                "label": "hours worked",
                "unit_name": "hours",
                "dollar_value_cents": 1_000,
                "equivalent_units": 25,
            }
        ],
    }


def test_statistics_summary_preserves_large_integers() -> None:
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


@pytest.mark.parametrize("equivalent_units", [0, 25, 8.3])
def test_opportunity_cost_equivalent_accepts_nonnegative_numeric_results(
    equivalent_units: int | float,
) -> None:
    equivalent = OpportunityCostEquivalentResponse(
        example_id=EXAMPLE_ID,
        label="hours worked",
        unit_name="hours",
        dollar_value_cents=1_000,
        equivalent_units=equivalent_units,
    )

    assert equivalent.model_dump(mode="json")["equivalent_units"] == equivalent_units


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("example_id", "not-a-uuid"),
        ("label", ""),
        ("label", " hours worked "),
        ("label", "x" * 121),
        ("unit_name", ""),
        ("unit_name", " hours "),
        ("unit_name", "x" * 81),
        ("dollar_value_cents", 0),
        ("dollar_value_cents", MAX_DOLLAR_VALUE_CENTS + 1),
        ("dollar_value_cents", 1.5),
        ("equivalent_units", -0.1),
        ("equivalent_units", 1.25),
        ("equivalent_units", "8.3"),
        ("equivalent_units", True),
        ("equivalent_units", float("inf")),
    ],
)
def test_opportunity_cost_equivalent_rejects_invalid_fields(field: str, value: object) -> None:
    payload = {
        "example_id": str(EXAMPLE_ID),
        "label": "hours worked",
        "unit_name": "hours",
        "dollar_value_cents": 1_000,
        "equivalent_units": 25,
        field: value,
    }

    with pytest.raises(ValidationError):
        OpportunityCostEquivalentResponse.model_validate(payload)


def test_opportunity_cost_equivalent_accepts_exact_field_limits() -> None:
    equivalent = OpportunityCostEquivalentResponse(
        example_id=EXAMPLE_ID,
        label="x" * 120,
        unit_name="x" * 80,
        dollar_value_cents=MAX_DOLLAR_VALUE_CENTS,
        equivalent_units=0,
    )

    assert equivalent.dollar_value_cents == MAX_DOLLAR_VALUE_CENTS


def test_opportunity_cost_equivalent_rejects_unknown_and_internal_fields() -> None:
    with pytest.raises(ValidationError):
        OpportunityCostEquivalentResponse.model_validate(
            {
                "example_id": str(EXAMPLE_ID),
                "label": "hours worked",
                "unit_name": "hours",
                "dollar_value_cents": 1_000,
                "equivalent_units": 25,
                "user_id": "20000000-0000-4000-8000-000000000001",
            }
        )


def test_statistics_summary_rejects_incomplete_opportunity_costs() -> None:
    with pytest.raises(ValidationError):
        StatisticsSummaryResponse.model_validate(
            {
                "range": StatisticsRange.THIS_MONTH,
                "total_saved_cents": 0,
                "avoided_purchase_count": 0,
                "purchased_count": 0,
                "opportunity_costs": [{"label": "hours worked"}],
            }
        )
