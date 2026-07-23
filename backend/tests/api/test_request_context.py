"""Tests for request IDs and structured request-completion logs."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from io import StringIO
from uuid import UUID

import httpx
import pytest
from app.core.config import AppEnvironment, Settings
from app.core.logging import (
    REQUEST_ID_HEADER,
    configure_logging,
    get_request_id,
)
from app.main import create_app
from fastapi import FastAPI

DATABASE_URL = "postgresql+psycopg://app:secret@localhost:5432/penny_saved"
FRONTEND_ORIGIN = "http://localhost:5173"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_url=DATABASE_URL,
        frontend_origin=FRONTEND_ORIGIN,
    )


@asynccontextmanager
async def no_database_lifespan(app: FastAPI) -> AsyncIterator[None]:
    del app
    yield


@asynccontextmanager
async def api_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def app_with_captured_logs(settings: Settings) -> tuple[FastAPI, StringIO]:
    app = create_app(settings, lifespan=no_database_lifespan)
    stream = StringIO()
    configure_logging(settings.app_env, settings.log_level, stream=stream)
    return app, stream


def parse_logs(stream: StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines()]


@pytest.mark.asyncio
async def test_missing_request_id_is_generated_and_correlated(settings: Settings) -> None:
    app, stream = app_with_captured_logs(settings)

    async with api_client(app) as client:
        response = await client.get("/api/health")

    response_request_id = response.headers[REQUEST_ID_HEADER]
    assert str(UUID(response_request_id)) == response_request_id
    log = parse_logs(stream)[0]
    assert log["request_id"] == response_request_id
    assert log["method"] == "GET"
    assert log["route"] == "/api/health"
    assert log["status"] == 200
    assert isinstance(log["duration_ms"], float)


@pytest.mark.asyncio
async def test_valid_inbound_request_id_is_propagated(settings: Settings) -> None:
    app, stream = app_with_captured_logs(settings)
    request_id = "07a541df-c2db-4e26-976e-14a03b11bc49"

    async with api_client(app) as client:
        response = await client.get(
            "/api/health",
            headers={REQUEST_ID_HEADER: request_id},
        )

    assert response.headers[REQUEST_ID_HEADER] == request_id
    assert parse_logs(stream)[0]["request_id"] == request_id


@pytest.mark.asyncio
async def test_invalid_inbound_request_id_is_replaced(settings: Settings) -> None:
    app, stream = app_with_captured_logs(settings)

    async with api_client(app) as client:
        response = await client.get(
            "/api/health",
            headers={REQUEST_ID_HEADER: "not-a-valid-request-id"},
        )

    generated_id = response.headers[REQUEST_ID_HEADER]
    assert generated_id != "not-a-valid-request-id"
    assert str(UUID(generated_id)) == generated_id
    assert parse_logs(stream)[0]["request_id"] == generated_id


@pytest.mark.asyncio
async def test_route_template_avoids_high_cardinality_identifiers(
    settings: Settings,
) -> None:
    app, stream = app_with_captured_logs(settings)

    @app.get("/items/{item_id}")
    async def read_item(item_id: str) -> dict[str, str]:
        return {"item_id": item_id}

    async with api_client(app) as client:
        response = await client.get("/items/sensitive-item-123")

    assert response.status_code == 200
    log = parse_logs(stream)[0]
    assert log["route"] == "/items/{item_id}"
    assert "sensitive-item-123" not in stream.getvalue()


@pytest.mark.asyncio
async def test_concurrent_request_contexts_remain_isolated(settings: Settings) -> None:
    app, stream = app_with_captured_logs(settings)

    @app.get("/context/{delay}")
    async def read_context(delay: float) -> dict[str, str | None]:
        first = get_request_id()
        await asyncio.sleep(delay)
        return {"first": first, "second": get_request_id()}

    first_id = "01a9a8a0-4464-4589-a405-54dc247f41ec"
    second_id = "d9ea0f4d-95a5-4a30-b0a5-322601a52af8"
    async with api_client(app) as client:
        first_response, second_response = await asyncio.gather(
            client.get("/context/0.01", headers={REQUEST_ID_HEADER: first_id}),
            client.get("/context/0", headers={REQUEST_ID_HEADER: second_id}),
        )

    assert first_response.json() == {"first": first_id, "second": first_id}
    assert second_response.json() == {"first": second_id, "second": second_id}
    logs_by_id = {log["request_id"]: log for log in parse_logs(stream)}
    assert logs_by_id[first_id]["route"] == "/context/{delay}"
    assert logs_by_id[second_id]["route"] == "/context/{delay}"


@pytest.mark.asyncio
async def test_request_logs_omit_headers_query_and_body_secrets(
    settings: Settings,
) -> None:
    app, stream = app_with_captured_logs(settings)

    @app.post("/sensitive")
    async def accept_sensitive_request() -> dict[str, bool]:
        return {"accepted": True}

    async with api_client(app) as client:
        response = await client.post(
            "/sensitive?token=query-secret",
            headers={
                "Authorization": "Bearer authorization-secret",
                "Cookie": "session=cookie-secret",
            },
            json={"password": "password-secret"},
        )

    assert response.status_code == 200
    output = stream.getvalue()
    assert "query-secret" not in output
    assert "authorization-secret" not in output
    assert "cookie-secret" not in output
    assert "password-secret" not in output
