"""Typed and validated application configuration."""

from __future__ import annotations

import os
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, Self
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

BACKEND_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


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

    @model_validator(mode="after")
    def validate_configuration(self) -> Self:
        """Validate rules involving one or more settings."""
        self.database_url = _validate_database_url(self.database_url)

        if self.frontend_origin is None:
            if self.app_env != AppEnvironment.TEST:
                raise ValueError("FRONTEND_ORIGIN is required outside the test environment")
        else:
            self.frontend_origin = _validate_frontend_origin(self.frontend_origin)

        if self.app_env == AppEnvironment.PRODUCTION and not self.session_cookie_secure:
            raise ValueError("SESSION_COOKIE_SECURE must be true in production")

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
