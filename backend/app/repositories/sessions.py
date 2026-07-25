"""Focused login-session persistence operations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.session import Session
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload


def add_session(
    db: AsyncSession,
    *,
    user_id: UUID,
    token_digest: str,
    created_at: datetime,
    expires_at: datetime,
) -> Session:
    """Stage a new session that stores only the token digest."""
    session = Session(
        user_id=user_id,
        session_token_hash=token_digest,
        created_at=created_at,
        last_used_at=created_at,
        expires_at=expires_at,
    )
    db.add(session)
    return session


async def get_session_with_user_by_digest(
    db: AsyncSession,
    token_digest: str,
) -> Session | None:
    """Resolve a session and eagerly load the account it authenticates."""
    statement = (
        select(Session)
        .options(joinedload(Session.user))
        .where(Session.session_token_hash == token_digest)
    )
    return await db.scalar(statement)


async def delete_session_by_digest(db: AsyncSession, token_digest: str) -> bool:
    """Delete the matching session when it exists."""
    session = await db.scalar(select(Session).where(Session.session_token_hash == token_digest))
    if session is None:
        return False
    await db.delete(session)
    return True
