"""Tests for opportunity-cost example API contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from app.models.opportunity_cost_example import (
    MAX_DOLLAR_VALUE_CENTS,
    OpportunityCostExample,
)
from app.schemas.opportunity_cost import (
    MAX_LABEL_LENGTH,
    MAX_UNIT_NAME_LENGTH,
    OpportunityCostCreateRequest,
    OpportunityCostExampleEnvelope,
    OpportunityCostExamplesResponse,
    OpportunityCostUpdateRequest,
    to_opportunity_cost_response,
)
from pydantic import ValidationError

EXAMPLE_ID = UUID("22222222-2222-4222-8222-222222222222")
USER_ID = UUID("11111111-1111-4111-8111-111111111111")
CREATED_AT = datetime(2026, 7, 15, 12, tzinfo=UTC)


def make_example() -> OpportunityCostExample:
    return OpportunityCostExample(
        id=EXAMPLE_ID,
        user_id=USER_ID,
        label="hours worked",
        unit_name="hours",
        dollar_value_cents=1_000,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


@pytest.mark.parametrize(
    "request_type", [OpportunityCostCreateRequest, OpportunityCostUpdateRequest]
)
def test_write_requests_normalize_required_text(
    request_type: type[OpportunityCostCreateRequest] | type[OpportunityCostUpdateRequest],
) -> None:
    request = request_type(
        label="  hours worked\n",
        unit_name="\thours  ",
        dollar_value_cents=1_000,
    )

    assert request.label == "hours worked"
    assert request.unit_name == "hours"


@pytest.mark.parametrize("field", ["label", "unit_name"])
def test_create_rejects_blank_required_text(field: str) -> None:
    payload = {
        "label": "hours worked",
        "unit_name": "hours",
        "dollar_value_cents": 1_000,
        field: " \t\n ",
    }

    with pytest.raises(ValidationError):
        OpportunityCostCreateRequest.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "limit"),
    [("label", MAX_LABEL_LENGTH), ("unit_name", MAX_UNIT_NAME_LENGTH)],
)
def test_text_accepts_exact_limit_and_rejects_over_limit(field: str, limit: int) -> None:
    payload = {
        "label": "hours worked",
        "unit_name": "hours",
        "dollar_value_cents": 1_000,
        field: "x" * limit,
    }

    request = OpportunityCostCreateRequest.model_validate(payload)
    assert getattr(request, field) == "x" * limit

    payload[field] = "x" * (limit + 1)
    with pytest.raises(ValidationError):
        OpportunityCostCreateRequest.model_validate(payload)


@pytest.mark.parametrize("value", [1, MAX_DOLLAR_VALUE_CENTS])
def test_create_accepts_cent_boundaries(value: int) -> None:
    request = OpportunityCostCreateRequest(
        label="hours worked",
        unit_name="hours",
        dollar_value_cents=value,
    )

    assert request.dollar_value_cents == value


@pytest.mark.parametrize("value", [0, -1, MAX_DOLLAR_VALUE_CENTS + 1, 19.99, "1000", True, False])
def test_create_rejects_invalid_cent_values(value: object) -> None:
    with pytest.raises(ValidationError):
        OpportunityCostCreateRequest(
            label="hours worked",
            unit_name="hours",
            dollar_value_cents=value,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("unknown_field", ["id", "user_id", "created_at", "updated_at", "other"])
def test_write_requests_reject_unknown_and_server_owned_fields(
    unknown_field: str,
) -> None:
    payload = {
        "label": "hours worked",
        "unit_name": "hours",
        "dollar_value_cents": 1_000,
        unknown_field: "not-client-controlled",
    }

    with pytest.raises(ValidationError):
        OpportunityCostCreateRequest.model_validate(payload)
    with pytest.raises(ValidationError):
        OpportunityCostUpdateRequest.model_validate(payload)


def test_response_mapping_returns_public_utc_shape_without_mutating_model() -> None:
    example = make_example()
    original_values = dict(example.__dict__)

    response = to_opportunity_cost_response(example)

    assert response.model_dump(mode="json") == {
        "id": str(EXAMPLE_ID),
        "label": "hours worked",
        "unit_name": "hours",
        "dollar_value_cents": 1_000,
        "created_at": "2026-07-15T12:00:00Z",
        "updated_at": "2026-07-15T12:00:00Z",
    }
    assert "user_id" not in response.model_dump()
    assert example.__dict__ == original_values


def test_response_mapping_requires_aware_timestamps() -> None:
    example = make_example()
    example.updated_at = datetime(2026, 7, 15, 12)

    with pytest.raises(ValueError, match="example.updated_at must be an aware datetime"):
        to_opportunity_cost_response(example)


def test_single_and_list_envelopes_share_the_public_shape() -> None:
    response = to_opportunity_cost_response(make_example())

    envelope = OpportunityCostExampleEnvelope(example=response)
    listing = OpportunityCostExamplesResponse(examples=[response])

    assert envelope.example == response
    assert listing.examples == [response]
    assert OpportunityCostExamplesResponse().examples == []
