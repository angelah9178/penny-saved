"""Injectable UTC clock."""

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Clock interface used by time-sensitive services."""

    def now(self) -> datetime:
        """Return a timezone-aware UTC instant."""
        ...


class UtcClock:
    """Production clock backed by the system UTC time."""

    def now(self) -> datetime:
        return datetime.now(UTC)


def get_clock() -> Clock:
    """FastAPI dependency for the authoritative application clock."""
    return UtcClock()
