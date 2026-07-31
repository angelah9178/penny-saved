"""Tests for impulse-purchase entry API contracts and lifecycle mapping."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest
from app.models.entry import (
    MAX_COMMENT_LENGTH,
    MAX_PRICE_CENTS,
    EntryStatus,
    ImpulsePurchaseEntry,
)
from app.schemas.entry import (
    DashboardBucket,
    DashboardEntriesResponse,
    EntryCheckInRequest,
    EntryCheckInResult,
    EntryCreateRequest,
    EntryEnvelope,
    EntryUpdateRequest,
    dashboard_bucket_for,
    normalize_required_text,
    to_entry_response,
)
from pydantic import ValidationError

ENTRY_ID = UUID("22222222-2222-4222-8222-222222222222")
USER_ID = UUID("11111111-1111-4111-8111-111111111111")
CREATED_AT = datetime(2026, 7, 15, 12, tzinfo=UTC)
ELIGIBLE_AT = CREATED_AT + timedelta(hours=48)


def make_entry(
    *,
    status: EntryStatus = EntryStatus.WAITING,
    created_at: datetime = CREATED_AT,
) -> ImpulsePurchaseEntry:
    checked_in_at = None if status is EntryStatus.WAITING else ELIGIBLE_AT
    return ImpulsePurchaseEntry(
        id=ENTRY_ID,
        user_id=USER_ID,
        item_name="New headphones",
        price_cents=8_500,
        reason_wanted="I want better noise cancellation",
        status=status,
        comment=None,
        created_at=created_at,
        checked_in_at=checked_in_at,
        updated_at=checked_in_at or created_at,
    )


@pytest.mark.parametrize("request_type", [EntryCreateRequest, EntryUpdateRequest])
def test_entry_write_request_normalizes_required_text(
    request_type: type[EntryCreateRequest] | type[EntryUpdateRequest],
) -> None:
    request = request_type(
        item_name="  New headphones\n",
        price_cents=8_500,
        reason_wanted="\tBetter noise cancellation  ",
    )

    assert request.item_name == "New headphones"
    assert request.reason_wanted == "Better noise cancellation"


@pytest.mark.parametrize("field", ["item_name", "reason_wanted"])
def test_entry_create_rejects_blank_required_text(field: str) -> None:
    payload = {
        "item_name": "New headphones",
        "price_cents": 8_500,
        "reason_wanted": "Better noise cancellation",
        field: " \t\n ",
    }

    with pytest.raises(ValidationError):
        EntryCreateRequest.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "length"),
    [("item_name", 201), ("reason_wanted", 2_001)],
)
def test_entry_create_rejects_text_above_database_bounds(field: str, length: int) -> None:
    payload = {
        "item_name": "New headphones",
        "price_cents": 8_500,
        "reason_wanted": "Better noise cancellation",
        field: "x" * length,
    }

    with pytest.raises(ValidationError):
        EntryCreateRequest.model_validate(payload)


@pytest.mark.parametrize("price_cents", [1, MAX_PRICE_CENTS])
def test_entry_create_accepts_integer_cent_boundaries(price_cents: int) -> None:
    request = EntryCreateRequest(
        item_name="Headphones",
        price_cents=price_cents,
        reason_wanted="Better noise cancellation",
    )

    assert request.price_cents == price_cents


@pytest.mark.parametrize(
    "price_cents",
    [0, -1, MAX_PRICE_CENTS + 1, 19.99, "1999", True, False],
)
def test_entry_create_rejects_invalid_cent_values(price_cents: object) -> None:
    with pytest.raises(ValidationError):
        EntryCreateRequest(
            item_name="Headphones",
            price_cents=price_cents,  # type: ignore[arg-type]
            reason_wanted="Better noise cancellation",
        )


@pytest.mark.parametrize(
    "unknown_field",
    ["status", "user_id", "comment", "created_at", "checked_in_at", "updated_at"],
)
def test_entry_write_requests_reject_server_owned_fields(unknown_field: str) -> None:
    payload = {
        "item_name": "Headphones",
        "price_cents": 8_500,
        "reason_wanted": "Better noise cancellation",
        unknown_field: "not-controlled-by-the-client",
    }

    with pytest.raises(ValidationError):
        EntryCreateRequest.model_validate(payload)
    with pytest.raises(ValidationError):
        EntryUpdateRequest.model_validate(payload)


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ("saved", EntryCheckInResult.SAVED),
        ("purchased", EntryCheckInResult.PURCHASED),
    ],
)
def test_entry_check_in_accepts_only_documented_results(
    result: str,
    expected: EntryCheckInResult,
) -> None:
    request = EntryCheckInRequest(result=result)

    assert request.result is expected
    assert request.comment is None


@pytest.mark.parametrize("comment", [None, "", "   ", "\t\n"])
def test_entry_check_in_normalizes_empty_comment_to_none(comment: str | None) -> None:
    request = EntryCheckInRequest(result="saved", comment=comment)

    assert request.comment is None


def test_entry_check_in_trims_optional_comment() -> None:
    request = EntryCheckInRequest(
        result="purchased",
        comment="  I still needed it for work.\n",
    )

    assert request.comment == "I still needed it for work."


def test_entry_check_in_accepts_comment_at_database_limit_after_trimming() -> None:
    comment = "x" * MAX_COMMENT_LENGTH

    request = EntryCheckInRequest(result="saved", comment=f" {comment} ")

    assert request.comment == comment


@pytest.mark.parametrize(
    "payload",
    [
        {"result": "waiting"},
        {"result": "other"},
        {"result": 1},
        {"result": "saved", "comment": 123},
        {"result": "saved", "comment": "x" * (MAX_COMMENT_LENGTH + 1)},
        {"result": "saved", "status": "purchased"},
        {"comment": "No answer"},
    ],
)
def test_entry_check_in_rejects_invalid_contract_values(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        EntryCheckInRequest.model_validate(payload)


def test_waiting_entry_remains_waiting_one_microsecond_before_eligibility() -> None:
    entry = make_entry()

    assert dashboard_bucket_for(entry, ELIGIBLE_AT - timedelta(microseconds=1)) is (
        DashboardBucket.WAITING
    )


def test_waiting_entry_needs_check_in_at_exact_eligibility_time() -> None:
    entry = make_entry()

    assert dashboard_bucket_for(entry, ELIGIBLE_AT) is DashboardBucket.NEEDS_CHECK_IN


@pytest.mark.parametrize(
    ("status", "expected_bucket"),
    [
        (EntryStatus.SAVED, DashboardBucket.SAVED),
        (EntryStatus.PURCHASED, DashboardBucket.PURCHASED),
    ],
)
def test_resolved_entry_bucket_comes_from_stored_status(
    status: EntryStatus,
    expected_bucket: DashboardBucket,
) -> None:
    entry = make_entry(status=status)

    assert dashboard_bucket_for(entry, CREATED_AT) is expected_bucket


def test_to_entry_response_returns_complete_public_shape_without_mutating_model() -> None:
    entry = make_entry()
    original_values = dict(entry.__dict__)

    response = to_entry_response(entry, ELIGIBLE_AT)

    assert response.model_dump(mode="json") == {
        "id": str(ENTRY_ID),
        "item_name": "New headphones",
        "price_cents": 8_500,
        "reason_wanted": "I want better noise cancellation",
        "status": "waiting",
        "dashboard_bucket": "needs_check_in",
        "comment": None,
        "created_at": "2026-07-15T12:00:00Z",
        "eligible_for_check_in_at": "2026-07-17T12:00:00Z",
        "checked_in_at": None,
        "updated_at": "2026-07-15T12:00:00Z",
    }
    assert "user_id" not in response.model_dump()
    assert entry.__dict__ == original_values


def test_entry_envelope_and_dashboard_response_keep_consistent_entry_shape() -> None:
    response = to_entry_response(make_entry(), CREATED_AT)

    envelope = EntryEnvelope(entry=response)
    dashboard = DashboardEntriesResponse(waiting=[response])

    assert envelope.entry == response
    assert dashboard.model_dump()["waiting"] == [response.model_dump()]
    assert dashboard.needs_check_in == []
    assert dashboard.saved == []
    assert dashboard.purchased == []


@pytest.mark.parametrize(
    "now",
    [
        datetime(2026, 7, 17, 12),
        datetime(2026, 7, 17, 8, tzinfo=timezone(timedelta(hours=-4))),
    ],
)
def test_lifecycle_mapping_requires_an_aware_utc_request_clock(now: datetime) -> None:
    with pytest.raises(ValueError, match="now must be an aware UTC datetime"):
        to_entry_response(make_entry(), now)


def test_normalize_required_text_is_shared_and_predictable() -> None:
    assert normalize_required_text("\t New headphones \n") == "New headphones"
