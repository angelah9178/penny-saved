"""Statistics time-range calculations and summary use cases."""

from __future__ import annotations

import logging
from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from app.core.time import Clock, normalize_utc
from app.models.opportunity_cost_example import OpportunityCostExample
from app.repositories.opportunity_costs import list_opportunity_cost_examples_by_user
from app.repositories.statistics import aggregate_statistics
from app.schemas.statistics import (
    OpportunityCostEquivalentResponse,
    StatisticsRange,
    StatisticsSummaryResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("penny_saved.statistics")
ONE_DECIMAL_PLACE = Decimal("0.1")


@dataclass(frozen=True, slots=True)
class StatisticsInterval:
    """A UTC half-open interval used to select resolved entries."""

    start: datetime | None
    end: datetime


def statistics_interval_for(
    selected_range: StatisticsRange,
    *,
    now: datetime,
) -> StatisticsInterval:
    """Calculate a selected statistics range from one authoritative request time."""
    end = normalize_utc(now)

    if selected_range is StatisticsRange.THIS_MONTH:
        start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif selected_range is StatisticsRange.LAST_3_MONTHS:
        start = _subtract_calendar_months(end, 3)
    elif selected_range is StatisticsRange.LAST_6_MONTHS:
        start = _subtract_calendar_months(end, 6)
    elif selected_range is StatisticsRange.LAST_YEAR:
        start = _subtract_calendar_months(end, 12)
    elif selected_range is StatisticsRange.ALL_TIME:
        start = None
    else:
        raise ValueError(f"Unsupported statistics range: {selected_range!r}")

    return StatisticsInterval(start=start, end=end)


async def get_statistics_summary(
    db: AsyncSession,
    *,
    user_id: UUID,
    selected_range: StatisticsRange,
    clock: Clock,
) -> StatisticsSummaryResponse:
    """Return one user's aggregate summary using one request-scoped clock read."""
    interval = statistics_interval_for(selected_range, now=clock.now())
    aggregate = await aggregate_statistics(
        db,
        user_id=user_id,
        range_start=interval.start,
        range_end=interval.end,
    )
    examples = await list_opportunity_cost_examples_by_user(db, user_id=user_id)
    return StatisticsSummaryResponse(
        range=selected_range,
        total_saved_cents=aggregate.total_saved_cents,
        avoided_purchase_count=aggregate.avoided_purchase_count,
        purchased_count=aggregate.purchased_count,
        opportunity_costs=_calculate_opportunity_cost_equivalents(
            examples,
            total_saved_cents=aggregate.total_saved_cents,
            user_id=user_id,
        ),
    )


def _calculate_opportunity_cost_equivalents(
    examples: list[OpportunityCostExample],
    *,
    total_saved_cents: int,
    user_id: UUID,
) -> list[OpportunityCostEquivalentResponse]:
    """Calculate ordered display equivalents without binary floating-point division."""
    equivalents: list[OpportunityCostEquivalentResponse] = []
    saved_total = Decimal(total_saved_cents)

    for example in examples:
        if example.dollar_value_cents == 0:
            logger.warning(
                "statistics.invalid_zero_opportunity_cost_skipped",
                extra={"user_id": str(user_id)},
            )
            continue

        rounded = (saved_total / Decimal(example.dollar_value_cents)).quantize(
            ONE_DECIMAL_PLACE,
            rounding=ROUND_HALF_UP,
        )
        numeric_result: int | float = (
            int(rounded) if rounded == rounded.to_integral_value() else float(rounded)
        )

        equivalents.append(
            OpportunityCostEquivalentResponse(
                example_id=example.id,
                label=example.label,
                unit_name=example.unit_name,
                dollar_value_cents=example.dollar_value_cents,
                equivalent_units=numeric_result,
            )
        )

    return equivalents


def _subtract_calendar_months(value: datetime, months: int) -> datetime:
    """Subtract whole calendar months, clamping the day in the target month."""
    zero_based_month = value.year * 12 + value.month - 1 - months
    target_year, target_month_index = divmod(zero_based_month, 12)
    target_month = target_month_index + 1
    target_day = min(value.day, monthrange(target_year, target_month)[1])
    return value.replace(year=target_year, month=target_month, day=target_day)
