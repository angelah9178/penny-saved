"""Focused user persistence operations."""

from __future__ import annotations

from datetime import datetime

from app.core.security import hash_password
from app.models.user import User
from app.schemas.auth import normalize_email
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Return the user matching one consistently normalized email."""
    return await db.scalar(select(User).where(User.email == normalize_email(email)))


def add_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    created_at: datetime,
) -> User:
    """Stage a normalized user with an Argon2id password hash."""
    user = User(
        email=normalize_email(email),
        password_hash=hash_password(password),
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(user)
    return user
