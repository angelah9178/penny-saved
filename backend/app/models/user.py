"""User persistence model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.entry import ImpulsePurchaseEntry
    from app.models.opportunity_cost_example import OpportunityCostExample
    from app.models.session import Session


class User(Base):
    """Account identity that owns all user-specific records."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(email)) > 0",
            name="email_not_blank",
        ),
        Index("uq_users_email", "email", unique=True),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    sessions: Mapped[list[Session]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True,
    )
    entries: Mapped[list[ImpulsePurchaseEntry]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True,
    )
    opportunity_cost_examples: Mapped[list[OpportunityCostExample]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True,
    )
