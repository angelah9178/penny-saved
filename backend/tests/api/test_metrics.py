"""Tests for private, bounded operational metrics."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from app.api.errors import ApplicationError, application_error_handler
from app.core.config import AppEnvironment, Settings
from app.core.metrics import MetricsRegistry
from app.main import create_app
from fastapi import FastAPI
from starlette.requests import Request

DATABASE_URL = "postgresql+psycopg://app:secret@localhost:5432/penny_saved"


@asynccontextmanager
async def no_database_lifespan(app: FastAPI) -> AsyncIterator[None]:
    del app
    yield


def settings(*, metrics_enabled: bool) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_url=DATABASE_URL,
        metrics_enabled=metrics_enabled,
    )


@asynccontextmanager
async def api_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_metrics_endpoint_is_opt_in() -> None:
    app = create_app(settings(metrics_enabled=False), lifespan=no_database_lifespan)

    async with api_client(app) as client:
        response = await client.get("/internal/metrics")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_bounded_request_and_error_measurements() -> None:
    app = create_app(settings(metrics_enabled=True), lifespan=no_database_lifespan)

    @app.get("/items/{item_id}")
    async def get_item(item_id: str) -> dict[str, str]:
        return {"item_id": item_id}

    async with api_client(app) as client:
        successful = await client.get("/items/private-entry-id?email=private@example.com")
        missing = await client.get("/missing/private-path-value")
        metrics = await client.get("/internal/metrics")

    assert successful.status_code == 200
    assert missing.status_code == 404
    assert metrics.status_code == 200
    assert metrics.headers["content-type"].startswith("text/plain; version=0.0.4")
    output = metrics.text
    assert (
        'http_server_requests_total{method="GET",route="/items/{item_id}",status_class="2xx"} 1'
        in output
    )
    assert (
        'http_server_requests_total{method="GET",route="unmatched",status_class="4xx"} 1' in output
    )
    assert 'http_server_errors_total{method="GET",route="unmatched",status_class="4xx"} 1' in output
    assert (
        'http_server_request_duration_seconds_count{method="GET",route="/items/{item_id}"} 1'
        in output
    )
    assert "/internal/metrics" not in output
    for private_value in (
        "private-entry-id",
        "private@example.com",
        "private-path-value",
    ):
        assert private_value not in output


def test_registry_exports_database_auth_conflict_and_readiness_metrics() -> None:
    class Pool:
        @staticmethod
        def checkedin() -> int:
            return 3

        @staticmethod
        def checkedout() -> int:
            return 2

        @staticmethod
        def overflow() -> int:
            return -1

    registry = MetricsRegistry()
    registry.record_authentication_failure(operation="login", reason="invalid_credentials")
    registry.record_lifecycle_conflict(operation="check_in")
    registry.set_readiness(True)

    output = registry.render(database_pool=Pool())

    assert 'database_pool_connections{state="checked_in"} 3' in output
    assert 'database_pool_connections{state="checked_out"} 2' in output
    assert 'database_pool_connections{state="overflow"} 0' in output
    assert (
        'authentication_failures_total{operation="login",reason="invalid_credentials"} 1' in output
    )
    assert 'entry_lifecycle_conflicts_total{operation="check_in"} 1' in output
    assert "application_readiness 1" in output


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("route", "status_code", "code", "expected_sample"),
    [
        (
            "/api/auth/login",
            401,
            "invalid_credentials",
            'authentication_failures_total{operation="login",reason="invalid_credentials"} 1',
        ),
        (
            "/api/entries/{entry_id}/check-in",
            409,
            "early_check_in",
            'entry_lifecycle_conflicts_total{operation="check_in"} 1',
        ),
    ],
)
async def test_application_errors_map_only_to_bounded_event_labels(
    route: str,
    status_code: int,
    code: str,
    expected_sample: str,
) -> None:
    class Route:
        path = route

    app = FastAPI()
    app.state.metrics_registry = MetricsRegistry()
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/private-value",
            "headers": [],
            "route": Route(),
            "app": app,
        }
    )
    error = ApplicationError(status_code=status_code, code=code, message="safe")

    await application_error_handler(request, error)

    output = app.state.metrics_registry.render()
    assert expected_sample in output
    assert "private-value" not in output
