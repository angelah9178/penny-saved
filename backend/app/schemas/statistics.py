"""Statistics range and API response contracts."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from app.schemas.opportunity_cost import (
    MAX_LABEL_LENGTH,
    MAX_UNIT_NAME_LENGTH,
    DollarValueCents,
)
from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, field_validator

NonNegativeInt = Annotated[StrictInt, Field(ge=0)]
EquivalentUnits = Annotated[StrictInt | StrictFloat, Field(ge=0, allow_inf_nan=False)]


class StatisticsRange(StrEnum):
    """Time ranges supported by the statistics summary API."""

    THIS_MONTH = "this_month"
    LAST_3_MONTHS = "last_3_months"
    LAST_6_MONTHS = "last_6_months"
    LAST_YEAR = "last_year"
    ALL_TIME = "all_time"


class OpportunityCostEquivalentResponse(BaseModel):
    """Public opportunity-cost comparison calculated from a saved total."""

    model_config = ConfigDict(extra="forbid")

    example_id: UUID
    label: str = Field(min_length=1, max_length=MAX_LABEL_LENGTH)
    unit_name: str = Field(min_length=1, max_length=MAX_UNIT_NAME_LENGTH)
    dollar_value_cents: DollarValueCents
    equivalent_units: EquivalentUnits

    @field_validator("label", "unit_name")
    @classmethod
    def require_normalized_text(cls, value: str) -> str:
        """Reject persistence data that violates the established normalized contract."""
        if value != value.strip():
            raise ValueError("must not contain outer whitespace")
        return value

    @field_validator("equivalent_units")
    @classmethod
    def require_one_decimal_place(cls, value: int | float) -> int | float:
        """Allow whole or one-decimal JSON numbers only."""
        if Decimal(str(value)).as_tuple().exponent < -1:
            raise ValueError("must have at most one decimal place")
        return value


class StatisticsSummaryResponse(BaseModel):
    """Aggregate statistics for one user and selected time range."""

    model_config = ConfigDict(extra="forbid")

    range: StatisticsRange
    total_saved_cents: NonNegativeInt
    avoided_purchase_count: NonNegativeInt
    purchased_count: NonNegativeInt
    opportunity_costs: list[OpportunityCostEquivalentResponse] = Field(default_factory=list)
