"""Statistics range and API response contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt

NonNegativeInt = Annotated[StrictInt, Field(ge=0)]


class StatisticsRange(StrEnum):
    """Time ranges supported by the statistics summary API."""

    THIS_MONTH = "this_month"
    LAST_3_MONTHS = "last_3_months"
    LAST_6_MONTHS = "last_6_months"
    LAST_YEAR = "last_year"
    ALL_TIME = "all_time"


class StatisticsSummaryResponse(BaseModel):
    """Aggregate statistics for one user and selected time range."""

    model_config = ConfigDict(extra="forbid")

    range: StatisticsRange
    total_saved_cents: NonNegativeInt
    avoided_purchase_count: NonNegativeInt
    purchased_count: NonNegativeInt
    opportunity_costs: list[object] = Field(default_factory=list, max_length=0)
