"""Tests for typed application configuration."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.config import (
    AppEnvironment,
    LogLevel,
    Settings,
    clear_settings_cache,
    get_settings,
)
from pydantic import ValidationError

DATABASE_URL = "postgresql+psycopg://app:secret@localhost:5432/penny_saved"
FRONTEND_ORIGIN = "http://localhost:5173"


@pytest.fixture(autouse=True)
def isolated_settings_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Keep tests independent from developer shell variables and backend/.env."""
    for name in (
        "APP_ENV",
        "DATABASE_URL",
        "FRONTEND_ORIGIN",
        "SESSION_COOKIE_NAME",
        "SESSION_TTL_SECONDS",
        "SESSION_COOKIE_SECURE",
        "LOG_LEVEL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    clear_settings_cache()
    yield
    clear_settings_cache()


def test_settings_apply_development_defaults() -> None:
    settings = Settings(
        _env_file=None,
        database_url=DATABASE_URL,
        frontend_origin=FRONTEND_ORIGIN,
    )

    assert settings.app_env is AppEnvironment.DEVELOPMENT
    assert settings.session_cookie_name == "penny_saved_session"
    assert settings.session_ttl_seconds == 2_592_000
    assert settings.session_cookie_secure is False
    assert settings.log_level is LogLevel.INFO


def test_settings_read_typed_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("SESSION_COOKIE_NAME", "custom_session")
    monkeypatch.setenv("SESSION_TTL_SECONDS", "3600")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = get_settings()

    assert settings.app_env is AppEnvironment.TEST
    assert settings.frontend_origin is None
    assert settings.session_cookie_name == "custom_session"
    assert settings.session_ttl_seconds == 3600
    assert settings.session_cookie_secure is True
    assert settings.log_level is LogLevel.DEBUG


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)

    first = get_settings()
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL.replace("penny_saved", "other"))

    assert get_settings() is first
    clear_settings_cache()
    assert get_settings().database_url.endswith("/other")


@pytest.mark.parametrize("app_env", ["local", "staging", ""])
def test_settings_reject_unknown_environment(app_env: str) -> None:
    with pytest.raises(ValidationError, match="app_env"):
        Settings(
            _env_file=None,
            app_env=app_env,
            database_url=DATABASE_URL,
            frontend_origin=FRONTEND_ORIGIN,
        )


@pytest.mark.parametrize(
    "database_url",
    [
        "not-a-url",
        "sqlite:///penny_saved.sqlite3",
        "postgresql+asyncpg://app:secret@localhost/penny_saved",
        "postgresql+psycopg://app:secret@localhost",
    ],
)
def test_settings_reject_invalid_database_url(database_url: str) -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(
            _env_file=None,
            database_url=database_url,
            frontend_origin=FRONTEND_ORIGIN,
        )


@pytest.mark.parametrize(
    "frontend_origin",
    [
        "*",
        "localhost:5173",
        "ftp://localhost:5173",
        "https://user:password@example.com",
        "https://example.com/app",
        "https://example.com?source=test",
        "https://example.com#fragment",
    ],
)
def test_settings_reject_non_exact_frontend_origin(frontend_origin: str) -> None:
    with pytest.raises(ValidationError, match="FRONTEND_ORIGIN"):
        Settings(
            _env_file=None,
            database_url=DATABASE_URL,
            frontend_origin=frontend_origin,
        )


def test_settings_normalize_trailing_origin_slash() -> None:
    settings = Settings(
        _env_file=None,
        database_url=DATABASE_URL,
        frontend_origin=f"{FRONTEND_ORIGIN}/",
    )

    assert settings.frontend_origin == FRONTEND_ORIGIN


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("session_ttl_seconds", 0),
        ("session_ttl_seconds", -1),
        ("session_cookie_name", ""),
        ("session_cookie_name", "invalid cookie"),
        ("log_level", "TRACE"),
    ],
)
def test_settings_reject_malformed_values(field: str, value: object) -> None:
    values = {
        "database_url": DATABASE_URL,
        "frontend_origin": FRONTEND_ORIGIN,
        field: value,
    }

    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_test_environment_allows_missing_frontend_origin() -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_url=DATABASE_URL,
    )

    assert settings.frontend_origin is None


def test_development_requires_frontend_origin() -> None:
    with pytest.raises(ValidationError, match="FRONTEND_ORIGIN"):
        Settings(
            _env_file=None,
            app_env=AppEnvironment.DEVELOPMENT,
            database_url=DATABASE_URL,
        )


def test_production_requires_secure_cookie() -> None:
    with pytest.raises(ValidationError, match="SESSION_COOKIE_SECURE"):
        Settings(
            _env_file=None,
            app_env=AppEnvironment.PRODUCTION,
            database_url=DATABASE_URL,
            frontend_origin="https://stopimpulsebuying.us",
            session_cookie_secure=False,
        )


def test_valid_production_configuration() -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnvironment.PRODUCTION,
        database_url=DATABASE_URL,
        frontend_origin="https://stopimpulsebuying.us",
        session_cookie_secure=True,
        log_level=LogLevel.WARNING,
    )

    assert settings.app_env is AppEnvironment.PRODUCTION
    assert settings.session_cookie_secure is True


def test_validation_error_text_hides_database_credentials() -> None:
    secret = "do-not-disclose"

    with pytest.raises(ValidationError) as error:
        Settings(
            _env_file=None,
            database_url=f"mysql://user:{secret}@localhost/penny_saved",
            frontend_origin=FRONTEND_ORIGIN,
        )

    assert secret not in str(error.value)
