"""Shared fixed-window rate-limit persistence model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CHAR, CheckConstraint, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RateLimitCounter(Base):
    """One shared counter identified only by a bucket and irreversible key digest."""

    __tablename__ = "rate_limit_counters"
    __table_args__ = (
        CheckConstraint("length(btrim(bucket)) > 0", name="bucket_not_blank"),
        CheckConstraint("key_digest ~ '^[0-9a-f]{64}$'", name="key_digest_format"),
        CheckConstraint("attempt_count > 0", name="attempt_count_positive"),
        CheckConstraint("expires_at > window_started_at", name="window_expiry"),
        Index("ix_rate_limit_counters_expires_at", "expires_at"),
    )

    bucket: Mapped[str] = mapped_column(String(64), primary_key=True)
    key_digest: Mapped[str] = mapped_column(CHAR(64), primary_key=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
