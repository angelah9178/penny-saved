"""Session-cookie issue and clearing helpers."""

from __future__ import annotations

from app.core.config import Settings
from fastapi import Response

SESSION_COOKIE_PATH = "/"
SESSION_COOKIE_SAME_SITE = "lax"


def set_session_cookie(response: Response, *, raw_token: str, settings: Settings) -> None:
    """Issue the configured browser-only session cookie."""
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=settings.session_ttl_seconds,
        path=SESSION_COOKIE_PATH,
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=SESSION_COOKIE_SAME_SITE,
    )


def clear_session_cookie(response: Response, *, settings: Settings) -> None:
    """Clear the session cookie with attributes matching issuance."""
    response.delete_cookie(
        key=settings.session_cookie_name,
        path=SESSION_COOKIE_PATH,
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=SESSION_COOKIE_SAME_SITE,
    )
