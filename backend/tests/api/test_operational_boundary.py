"""Assembled verification of the complete production operational boundary."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from io import StringIO
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from app.api.errors import ApplicationError
from app.core.config import AppEnvironment, LogFormat, Settings
from app.core.logging import REQUEST_ID_HEADER, configure_logging
from app.db.session import LIFECYCLE_STATE_KEY, ApplicationLifecycleState, get_db_session
from app.main import create_app
from fastapi import FastAPI, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

DATABASE_URL = "postgresql+psycopg://app:database-password-secret@localhost/penny_saved"
PRIVATE_VALUES = (
    "password-secret",
    "cookie-secret",
    "authorization-secret",
    "database-password-secret",
    "private@example.com",
    "198.51.100.42",
    "private-entry-id",
    "private-body-value",
    "private-query-value",
    "unexpected-token-secret",
)


@asynccontextmanager
async def no_database_lifespan(app: FastAPI) -> AsyncIterator[None]:
    del app
    yield


@asynccontextmanager
async def api_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://stopimpulsebuying.us",
    ) as client:
        yield client


def production_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.PRODUCTION,
        database_url=DATABASE_URL,
        frontend_origin="https://stopimpulsebuying.us",
        session_cookie_secure=True,
        log_format=LogFormat.JSON,
        metrics_enabled=True,
        trusted_hosts=("stopimpulsebuying.us",),
        trusted_proxy_networks=("127.0.0.1/32",),
        max_request_body_bytes=1_024,
        rate_limit_key_secret="production-rate-limit-secret-at-least-32-bytes",
    )


@pytest.mark.asyncio
async def test_complete_operational_boundary_is_correlated_bounded_and_private() -> None:
    settings = production_settings()
    app = create_app(settings, lifespan=no_database_lifespan)
    setattr(app.state, LIFECYCLE_STATE_KEY, ApplicationLifecycleState.READY)
    database_session = AsyncMock(spec=AsyncSession)
    database_session.execute.side_effect = [
        SQLAlchemyError("database-password-secret"),
        None,
    ]

    async def override_database_session() -> AsyncIterator[AsyncSession]:
        yield database_session

    app.dependency_overrides[get_db_session] = override_database_session

    @app.get("/verify/success/{entry_id}")
    async def successful_request(entry_id: str) -> dict[str, bool]:
        del entry_id
        await asyncio.sleep(0)
        return {"ok": True}

    @app.get("/verify/authenticated")
    async def authenticated_request(request: Request) -> dict[str, bool]:
        request.state.user_id = "cf50ea71-196a-4c23-bc66-48fe26bb2d14"
        return {"ok": True}

    @app.get("/verify/safe-error")
    async def safe_error() -> None:
        raise ApplicationError(
            status_code=status.HTTP_409_CONFLICT,
            code="verification_conflict",
            message="The verification request conflicts with current state.",
        )

    @app.post("/verify/unexpected/{entry_id}")
    async def unexpected_error(entry_id: str, request: Request) -> None:
        del entry_id
        await request.body()
        raise RuntimeError(
            "password=password-secret Cookie=cookie-secret "
            "authorization=authorization-secret token=unexpected-token-secret"
        )

    stream = StringIO()
    configure_logging(
        settings.app_env,
        settings.log_level,
        log_format=settings.log_format,
        stream=stream,
    )

    async with api_client(app) as client:
        concurrent = await asyncio.gather(
            *(
                client.get(
                    f"/verify/success/private-entry-id-{index}?value=private-query-value",
                    headers={
                        "Cookie": "session=cookie-secret",
                        "X-Forwarded-For": "198.51.100.42",
                    },
                )
                for index in range(8)
            )
        )
        authenticated = await client.get("/verify/authenticated")
        expected_error = await client.get("/verify/safe-error")
        unexpected_error_response = await client.post(
            "/verify/unexpected/private-entry-id",
            headers={"Authorization": "Bearer authorization-secret"},
            json={"value": "private-body-value", "email": "private@example.com"},
        )
        unmatched = await client.get("/verify/missing/private-entry-id")
        hostile_host = await client.get(
            "/api/health",
            headers={"Host": "attacker.example"},
        )
        database_lost = await client.get("/api/ready")
        liveness_during_loss = await client.get("/api/health")
        database_recovered = await client.get("/api/ready")
        metrics = await client.get("/internal/metrics")

    responses = [
        *concurrent,
        authenticated,
        expected_error,
        unexpected_error_response,
        unmatched,
        hostile_host,
        database_lost,
        liveness_during_loss,
        database_recovered,
    ]
    assert all(response.status_code == 200 for response in concurrent)
    assert authenticated.status_code == 200
    assert expected_error.status_code == 409
    assert unexpected_error_response.status_code == 500
    assert unexpected_error_response.json() == {
        "error": {
            "code": "internal_error",
            "message": "An unexpected error occurred.",
        }
    }
    assert unmatched.status_code == 404
    assert hostile_host.status_code == 400
    assert database_lost.status_code == 503
    assert liveness_during_loss.status_code == 200
    assert database_recovered.status_code == 200

    logs = [json.loads(line) for line in stream.getvalue().splitlines()]
    logs_by_request_id: dict[str, list[dict[str, object]]] = {}
    for log in logs:
        request_id = log.get("request_id")
        if isinstance(request_id, str):
            logs_by_request_id.setdefault(request_id, []).append(log)
    for response in responses:
        request_id = response.headers[REQUEST_ID_HEADER]
        assert str(UUID(request_id)) == request_id
        assert request_id in logs_by_request_id

    unexpected_request_id = unexpected_error_response.headers[REQUEST_ID_HEADER]
    unexpected_logs = logs_by_request_id[unexpected_request_id]
    exception_log = next(
        log for log in unexpected_logs if log["event"] == "request.unhandled_exception"
    )
    assert exception_log["exception_type"] == "RuntimeError"
    assert exception_log["stack_trace"]
    completion_log = next(log for log in unexpected_logs if log["event"] == "request.completed")
    assert completion_log["route"] == "/verify/unexpected/{entry_id}"
    assert completion_log["status"] == 500
    assert "stack_trace" not in unexpected_error_response.text

    authenticated_id = authenticated.headers[REQUEST_ID_HEADER]
    authenticated_log = next(
        log for log in logs_by_request_id[authenticated_id] if log["event"] == "request.completed"
    )
    assert authenticated_log["user_id"] == "cf50ea71-196a-4c23-bc66-48fe26bb2d14"

    metrics_output = metrics.text
    assert (
        'http_server_requests_total{method="GET",'
        'route="/verify/success/{entry_id}",status_class="2xx"} 8' in metrics_output
    )
    assert (
        'http_server_request_duration_seconds_count{method="GET",'
        'route="/verify/success/{entry_id}"} 8' in metrics_output
    )
    assert (
        'http_server_errors_total{method="POST",'
        'route="/verify/unexpected/{entry_id}",status_class="5xx"} 1' in metrics_output
    )
    assert "application_readiness 1" in metrics_output

    combined_evidence = stream.getvalue() + metrics_output
    for private_value in PRIVATE_VALUES:
        assert private_value not in combined_evidence
