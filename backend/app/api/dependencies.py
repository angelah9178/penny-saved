"""Reusable authentication dependencies for protected API routes."""

from __future__ import annotations

import asyncio
from typing import Annotated

from app.api.errors import ApplicationError
from app.core.config import Settings
from app.core.rate_limits import (
    PostgresRateLimitStore,
    RateLimitStore,
    digest_rate_limit_key,
)
from app.core.security import is_valid_session_token
from app.core.time import Clock, get_clock
from app.db.session import SESSION_FACTORY_STATE_KEY, SessionFactory, get_db_session
from app.models.user import User
from app.services.sessions import resolve_session
from fastapi import Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

UNAUTHORIZED_MESSAGE = "Authentication is required."
UNTRUSTED_ORIGIN_MESSAGE = "The request origin is not allowed."
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
RATE_LIMITED_MESSAGE = "Too many authentication attempts. Try again later."


def get_rate_limit_store(request: Request) -> RateLimitStore:
    """Build the shared store from the application-owned database session factory."""
    session_factory: SessionFactory | None = getattr(
        request.app.state,
        SESSION_FACTORY_STATE_KEY,
        None,
    )
    if session_factory is None:
        raise RuntimeError("Rate-limit store is unavailable outside app lifespan")
    return PostgresRateLimitStore(session_factory)


async def enforce_auth_rate_limit(
    *,
    request: Request,
    credentials_email: str,
    action: str,
    clock: Clock,
    store: RateLimitStore,
) -> None:
    """Consume IP and normalized-account limits without revealing the blocked bucket."""
    if action not in {"login", "signup"}:
        raise ValueError("Authentication rate-limit action is invalid")
    settings: Settings = request.app.state.settings
    secret = settings.rate_limit_key_secret.get_secret_value().encode()
    client_host = request.client.host if request.client is not None else "unknown"
    ip_bucket = f"{action}.ip"
    account_bucket = f"{action}.account"
    ip_limit = getattr(settings, f"auth_{action}_ip_limit")
    account_limit = getattr(settings, f"auth_{action}_account_limit")
    now = clock.now()

    ip_decision, account_decision = await asyncio.gather(
        store.consume(
            bucket=ip_bucket,
            key_digest=digest_rate_limit_key(
                secret=secret,
                domain=ip_bucket,
                value=client_host,
            ),
            limit=ip_limit,
            window_seconds=settings.auth_rate_limit_window_seconds,
            now=now,
        ),
        store.consume(
            bucket=account_bucket,
            key_digest=digest_rate_limit_key(
                secret=secret,
                domain=account_bucket,
                value=credentials_email,
            ),
            limit=account_limit,
            window_seconds=settings.auth_rate_limit_window_seconds,
            now=now,
        ),
    )
    blocked = [decision for decision in (ip_decision, account_decision) if not decision.allowed]
    if blocked:
        retry_after = max(decision.retry_after_seconds for decision in blocked)
        raise ApplicationError(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="rate_limited",
            message=RATE_LIMITED_MESSAGE,
            headers={"Retry-After": str(retry_after)},
        )


def get_presented_session_token(request: Request) -> str | None:
    """Return a syntactically valid configured session cookie when present."""
    settings: Settings = request.app.state.settings
    raw_token = request.cookies.get(settings.session_cookie_name)
    return raw_token if is_valid_session_token(raw_token) else None


def enforce_trusted_origin(request: Request) -> None:
    """Reject browser mutations whose Origin is not the configured exact origin."""
    if request.method in SAFE_METHODS:
        return

    origin = request.headers.get("origin")
    if origin is None:
        return

    settings: Settings = request.app.state.settings
    if settings.frontend_origin is None or origin != settings.frontend_origin:
        raise ApplicationError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="forbidden",
            message=UNTRUSTED_ORIGIN_MESSAGE,
        )


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
