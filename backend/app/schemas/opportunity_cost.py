"""Opportunity-cost example request and response contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from app.models.opportunity_cost_example import (
    MAX_DOLLAR_VALUE_CENTS,
    OpportunityCostExample,
)
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

MAX_LABEL_LENGTH = 120
MAX_UNIT_NAME_LENGTH = 80

DollarValueCents = Annotated[
    StrictInt,
    Field(ge=1, le=MAX_DOLLAR_VALUE_CENTS),
]


class _OpportunityCostWriteFields(BaseModel):
    """User-controlled fields shared by create and update requests."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=MAX_LABEL_LENGTH)
    unit_name: str = Field(min_length=1, max_length=MAX_UNIT_NAME_LENGTH)
    dollar_value_cents: DollarValueCents

    @field_validator("label", "unit_name", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        """Trim required text before applying nonblank and length rules."""
        if isinstance(value, str):
            return value.strip()
        return value


class OpportunityCostCreateRequest(_OpportunityCostWriteFields):
    """User-controlled fields accepted when creating an example."""


class OpportunityCostUpdateRequest(_OpportunityCostWriteFields):
    """User-controlled fields accepted when updating an example."""


class OpportunityCostExampleResponse(BaseModel):
    """Public representation of one opportunity-cost example."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    label: str
    unit_name: str
    dollar_value_cents: int
    created_at: datetime
    updated_at: datetime


class OpportunityCostExampleEnvelope(BaseModel):
    """Envelope returned by endpoints that produce one example."""

    model_config = ConfigDict(extra="forbid")

    example: OpportunityCostExampleResponse


class OpportunityCostExamplesResponse(BaseModel):
    """Ordered opportunity-cost example list returned to clients."""

    model_config = ConfigDict(extra="forbid")

    examples: list[OpportunityCostExampleResponse] = Field(default_factory=list)


def _as_utc(value: datetime, *, name: str) -> datetime:
    """Require an aware timestamp and serialize it consistently in UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be an aware datetime")
    return value.astimezone(UTC)


def to_opportunity_cost_response(
    example: OpportunityCostExample,
) -> OpportunityCostExampleResponse:
    """Map persistence data to the deliberate public API contract."""
    return OpportunityCostExampleResponse(
        id=example.id,
        label=example.label,
        unit_name=example.unit_name,
        dollar_value_cents=example.dollar_value_cents,
        created_at=_as_utc(example.created_at, name="example.created_at"),
        updated_at=_as_utc(example.updated_at, name="example.updated_at"),
    )
