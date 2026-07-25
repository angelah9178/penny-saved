"""Login-session creation, resolution, and revocation policy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from app.core.security import digest_session_token, generate_session_token
from app.core.time import Clock, normalize_utc
from app.models.session import Session
from app.models.user import User
from app.repositories.sessions import (
    add_session,
    delete_session_by_digest,
    get_session_with_user_by_digest,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

LAST_USED_WRITE_INTERVAL = timedelta(hours=1)
MAX_TOKEN_GENERATION_ATTEMPTS = 3
TokenFactory = Callable[[int], str]


class SessionTokenCollisionError(RuntimeError):
    """Raised when secure token generation repeatedly produces stored collisions."""


@dataclass(frozen=True, slots=True, repr=False)
class IssuedSession:
    """A persisted session and its browser-only raw token."""

    session: Session
    raw_token: str

    def __repr__(self) -> str:
        return f"{type(self).__name__}(session_id={self.session.id!r}, raw_token=<redacted>)"


@dataclass(frozen=True, slots=True)
class ResolvedSession:
    """A valid persisted session and the account it authenticates."""

    session: Session
    user: User


async def create_session(
    db: AsyncSession,
    *,
    user_id: UUID,
    clock: Clock,
    ttl_seconds: int,
    token_factory: TokenFactory | None = None,
) -> IssuedSession:
    """Persist and commit one new absolute-expiry session."""
    issued = await stage_session(
        db,
        user_id=user_id,
        now=clock.now(),
        ttl_seconds=ttl_seconds,
        token_factory=token_factory,
    )
    await db.commit()
    return issued


async def stage_session(
    db: AsyncSession,
    *,
    user_id: UUID,
    now: datetime,
    ttl_seconds: int,
    token_factory: TokenFactory | None = None,
) -> IssuedSession:
    """Stage a session inside a caller-owned transaction and flush it safely."""
    created_at = normalize_utc(now)
    if ttl_seconds <= 0:
        raise ValueError("Session TTL must be positive")
    expires_at = created_at + timedelta(seconds=ttl_seconds)

    for _ in range(MAX_TOKEN_GENERATION_ATTEMPTS):
        raw_token = (
            generate_session_token()
            if token_factory is None
            else generate_session_token(token_factory)
        )
        token_digest = digest_session_token(raw_token)
        try:
            async with db.begin_nested():
                session = add_session(
                    db,
                    user_id=user_id,
                    token_digest=token_digest,
                    created_at=created_at,
                    expires_at=expires_at,
                )
                await db.flush()
        except IntegrityError as error:
            if _is_token_digest_collision(error):
                continue
            raise
        return IssuedSession(session=session, raw_token=raw_token)

    raise SessionTokenCollisionError("Unable to generate a unique session token")


async def resolve_session(
    db: AsyncSession,
    *,
    raw_token: str,
    clock: Clock,
) -> ResolvedSession | None:
    """Resolve a valid session, enforcing expiry and throttled activity writes."""
    now = normalize_utc(clock.now())
    session = await get_session_with_user_by_digest(db, digest_session_token(raw_token))
    if session is None:
        return None

    if session.expires_at <= now:
        await db.delete(session)
        await db.commit()
        return None

    if now - session.last_used_at >= LAST_USED_WRITE_INTERVAL:
        session.last_used_at = now
        await db.commit()

    return ResolvedSession(session=session, user=session.user)


async def revoke_session(db: AsyncSession, *, raw_token: str) -> bool:
    """Revoke and commit only the session represented by the raw token."""
    deleted = await delete_session_by_digest(db, digest_session_token(raw_token))
    if deleted:
        await db.commit()
    return deleted


def _is_token_digest_collision(error: IntegrityError) -> bool:
    constraint_name = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
    return constraint_name == "uq_sessions_token_hash"
