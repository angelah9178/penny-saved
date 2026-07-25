"""Reusable authentication dependencies for protected API routes."""

from __future__ import annotations

from typing import Annotated

from app.api.errors import ApplicationError
from app.core.config import Settings
from app.core.security import is_valid_session_token
from app.core.time import Clock, get_clock
from app.db.session import get_db_session
from app.models.user import User
from app.services.sessions import resolve_session
from fastapi import Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

UNAUTHORIZED_MESSAGE = "Authentication is required."


def get_presented_session_token(request: Request) -> str | None:
    """Return a syntactically valid configured session cookie when present."""
    settings: Settings = request.app.state.settings
    raw_token = request.cookies.get(settings.session_cookie_name)
    return raw_token if is_valid_session_token(raw_token) else None


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> User:
    """Resolve the authenticated user or raise the standard safe 401 error."""
    raw_token = get_presented_session_token(request)
    if raw_token is None:
        raise unauthorized_error()

    resolved = await resolve_session(db, raw_token=raw_token, clock=clock)
    if resolved is None:
        raise unauthorized_error()
    return resolved.user


def unauthorized_error() -> ApplicationError:
    """Build the shared response-safe authentication failure."""
    return ApplicationError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="unauthorized",
        message=UNAUTHORIZED_MESSAGE,
    )
