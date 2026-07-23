"""Tests for canonical, safe API error responses."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from io import StringIO
from uuid import UUID

import httpx
import pytest
from app.api.errors import ApplicationError
from app.core.config import AppEnvironment, Settings
from app.core.logging import REQUEST_ID_HEADER, configure_logging
from app.main import create_app
from fastapi import FastAPI
from pydantic import BaseModel, Field
from sqlalchemy.exc import OperationalError

DATABASE_URL = "postgresql+psycopg://app:secret@localhost:5432/penny_saved"


class ExamplePayload(BaseModel):
    name: str = Field(min_length=3)
    count: int


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_url=DATABASE_URL,
    )


@asynccontextmanager
async def no_database_lifespan(app: FastAPI) -> AsyncIterator[None]:
    del app
    yield


@asynccontextmanager
async def api_client(
    app: FastAPI,
    *,
    raise_app_exceptions: bool = True,
) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(
        app=app,
        raise_app_exceptions=raise_app_exceptions,
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def error_test_app(settings: Settings) -> FastAPI:
    app = create_app(settings, lifespan=no_database_lifespan)

    @app.post("/examples")
    async def create_example(payload: ExamplePayload) -> ExamplePayload:
        return payload

    @app.get("/application-error")
    async def raise_application_error() -> None:
        raise ApplicationError(
            status_code=409,
            code="example_conflict",
            message="The example conflicts with existing data.",
            fields={"name": "Choose a different name."},
        )

    @app.get("/database-error")
    async def raise_database_error() -> None:
        raise OperationalError(
            "SELECT database-secret",
            {"password": "database-password-secret"},
            RuntimeError("driver-secret"),
        )

    @app.get("/unexpected-error")
    async def raise_unexpected_error() -> None:
        raise RuntimeError("unexpected-exception-secret")

    @app.get("/resources/{resource_id}")
    async def read_resource(resource_id: UUID) -> dict[str, str]:
        return {"resource_id": str(resource_id)}

    return app


@pytest.mark.asyncio
async def test_application_error_uses_exact_envelope(settings: Settings) -> None:
    app = error_test_app(settings)

    async with api_client(app) as client:
        response = await client.get("/application-error")

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "example_conflict",
            "message": "The example conflicts with existing data.",
            "fields": {"name": "Choose a different name."},
        }
    }


@pytest.mark.asyncio
async def test_validation_error_has_safe_field_messages(settings: Settings) -> None:
    app = error_test_app(settings)

    async with api_client(app) as client:
        response = await client.post(
            "/examples",
            json={"name": "x", "count": "not-an-integer", "secret": "input-secret"},
        )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "The submitted data is invalid.",
            "fields": {
                "name": "Enter valid text.",
                "count": "Enter a valid integer.",
            },
        }
    }
    assert "input-secret" not in response.text
    assert "not-an-integer" not in response.text


@pytest.mark.asyncio
async def test_missing_field_validation_is_safe(settings: Settings) -> None:
    app = error_test_app(settings)

    async with api_client(app) as client:
        response = await client.post("/examples", json={"name": "valid"})

    assert response.status_code == 422
    assert response.json()["error"]["fields"] == {
        "count": "This field is required.",
    }


@pytest.mark.asyncio
async def test_malformed_uuid_path_uses_safe_validation_envelope(
    settings: Settings,
) -> None:
    app = error_test_app(settings)

    async with api_client(app) as client:
        response = await client.get("/resources/not-a-uuid")

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "The submitted data is invalid.",
            "fields": {"resource_id": "Enter a valid identifier."},
        }
    }


@pytest.mark.asyncio
async def test_malformed_json_returns_safe_400(settings: Settings) -> None:
    app = error_test_app(settings)

    async with api_client(app) as client:
        response = await client.post(
            "/examples",
            content='{"name": "secret-value",',
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "malformed_json",
            "message": "The request body contains malformed JSON.",
        }
    }
    assert "secret-value" not in response.text


@pytest.mark.asyncio
async def test_database_error_returns_generic_503(settings: Settings) -> None:
    app = error_test_app(settings)

    async with api_client(app) as client:
        response = await client.get("/database-error")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "service_unavailable",
            "message": "The service is temporarily unavailable.",
        }
    }
    for secret in ("database-secret", "database-password-secret", "driver-secret"):
        assert secret not in response.text


@pytest.mark.asyncio
async def test_unexpected_error_is_safe_and_request_correlated(
    settings: Settings,
) -> None:
    app = error_test_app(settings)
    stream = StringIO()
    configure_logging(settings.app_env, settings.log_level, stream=stream)

    async with api_client(app, raise_app_exceptions=False) as client:
        response = await client.get("/unexpected-error")

    request_id = response.headers[REQUEST_ID_HEADER]
    assert str(UUID(request_id)) == request_id
    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "An unexpected error occurred.",
        }
    }
    assert "unexpected-exception-secret" not in response.text

    logs = [json.loads(line) for line in stream.getvalue().splitlines()]
    error_log = next(log for log in logs if log["message"] == "request.unhandled_exception")
    assert error_log["request_id"] == request_id
    assert error_log["exception_type"] == "RuntimeError"
    assert error_log["stack_trace"]
    assert "unexpected-exception-secret" not in stream.getvalue()
