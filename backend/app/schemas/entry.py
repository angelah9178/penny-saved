"""Impulse-purchase entry request and response contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from app.models.entry import (
    MAX_COMMENT_LENGTH,
    MAX_PRICE_CENTS,
    EntryStatus,
    ImpulsePurchaseEntry,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
)

MAX_ITEM_NAME_LENGTH = 200
MAX_REASON_WANTED_LENGTH = 2_000
ENTRY_WAIT_PERIOD = timedelta(hours=48)

PriceCents = Annotated[StrictInt, Field(ge=1, le=MAX_PRICE_CENTS)]


def normalize_required_text(value: str) -> str:
    """Strip outer whitespace from required entry text."""
    return value.strip()


def normalize_optional_comment(value: object) -> object:
    """Trim comment text and represent blank input consistently as null."""
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return value


class DashboardBucket(StrEnum):
    """Display groups derived from stored entry state and request time."""

    NEEDS_CHECK_IN = "needs_check_in"
    WAITING = "waiting"
    SAVED = "saved"
    PURCHASED = "purchased"


class EntryCheckInResult(StrEnum):
    """User-selectable outcomes accepted by the check-in API."""

    SAVED = "saved"
    PURCHASED = "purchased"


class _EntryWriteFields(BaseModel):
    """Core entry fields shared by create and waiting-entry update requests."""

    model_config = ConfigDict(extra="forbid")

    item_name: str = Field(min_length=1, max_length=MAX_ITEM_NAME_LENGTH)
    price_cents: PriceCents
    reason_wanted: str = Field(min_length=1, max_length=MAX_REASON_WANTED_LENGTH)

    @field_validator("item_name", "reason_wanted", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        """Normalize string input before applying its nonblank and length rules."""
        if isinstance(value, str):
            return normalize_required_text(value)
        return value


class EntryCreateRequest(_EntryWriteFields):
    """User-controlled fields accepted when creating a waiting entry."""


class EntryUpdateRequest(_EntryWriteFields):
    """User-controlled fields accepted when replacing waiting-entry details."""


class EntryCheckInRequest(BaseModel):
    """The outcome and optional reflection accepted during entry check-in."""

    model_config = ConfigDict(extra="forbid")

    result: EntryCheckInResult
    comment: str | None = Field(default=None, max_length=MAX_COMMENT_LENGTH)

    @field_validator("comment", mode="before")
    @classmethod
    def normalize_comment(cls, value: object) -> object:
        """Trim comments and represent blank text consistently as null."""
        return normalize_optional_comment(value)


class EntryCommentUpdateRequest(BaseModel):
    """The only user-controlled field accepted when revising a resolved comment."""

    model_config = ConfigDict(extra="forbid")

    comment: str | None = Field(max_length=MAX_COMMENT_LENGTH)

    @field_validator("comment", mode="before")
    @classmethod
    def normalize_comment(cls, value: object) -> object:
        """Reuse check-in comment normalization for later reflection edits."""
        return normalize_optional_comment(value)


class EntryResponse(BaseModel):
    """Complete public representation of an impulse-purchase entry."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    item_name: str
    price_cents: int
    reason_wanted: str
    status: EntryStatus
    dashboard_bucket: DashboardBucket
    comment: str | None
    created_at: datetime
    eligible_for_check_in_at: datetime
    checked_in_at: datetime | None
    updated_at: datetime


class EntryEnvelope(BaseModel):
    """Envelope returned by entry endpoints that produce one entry."""

    model_config = ConfigDict(extra="forbid")

    entry: EntryResponse


class DashboardEntriesResponse(BaseModel):
    """Four entry arrays consumed by the dashboard."""

    model_config = ConfigDict(extra="forbid")

    needs_check_in: list[EntryResponse] = Field(default_factory=list)
    waiting: list[EntryResponse] = Field(default_factory=list)
    saved: list[EntryResponse] = Field(default_factory=list)
    purchased: list[EntryResponse] = Field(default_factory=list)


def _require_utc(value: datetime, *, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be an aware UTC datetime")


def dashboard_bucket_for(entry: ImpulsePurchaseEntry, now: datetime) -> DashboardBucket:
    """Derive an entry's dashboard bucket using one explicit request clock."""
    _require_utc(now, name="now")
    _require_utc(entry.created_at, name="entry.created_at")

    if entry.status is EntryStatus.SAVED:
        return DashboardBucket.SAVED
    if entry.status is EntryStatus.PURCHASED:
        return DashboardBucket.PURCHASED
    if entry.created_at + ENTRY_WAIT_PERIOD <= now:
        return DashboardBucket.NEEDS_CHECK_IN
    return DashboardBucket.WAITING


def to_entry_response(entry: ImpulsePurchaseEntry, now: datetime) -> EntryResponse:
    """Map a persistence model to its deliberate, frontend-ready API contract."""
    _require_utc(now, name="now")
    _require_utc(entry.created_at, name="entry.created_at")

    eligible_at = entry.created_at + ENTRY_WAIT_PERIOD
    return EntryResponse(
        id=entry.id,
        item_name=entry.item_name,
        price_cents=entry.price_cents,
        reason_wanted=entry.reason_wanted,
        status=entry.status,
        dashboard_bucket=dashboard_bucket_for(entry, now),
        comment=entry.comment,
        created_at=entry.created_at.astimezone(UTC),
        eligible_for_check_in_at=eligible_at.astimezone(UTC),
        checked_in_at=(
            entry.checked_in_at.astimezone(UTC) if entry.checked_in_at is not None else None
        ),
        updated_at=entry.updated_at.astimezone(UTC),
    )
