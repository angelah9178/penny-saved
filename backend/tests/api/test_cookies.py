"""Tests for session-cookie issue and clearing behavior."""

from __future__ import annotations

from app.api.cookies import clear_session_cookie, set_session_cookie
from app.core.config import AppEnvironment, Settings
from fastapi import Response


def _settings(*, secure: bool) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_url="postgresql+psycopg://app:secret@localhost/penny_saved_test",
        session_cookie_name="test_session",
        session_ttl_seconds=600,
        session_cookie_secure=secure,
    )


def test_set_session_cookie_uses_required_attributes() -> None:
    response = Response()

    set_session_cookie(response, raw_token="browser-token", settings=_settings(secure=True))

    header = response.headers["set-cookie"]
    assert "test_session=browser-token" in header
    assert "HttpOnly" in header
    assert "Max-Age=600" in header
    assert "Path=/" in header
    assert "SameSite=lax" in header
    assert "Secure" in header


def test_set_session_cookie_omits_secure_when_disabled() -> None:
    response = Response()

    set_session_cookie(response, raw_token="browser-token", settings=_settings(secure=False))

    assert "Secure" not in response.headers["set-cookie"]


def test_clear_session_cookie_matches_scope_and_security_attributes() -> None:
    response = Response()

    clear_session_cookie(response, settings=_settings(secure=True))

    header = response.headers["set-cookie"]
    assert "test_session=" in header
    assert "Max-Age=0" in header
    assert "HttpOnly" in header
    assert "Path=/" in header
    assert "SameSite=lax" in header
    assert "Secure" in header
