"""UTC clock abstractions for deterministic time-based behavior."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


def normalize_utc(value: datetime) -> datetime:
    """Normalize an aware datetime to UTC and reject ambiguous naive values."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Clock values must be timezone-aware")
    return value.astimezone(UTC)


class Clock(Protocol):
    """Source of authoritative, timezone-aware UTC timestamps."""

    def now(self) -> datetime:
        """Return the current time normalized to UTC."""
        ...


@dataclass(frozen=True, slots=True)
class SystemClock:
    """Production clock backed by the system's current UTC time."""

    def now(self) -> datetime:
        """Return the current system time as an aware UTC datetime."""
        return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class FixedClock:
    """Controllable clock for deterministic tests and time-bound operations."""

    current_time: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "current_time", normalize_utc(self.current_time))

    def now(self) -> datetime:
        """Return the configured fixed time."""
        return self.current_time


def get_clock() -> Clock:
    """Provide the production clock as an overrideable FastAPI dependency."""
    return SystemClock()
