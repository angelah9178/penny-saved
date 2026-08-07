"""Authentication rate-limit policy and response tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from app.api.dependencies import enforce_auth_rate_limit
from app.api.errors import ApplicationError, application_error_handler
from app.core.config import AppEnvironment, Settings
from app.core.rate_limits import InMemoryRateLimitStore, digest_rate_limit_key
from app.core.time import FixedClock
from app.schemas.auth import AuthRequest
from fastapi import FastAPI
from starlette.requests import Request

NOW = datetime(2026, 8, 7, 12, tzinfo=UTC)
DATABASE_URL = "postgresql+psycopg://test:test@localhost/penny_saved_test"
SECRET = "test-rate-limit-secret-that-is-at-least-32-bytes"
PASSWORD = "password123"


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "app_env": AppEnvironment.TEST,
        "database_url": DATABASE_URL,
        "rate_limit_key_secret": SECRET,
        "auth_rate_limit_window_seconds": 900,
        "auth_login_ip_limit": 20,
        "auth_login_account_limit": 10,
        "auth_signup_ip_limit": 10,
        "auth_signup_account_limit": 3,
    }
    values.update(overrides)
    return Settings(**values)


def request_for(configuration: Settings, *, client_host: str = "203.0.113.10") -> Request:
    app = FastAPI()
    app.state.settings = configuration
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": "/api/auth/login",
            "raw_path": b"/api/auth/login",
            "query_string": b"",
            "headers": [],
            "client": (client_host, 12345),
            "server": ("example.com", 443),
            "app": app,
        }
    )


@pytest.mark.asyncio
async def test_normalized_account_limit_blocks_case_and_space_variants() -> None:
    configuration = settings(auth_login_account_limit=1)
    store = InMemoryRateLimitStore()
    request = request_for(configuration)
    first_email = AuthRequest(email=" Person@Example.com ", password=PASSWORD).email
    second_email = AuthRequest(email="person@example.com", password=PASSWORD).email

    await enforce_auth_rate_limit(
        request=request,
        credentials_email=first_email,
        action="login",
        clock=FixedClock(NOW),
        store=store,
    )
    with pytest.raises(ApplicationError) as blocked:
        await enforce_auth_rate_limit(
            request=request,
            credentials_email=second_email,
            action="login",
            clock=FixedClock(NOW),
            store=store,
        )

    error = blocked.value
    assert error.status_code == 429
    assert error.code == "rate_limited"
    assert error.headers == {"Retry-After": "900"}


@pytest.mark.asyncio
async def test_ip_limit_spans_accounts_but_actions_are_independent() -> None:
    configuration = settings(auth_login_ip_limit=1)
    store = InMemoryRateLimitStore()
    request = request_for(configuration)

    await enforce_auth_rate_limit(
        request=request,
        credentials_email="first@example.com",
        action="login",
        clock=FixedClock(NOW),
        store=store,
    )
    with pytest.raises(ApplicationError) as blocked:
        await enforce_auth_rate_limit(
            request=request,
            credentials_email="second@example.com",
            action="login",
            clock=FixedClock(NOW),
            store=store,
        )
    await enforce_auth_rate_limit(
        request=request,
        credentials_email="second@example.com",
        action="signup",
        clock=FixedClock(NOW),
        store=store,
    )

    assert blocked.value.status_code == 429


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "limit_field"),
    [
        ("login", "auth_login_account_limit"),
        ("signup", "auth_signup_account_limit"),
    ],
)
async def test_blocked_response_is_uniform_and_never_mutates_a_cookie(
    action: str,
    limit_field: str,
) -> None:
    configuration = settings(**{limit_field: 1})
    store = InMemoryRateLimitStore()
    email = "unknown@example.com"
    account_bucket = f"{action}.account"
    await store.consume(
        bucket=account_bucket,
        key_digest=digest_rate_limit_key(
            secret=SECRET.encode(),
            domain=account_bucket,
            value=email,
        ),
        limit=1,
        window_seconds=900,
        now=NOW,
    )
    request = request_for(configuration)
    with pytest.raises(ApplicationError) as blocked:
        await enforce_auth_rate_limit(
            request=request,
            credentials_email=email,
            action=action,
            clock=FixedClock(NOW),
            store=store,
        )
    response = await application_error_handler(request, blocked.value)

    assert response.status_code == 429
    assert json.loads(response.body) == {
        "error": {
            "code": "rate_limited",
            "message": "Too many authentication attempts. Try again later.",
        }
    }
    assert response.headers["retry-after"] == "900"
    assert "set-cookie" not in response.headers
