"""Opportunity-cost example persistence model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User

MAX_DOLLAR_VALUE_CENTS = 999_999_999_999


class OpportunityCostExample(Base):
    """A user-owned comparison for making saved money relatable."""

    __tablename__ = "opportunity_cost_examples"
    __table_args__ = (
        CheckConstraint("length(btrim(label)) > 0", name="label_not_blank"),
        CheckConstraint("length(btrim(unit_name)) > 0", name="unit_name_not_blank"),
        CheckConstraint(
            f"dollar_value_cents BETWEEN 1 AND {MAX_DOLLAR_VALUE_CENTS}",
            name="dollar_value",
        ),
        CheckConstraint("updated_at >= created_at", name="updated_after_created"),
        Index(
            "ix_opportunity_cost_examples_user_created",
            "user_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_opportunity_cost_examples_user_id_users",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    unit_name: Mapped[str] = mapped_column(String(80), nullable=False)
    dollar_value_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User] = relationship(
        back_populates="opportunity_cost_examples",
        lazy="raise",
    )
