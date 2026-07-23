"""Typed application configuration loaded from the process environment."""

from __future__ import annotations

import os
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

BACKEND_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class AppEnvironment(StrEnum):
    """Supported application deployment environments."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """Log levels supported by the application logging configuration."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """Validated settings for one application process."""

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

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Require the async psycopg SQLAlchemy URL used by this project."""
        try:
            url = make_url(value)
        except ArgumentError as error:
            raise ValueError("DATABASE_URL must be a valid SQLAlchemy database URL") from error

        if url.drivername != "postgresql+psycopg":
            raise ValueError("DATABASE_URL must use the postgresql+psycopg driver")
        if not url.database:
            raise ValueError("DATABASE_URL must include a database name")
        return value

    @field_validator("frontend_origin")
    @classmethod
    def validate_frontend_origin(
        cls,
        value: str | None,
        info: ValidationInfo,
    ) -> str | None:
        """Require one exact HTTP(S) browser origin outside the test environment."""
        app_env = info.data.get("app_env", AppEnvironment.DEVELOPMENT)
        if value is None:
            if app_env != AppEnvironment.TEST:
                raise ValueError("FRONTEND_ORIGIN is required outside the test environment")
            return None

        if value == "*":
            raise ValueError("FRONTEND_ORIGIN cannot be a wildcard when credentials are enabled")

        parsed = urlsplit(value)
        is_http_origin = (
            parsed.scheme in {"http", "https"}
            and parsed.netloc
            and parsed.hostname is not None
            and parsed.username is None
            and parsed.password is None
            and parsed.path in {"", "/"}
            and not parsed.query
            and not parsed.fragment
        )
        if not is_http_origin:
            raise ValueError(
                "FRONTEND_ORIGIN must be an exact http(s) origin without a path, "
                "query, fragment, or credentials"
            )
        return value.removesuffix("/")

    @field_validator("session_cookie_secure")
    @classmethod
    def validate_production_secure_cookie(
        cls,
        value: bool,
        info: ValidationInfo,
    ) -> bool:
        """Require HTTPS-only session cookies in production."""
        if info.data.get("app_env") == AppEnvironment.PRODUCTION and not value:
            raise ValueError("SESSION_COOKIE_SECURE must be true in production")
        return value


def _settings_kwargs() -> dict[str, Any]:
    """Select environment-file loading before Pydantic reads any settings."""
    app_env = os.environ.get("APP_ENV", AppEnvironment.DEVELOPMENT.value).lower()
    if app_env == AppEnvironment.DEVELOPMENT:
        return {"_env_file": BACKEND_ENV_FILE, "_env_file_encoding": "utf-8"}
    return {"_env_file": None}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the validated settings shared by the application process."""
    return Settings(**_settings_kwargs())


def clear_settings_cache() -> None:
    """Clear cached settings so tests can safely change the environment."""
    get_settings.cache_clear()
