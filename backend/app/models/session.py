"""Login session persistence model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CHAR, CheckConstraint, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Session(Base):
    """A revocable login session that stores only a token digest."""

    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(
            "session_token_hash ~ '^[0-9a-f]{64}$'",
            name="token_hash_format",
        ),
        CheckConstraint("expires_at > created_at", name="expiry"),
        CheckConstraint("last_used_at >= created_at", name="last_used"),
        Index("uq_sessions_token_hash", "session_token_hash", unique=True),
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_expires_at", "expires_at"),
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
            name="fk_sessions_user_id_users",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    session_token_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User] = relationship(back_populates="sessions", lazy="raise")
