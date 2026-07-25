"""Focused user persistence operations."""

from __future__ import annotations

from app.models.user import User
from app.schemas.auth import normalize_email
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Return the user matching one consistently normalized email."""
    return await db.scalar(select(User).where(User.email == normalize_email(email)))
