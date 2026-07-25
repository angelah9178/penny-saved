"""Authentication account workflows."""

from __future__ import annotations

from dataclasses import dataclass

from app.api.errors import ApplicationError
from app.core.config import Settings
from app.core.time import Clock, normalize_utc
from app.models.user import User
from app.repositories.users import add_user, get_user_by_email
from app.schemas.auth import AuthRequest
from app.services.sessions import IssuedSession, stage_session
from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

DUPLICATE_EMAIL_MESSAGE = "An account with this email already exists."


@dataclass(frozen=True, slots=True, repr=False)
class SignupResult:
    """The new public account and browser-only session token."""

    user: User
    issued_session: IssuedSession

    def __repr__(self) -> str:
        return f"{type(self).__name__}(user_id={self.user.id!r}, issued_session=<redacted>)"


async def signup(
    db: AsyncSession,
    *,
    credentials: AuthRequest,
    clock: Clock,
    settings: Settings,
) -> SignupResult:
    """Create one user and initial login session in an atomic transaction."""
    try:
        if await get_user_by_email(db, credentials.email) is not None:
            raise _duplicate_email_error()

        now = normalize_utc(clock.now())
        user = add_user(
            db,
            email=credentials.email,
            password=credentials.password.get_secret_value(),
            created_at=now,
        )
        await db.flush()
        issued_session = await stage_session(
            db,
            user_id=user.id,
            now=now,
            ttl_seconds=settings.session_ttl_seconds,
        )
        await db.commit()
        return SignupResult(user=user, issued_session=issued_session)
    except IntegrityError as error:
        await db.rollback()
        if _is_unique_email_violation(error):
            raise _duplicate_email_error() from None
        raise
    except BaseException:
        await db.rollback()
        raise


def _duplicate_email_error() -> ApplicationError:
    return ApplicationError(
        status_code=status.HTTP_409_CONFLICT,
        code="duplicate_email",
        message=DUPLICATE_EMAIL_MESSAGE,
    )


def _is_unique_email_violation(error: IntegrityError) -> bool:
    constraint_name = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
    return constraint_name == "uq_users_email"
