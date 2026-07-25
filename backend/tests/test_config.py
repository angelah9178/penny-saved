"""Tests for typed backend configuration."""

from __future__ import annotations

from collections.abc import Iterator

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
SETTING_NAMES = (
    "APP_ENV",
    "DATABASE_URL",
    "FRONTEND_ORIGIN",
    "SESSION_COOKIE_NAME",
    "SESSION_TTL_SECONDS",
    "SESSION_COOKIE_SECURE",
    "LOG_LEVEL",
)


@pytest.fixture(autouse=True)
def isolate_settings_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Prevent developer environment variables and the settings cache leaking into tests."""
    for name in SETTING_NAMES:
        monkeypatch.delenv(name, raising=False)
    clear_settings_cache()
    yield
    clear_settings_cache()


def development_settings(**overrides: object) -> Settings:
    """Build settings without loading the developer's backend/.env file."""
    values: dict[str, object] = {
        "database_url": DATABASE_URL,
        "frontend_origin": FRONTEND_ORIGIN,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_development_defaults_are_typed() -> None:
    settings = development_settings()

    assert settings.app_env is AppEnvironment.DEVELOPMENT
    assert settings.session_cookie_name == "penny_saved_session"
    assert settings.session_ttl_seconds == 2_592_000
    assert settings.session_cookie_secure is False
    assert settings.log_level is LogLevel.INFO


def test_environment_values_are_parsed_into_expected_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_get_settings_caches_until_explicitly_cleared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)

    original = get_settings()
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL.replace("penny_saved", "other"))

    assert get_settings() is original
    clear_settings_cache()
    assert get_settings().database_url.endswith("/other")


@pytest.mark.parametrize("app_env", ["local", "staging", ""])
def test_unknown_environment_is_rejected(app_env: str) -> None:
    with pytest.raises(ValidationError, match="app_env"):
        development_settings(app_env=app_env)


@pytest.mark.parametrize(
    "database_url",
    [
        "not-a-url",
        "sqlite:///penny_saved.sqlite3",
        "postgresql+asyncpg://app:secret@localhost/penny_saved",
        "postgresql+psycopg://app:secret@localhost",
    ],
)
def test_invalid_database_url_is_rejected(database_url: str) -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        development_settings(database_url=database_url)


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
        "https://example.com:invalid",
    ],
)
def test_non_exact_frontend_origin_is_rejected(frontend_origin: str) -> None:
    with pytest.raises(ValidationError, match="FRONTEND_ORIGIN"):
        development_settings(frontend_origin=frontend_origin)


def test_frontend_origin_trailing_slash_is_normalized() -> None:
    settings = development_settings(frontend_origin=f"{FRONTEND_ORIGIN}/")

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
def test_malformed_setting_is_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        development_settings(**{field: value})


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


def test_production_requires_frontend_origin() -> None:
    with pytest.raises(ValidationError, match="FRONTEND_ORIGIN"):
        Settings(
            _env_file=None,
            app_env=AppEnvironment.PRODUCTION,
            database_url=DATABASE_URL,
            session_cookie_secure=True,
        )


def test_production_requires_secure_cookie() -> None:
    with pytest.raises(ValidationError, match="SESSION_COOKIE_SECURE"):
        Settings(
            _env_file=None,
            app_env=AppEnvironment.PRODUCTION,
            database_url=DATABASE_URL,
            frontend_origin="https://stopimpulsebuying.us",
        )


def test_production_requires_https_frontend_origin() -> None:
    with pytest.raises(ValidationError, match="HTTPS"):
        Settings(
            _env_file=None,
            app_env=AppEnvironment.PRODUCTION,
            database_url=DATABASE_URL,
            frontend_origin="http://stopimpulsebuying.us",
            session_cookie_secure=True,
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


def test_validation_error_text_does_not_expose_database_password() -> None:
    password = "do-not-disclose"

    with pytest.raises(ValidationError) as error:
        development_settings(
            database_url=f"mysql://user:{password}@localhost/penny_saved",
        )

    assert password not in str(error.value)
