"""Typed and validated application configuration."""

from __future__ import annotations

import os
import re
from enum import StrEnum
from functools import lru_cache
from ipaddress import ip_address, ip_network
from pathlib import Path
from typing import Any, Self
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

BACKEND_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
_HOST_PATTERN = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*$"
)


class AppEnvironment(StrEnum):
    """Environments supported by the application."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """Supported application log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """Configuration validated before application startup."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_env: AppEnvironment = AppEnvironment.DEVELOPMENT
    database_url: str
    frontend_origin: str | None = None
    session_cookie_name: str = Field(
        default="penny_saved_session",
        min_length=1,
        pattern=r"^[A-Za-z0-9!#$%&'*+\-.^_`|~]+$",
    )
    session_ttl_seconds: int = Field(default=2_592_000, gt=0)
    session_cookie_secure: bool = False
    log_level: LogLevel = LogLevel.INFO
    trusted_hosts: tuple[str, ...] = ("localhost", "127.0.0.1")
    trusted_proxy_networks: tuple[str, ...] = ()
    max_request_body_bytes: int = Field(default=1_048_576, ge=1_024, le=10_485_760)
    auth_rate_limit_window_seconds: int = Field(default=900, ge=1, le=86_400)
    auth_login_ip_limit: int = Field(default=20, ge=1, le=10_000)
    auth_login_account_limit: int = Field(default=10, ge=1, le=10_000)
    auth_signup_ip_limit: int = Field(default=10, ge=1, le=10_000)
    auth_signup_account_limit: int = Field(default=3, ge=1, le=10_000)

    @model_validator(mode="after")
    def validate_configuration(self) -> Self:
        """Validate rules involving one or more settings."""
        self.database_url = _validate_database_url(self.database_url)

        if self.frontend_origin is None:
            if self.app_env != AppEnvironment.TEST:
                raise ValueError("FRONTEND_ORIGIN is required outside the test environment")
        else:
            self.frontend_origin = _validate_frontend_origin(self.frontend_origin)

        self.trusted_hosts = _validate_trusted_hosts(self.trusted_hosts)
        self.trusted_proxy_networks = _validate_trusted_proxy_networks(
            self.trusted_proxy_networks,
            production=self.app_env == AppEnvironment.PRODUCTION,
        )

        if self.app_env == AppEnvironment.PRODUCTION and not self.session_cookie_secure:
            raise ValueError("SESSION_COOKIE_SECURE must be true in production")
        if (
            self.app_env == AppEnvironment.PRODUCTION
            and self.frontend_origin is not None
            and not self.frontend_origin.startswith("https://")
        ):
            raise ValueError("FRONTEND_ORIGIN must use HTTPS in production")
        if self.app_env == AppEnvironment.PRODUCTION and self.frontend_origin is not None:
            frontend_host = urlsplit(self.frontend_origin).hostname
            if frontend_host not in self.trusted_hosts:
                raise ValueError(
                    "TRUSTED_HOSTS must include the production FRONTEND_ORIGIN hostname"
                )

        return self


def _validate_database_url(value: str) -> str:
    """Require the PostgreSQL SQLAlchemy driver selected for this project."""
    try:
        url = make_url(value)
    except ArgumentError as error:
        raise ValueError("DATABASE_URL must be a valid SQLAlchemy database URL") from error

    if url.drivername != "postgresql+psycopg":
        raise ValueError("DATABASE_URL must use the postgresql+psycopg driver")
    if not url.database:
        raise ValueError("DATABASE_URL must include a database name")
    return value


def _validate_frontend_origin(value: str) -> str:
    """Require one exact HTTP(S) browser origin for credentialed CORS."""
    if value == "*":
        raise ValueError("FRONTEND_ORIGIN cannot be a wildcard when credentials are enabled")

    parsed = urlsplit(value)
    try:
        _ = parsed.port
    except ValueError as error:
        raise ValueError("FRONTEND_ORIGIN must contain a valid port") from error

    is_exact_origin = (
        parsed.scheme in {"http", "https"}
        and bool(parsed.netloc)
        and parsed.hostname is not None
        and parsed.username is None
        and parsed.password is None
        and parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment
    )
    if not is_exact_origin:
        raise ValueError(
            "FRONTEND_ORIGIN must be an exact http(s) origin without a path, "
            "query, fragment, or credentials"
        )
    return value.removesuffix("/")


def _validate_trusted_hosts(values: tuple[str, ...]) -> tuple[str, ...]:
    """Normalize an exact host allowlist without ports, schemes, or wildcards."""
    if not values:
        raise ValueError("TRUSTED_HOSTS must contain at least one exact hostname or IP address")

    normalized: list[str] = []
    for value in values:
        host = value.strip().lower().removesuffix(".")
        is_valid = bool(host) and host != "*" and "://" not in host and "/" not in host
        try:
            normalized_host = str(ip_address(host.removeprefix("[").removesuffix("]")))
        except ValueError:
            normalized_host = host
            is_valid = is_valid and ":" not in host and bool(_HOST_PATTERN.fullmatch(host))
        if not is_valid:
            raise ValueError(
                "TRUSTED_HOSTS entries must be exact hostnames or IPv4 addresses "
                "without schemes, ports, paths, or wildcards"
            )
        if normalized_host not in normalized:
            normalized.append(normalized_host)
    return tuple(normalized)


def _validate_trusted_proxy_networks(
    values: tuple[str, ...],
    *,
    production: bool,
) -> tuple[str, ...]:
    """Normalize explicitly trusted proxy networks and reject trust-everywhere ranges."""
    normalized: list[str] = []
    for value in values:
        try:
            network = ip_network(value, strict=False)
        except ValueError as error:
            raise ValueError("TRUSTED_PROXY_NETWORKS entries must be valid IP networks") from error
        if production and network.prefixlen == 0:
            raise ValueError("TRUSTED_PROXY_NETWORKS cannot trust every address in production")
        canonical = str(network)
        if canonical not in normalized:
            normalized.append(canonical)
    return tuple(normalized)


def _settings_source_options() -> dict[str, Any]:
    """Load the local dotenv file only when starting in development."""
    app_env = os.environ.get("APP_ENV", AppEnvironment.DEVELOPMENT.value).lower()
    if app_env == AppEnvironment.DEVELOPMENT:
        return {"_env_file": BACKEND_ENV_FILE, "_env_file_encoding": "utf-8"}
    return {"_env_file": None}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the settings shared by one application process."""
    return Settings(**_settings_source_options())


def clear_settings_cache() -> None:
    """Clear cached settings when a test changes its environment."""
    get_settings.cache_clear()
