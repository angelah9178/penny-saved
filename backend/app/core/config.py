"""Typed application configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnvironment = Literal["development", "test", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Configuration sourced from explicit arguments or environment variables."""

    model_config = SettingsConfigDict(
        case_sensitive=True,
        extra="ignore",
        populate_by_name=True,
        validate_default=True,
    )

    app_env: AppEnvironment = Field(default="development", validation_alias="APP_ENV")
    database_url: str = Field(validation_alias="DATABASE_URL")
    frontend_origin: str = Field(validation_alias="FRONTEND_ORIGIN")
    session_cookie_name: str = Field(
        default="penny_saved_session",
        min_length=1,
        validation_alias="SESSION_COOKIE_NAME",
    )
    session_ttl_seconds: int = Field(
        default=2_592_000,
        gt=0,
        validation_alias="SESSION_TTL_SECONDS",
    )
    session_cookie_secure: bool = Field(
        default=False,
        validation_alias="SESSION_COOKIE_SECURE",
    )
    log_level: LogLevel = Field(default="INFO", validation_alias="LOG_LEVEL")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Require the async psycopg SQLAlchemy URL selected by the design."""
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use postgresql+psycopg://")
        return value

    @field_validator("frontend_origin")
    @classmethod
    def validate_frontend_origin(cls, value: str) -> str:
        """Require one exact HTTP(S) origin without paths or wildcards."""
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or "*" in value
        ):
            raise ValueError("FRONTEND_ORIGIN must be one exact HTTP(S) origin")
        return value.rstrip("/")

    @model_validator(mode="after")
    def validate_production_security(self) -> Self:
        """Fail early when production-only security requirements are unmet."""
        if self.app_env != "production":
            return self

        errors: list[str] = []
        if not self.session_cookie_secure:
            errors.append("SESSION_COOKIE_SECURE must be true in production")
        if not self.frontend_origin.startswith("https://"):
            errors.append("FRONTEND_ORIGIN must use HTTPS in production")
        if "change-me" in self.database_url.lower():
            errors.append("DATABASE_URL contains a placeholder credential")
        if errors:
            raise ValueError("; ".join(errors))
        return self


@lru_cache
def get_settings() -> Settings:
    """Load local dotenv values only when the process is not production."""
    import os

    app_env = os.environ.get("APP_ENV", "development")
    env_file = Path(__file__).resolve().parents[2] / ".env"
    return Settings(_env_file=env_file if app_env != "production" else None)  # type: ignore[call-arg]
