"""Tests for typed backend configuration."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from app.core.config import (
    AppEnvironment,
    LogFormat,
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
    "LOG_FORMAT",
    "HEALTH_CHECK_TIMEOUT_SECONDS",
    "METRICS_ENABLED",
    "GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS",
    "TRUSTED_HOSTS",
    "TRUSTED_PROXY_NETWORKS",
    "MAX_REQUEST_BODY_BYTES",
    "AUTH_RATE_LIMIT_WINDOW_SECONDS",
    "AUTH_LOGIN_IP_LIMIT",
    "AUTH_LOGIN_ACCOUNT_LIMIT",
    "AUTH_SIGNUP_IP_LIMIT",
    "AUTH_SIGNUP_ACCOUNT_LIMIT",
    "RATE_LIMIT_KEY_SECRET",
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
    assert settings.log_format is LogFormat.JSON
    assert settings.health_check_timeout_seconds == 2.0
    assert settings.metrics_enabled is False
    assert settings.graceful_shutdown_timeout_seconds == 30
    assert settings.trusted_hosts == ("localhost", "127.0.0.1")
    assert settings.trusted_proxy_networks == ()
    assert settings.max_request_body_bytes == 1_048_576
    assert settings.auth_rate_limit_window_seconds == 900
    assert settings.auth_login_ip_limit == 20
    assert settings.auth_login_account_limit == 10
    assert settings.auth_signup_ip_limit == 10
    assert settings.auth_signup_account_limit == 3
    assert settings.rate_limit_key_secret.get_secret_value() == (
        "development-only-rate-limit-key-secret"
    )


def test_environment_values_are_parsed_into_expected_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("SESSION_COOKIE_NAME", "custom_session")
    monkeypatch.setenv("SESSION_TTL_SECONDS", "3600")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FORMAT", "text")
    monkeypatch.setenv("HEALTH_CHECK_TIMEOUT_SECONDS", "1.5")
    monkeypatch.setenv("METRICS_ENABLED", "true")
    monkeypatch.setenv("GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("TRUSTED_HOSTS", '["api.example.com"]')
    monkeypatch.setenv("TRUSTED_PROXY_NETWORKS", '["10.0.0.7/24"]')
    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", "2097152")
    monkeypatch.setenv("AUTH_LOGIN_IP_LIMIT", "30")

    settings = get_settings()

    assert settings.app_env is AppEnvironment.TEST
    assert settings.frontend_origin is None
    assert settings.session_cookie_name == "custom_session"
    assert settings.session_ttl_seconds == 3600
    assert settings.session_cookie_secure is True
    assert settings.log_level is LogLevel.DEBUG
    assert settings.log_format is LogFormat.TEXT
    assert settings.health_check_timeout_seconds == 1.5
    assert settings.metrics_enabled is True
    assert settings.graceful_shutdown_timeout_seconds == 45
    assert settings.trusted_hosts == ("api.example.com",)
    assert settings.trusted_proxy_networks == ("10.0.0.0/24",)
    assert settings.max_request_body_bytes == 2_097_152
    assert settings.auth_login_ip_limit == 30


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
        ("log_format", "xml"),
        ("health_check_timeout_seconds", 0.09),
        ("health_check_timeout_seconds", 30.1),
        ("graceful_shutdown_timeout_seconds", 0),
        ("graceful_shutdown_timeout_seconds", 301),
        ("max_request_body_bytes", 1_023),
        ("max_request_body_bytes", 10_485_761),
        ("auth_rate_limit_window_seconds", 0),
        ("auth_login_ip_limit", 0),
        ("auth_login_account_limit", 10_001),
        ("auth_signup_ip_limit", -1),
        ("auth_signup_account_limit", 0),
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
        trusted_hosts=("stopimpulsebuying.us",),
        rate_limit_key_secret="production-rate-limit-secret-at-least-32-bytes",
    )

    assert settings.app_env is AppEnvironment.PRODUCTION
    assert settings.session_cookie_secure is True


def test_production_requires_json_log_format() -> None:
    with pytest.raises(ValidationError, match="LOG_FORMAT"):
        Settings(
            _env_file=None,
            app_env=AppEnvironment.PRODUCTION,
            database_url=DATABASE_URL,
            frontend_origin="https://stopimpulsebuying.us",
            session_cookie_secure=True,
            log_format=LogFormat.TEXT,
            trusted_hosts=("stopimpulsebuying.us",),
            rate_limit_key_secret="production-rate-limit-secret-at-least-32-bytes",
        )


@pytest.mark.parametrize(
    "trusted_hosts",
    [
        (),
        ("*",),
        ("https://example.com",),
        ("example.com:443",),
        ("example.com/path",),
        ("bad_host.example",),
    ],
)
def test_invalid_trusted_hosts_are_rejected(trusted_hosts: tuple[str, ...]) -> None:
    with pytest.raises(ValidationError, match="TRUSTED_HOSTS"):
        development_settings(trusted_hosts=trusted_hosts)


def test_trusted_hosts_are_normalized_and_deduplicated() -> None:
    settings = development_settings(
        trusted_hosts=("API.Example.com.", "api.example.com", "127.0.0.1", "[::1]"),
    )

    assert settings.trusted_hosts == ("api.example.com", "127.0.0.1", "::1")


@pytest.mark.parametrize("network", ["not-a-network", "10.0.0.999/24"])
def test_invalid_trusted_proxy_network_is_rejected(network: str) -> None:
    with pytest.raises(ValidationError, match="TRUSTED_PROXY_NETWORKS"):
        development_settings(trusted_proxy_networks=(network,))


@pytest.mark.parametrize("network", ["0.0.0.0/0", "::/0"])
def test_production_rejects_trusting_every_proxy(network: str) -> None:
    with pytest.raises(ValidationError, match="TRUSTED_PROXY_NETWORKS"):
        Settings(
            _env_file=None,
            app_env=AppEnvironment.PRODUCTION,
            database_url=DATABASE_URL,
            frontend_origin="https://stopimpulsebuying.us",
            session_cookie_secure=True,
            trusted_hosts=("stopimpulsebuying.us",),
            trusted_proxy_networks=(network,),
            rate_limit_key_secret="production-rate-limit-secret-at-least-32-bytes",
        )


def test_production_host_must_cover_frontend_origin() -> None:
    with pytest.raises(ValidationError, match="TRUSTED_HOSTS"):
        Settings(
            _env_file=None,
            app_env=AppEnvironment.PRODUCTION,
            database_url=DATABASE_URL,
            frontend_origin="https://stopimpulsebuying.us",
            session_cookie_secure=True,
            trusted_hosts=("api.stopimpulsebuying.us",),
            rate_limit_key_secret="production-rate-limit-secret-at-least-32-bytes",
        )


def test_production_requires_a_non_default_rate_limit_secret() -> None:
    with pytest.raises(ValidationError, match="RATE_LIMIT_KEY_SECRET"):
        Settings(
            _env_file=None,
            app_env=AppEnvironment.PRODUCTION,
            database_url=DATABASE_URL,
            frontend_origin="https://stopimpulsebuying.us",
            session_cookie_secure=True,
            trusted_hosts=("stopimpulsebuying.us",),
        )


def test_rate_limit_secret_is_hidden_in_validation_errors() -> None:
    secret = "too-short"

    with pytest.raises(ValidationError) as error:
        development_settings(rate_limit_key_secret=secret)

    assert secret not in str(error.value)


def test_validation_error_text_does_not_expose_database_password() -> None:
    password = "do-not-disclose"

    with pytest.raises(ValidationError) as error:
        development_settings(
            database_url=f"mysql://user:{password}@localhost/penny_saved",
        )

    assert password not in str(error.value)
