"""Configuration boundary tests."""

import pytest
from app.core.config import Settings
from pydantic import ValidationError

BASE_SETTINGS = {
    "database_url": "postgresql+psycopg://user:password@localhost:5432/penny_saved",
    "frontend_origin": "http://localhost:5173",
}


def test_development_settings_have_safe_cookie_defaults() -> None:
    settings = Settings(app_env="development", **BASE_SETTINGS)  # type: ignore[arg-type]

    assert settings.app_env == "development"
    assert settings.session_cookie_name == "penny_saved_session"
    assert settings.session_ttl_seconds == 2_592_000
    assert settings.session_cookie_secure is False


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"session_cookie_secure": False}, "SESSION_COOKIE_SECURE"),
        ({"frontend_origin": "http://example.com"}, "FRONTEND_ORIGIN"),
        (
            {
                "database_url": (
                    "postgresql+psycopg://user:change-me@database.example.com/penny_saved"
                )
            },
            "placeholder credential",
        ),
    ],
)
def test_invalid_production_settings_fail_early(
    override: dict[str, object],
    message: str,
) -> None:
    values: dict[str, object] = {
        **BASE_SETTINGS,
        "app_env": "production",
        "frontend_origin": "https://example.com",
        "session_cookie_secure": True,
        **override,
    }

    with pytest.raises(ValidationError, match=message):
        Settings(**values)  # type: ignore[arg-type]


def test_database_driver_and_exact_origin_are_validated() -> None:
    with pytest.raises(ValidationError, match="postgresql\\+psycopg"):
        Settings(  # type: ignore[call-arg]
            database_url="postgresql://user:password@localhost/penny_saved",
            frontend_origin="http://localhost:5173/path",
        )

    with pytest.raises(ValidationError, match="exact HTTP"):
        Settings(  # type: ignore[call-arg]
            database_url=BASE_SETTINGS["database_url"],
            frontend_origin="*",
        )
