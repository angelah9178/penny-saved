"""Impulse-purchase entry persistence model."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import conv

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User

MAX_PRICE_CENTS = 999_999_999_999
MAX_COMMENT_LENGTH = 4_000


class EntryStatus(StrEnum):
    """Lifecycle states persisted for an impulse-purchase entry."""

    WAITING = "waiting"
    SAVED = "saved"
    PURCHASED = "purchased"


class ImpulsePurchaseEntry(Base):
    """A user-owned impulse purchase and its stored lifecycle state."""

    __tablename__ = "impulse_purchase_entries"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_entries_user_id_users",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason_wanted: Mapped[str] = mapped_column(String(2000), nullable=False)
    status: Mapped[EntryStatus] = mapped_column(
        Enum(
            EntryStatus,
            name="entry_status",
            native_enum=False,
            create_constraint=False,
            values_callable=lambda enum: [status.value for status in enum],
            length=16,
        ),
        nullable=False,
    )
    comment: Mapped[str | None] = mapped_column(String(MAX_COMMENT_LENGTH), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    checked_in_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User] = relationship(back_populates="entries", lazy="raise")

    __table_args__ = (
        CheckConstraint(
            "status IN ('waiting', 'saved', 'purchased')",
            name=conv("ck_entries_status"),
        ),
        CheckConstraint(
            "length(btrim(item_name)) > 0",
            name=conv("ck_entries_item_name_not_blank"),
        ),
        CheckConstraint(
            "length(btrim(reason_wanted)) > 0",
            name=conv("ck_entries_reason_not_blank"),
        ),
        CheckConstraint(
            "comment IS NULL OR length(btrim(comment)) > 0",
            name=conv("ck_entries_comment_not_blank"),
        ),
        CheckConstraint(
            f"price_cents BETWEEN 1 AND {MAX_PRICE_CENTS}",
            name=conv("ck_entries_price"),
        ),
        CheckConstraint(
            "(status = 'waiting' AND checked_in_at IS NULL) "
            "OR (status IN ('saved', 'purchased') AND checked_in_at IS NOT NULL)",
            name=conv("ck_entries_lifecycle"),
        ),
        CheckConstraint(
            "checked_in_at IS NULL OR checked_in_at >= created_at",
            name=conv("ck_entries_checked_after_created"),
        ),
        CheckConstraint(
            "updated_at >= created_at",
            name=conv("ck_entries_updated_after_created"),
        ),
        Index(
            "ix_entries_user_status_created",
            user_id,
            status,
            created_at.desc(),
        ),
        Index(
            "ix_entries_user_status_checked",
            user_id,
            status,
            checked_in_at.desc(),
        ),
    )
