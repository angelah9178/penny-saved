"""Statistics time-range calculations and summary use cases."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime

from app.core.time import normalize_utc
from app.schemas.statistics import StatisticsRange


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


def _subtract_calendar_months(value: datetime, months: int) -> datetime:
    """Subtract whole calendar months, clamping the day in the target month."""
    zero_based_month = value.year * 12 + value.month - 1 - months
    target_year, target_month_index = divmod(zero_based_month, 12)
    target_month = target_month_index + 1
    target_day = min(value.day, monthrange(target_year, target_month)[1])
    return value.replace(year=target_year, month=target_month, day=target_day)
