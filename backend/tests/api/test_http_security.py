"""Tests for public HTTP request-boundary middleware."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from app.api.dependencies import enforce_trusted_origin
from app.api.errors import ApplicationError
from app.core.config import AppEnvironment, Settings
from app.core.logging import REQUEST_ID_HEADER
from app.main import create_app
from fastapi import Depends, FastAPI, Request

DATABASE_URL = "postgresql+psycopg://app:secret@localhost:5432/penny_saved"
PRODUCTION_SECRET = "production-rate-limit-secret-at-least-32-bytes"
SESSION_TOKEN = "a" * 43


@asynccontextmanager
async def no_database_lifespan(app: FastAPI) -> AsyncIterator[None]:
    del app
    yield


def build_test_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "app_env": AppEnvironment.TEST,
        "database_url": DATABASE_URL,
        "frontend_origin": "http://localhost:5173",
        "trusted_hosts": ("test", "api.example.com"),
    }
    values.update(overrides)
    return Settings(**values)


def production_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.PRODUCTION,
        database_url=DATABASE_URL,
        frontend_origin="https://app.example.com",
        session_cookie_secure=True,
        trusted_hosts=("app.example.com",),
        trusted_proxy_networks=("10.0.0.0/8",),
        rate_limit_key_secret=PRODUCTION_SECRET,
    )


def security_app(settings: Settings) -> FastAPI:
    app = create_app(settings, lifespan=no_database_lifespan)

    @app.get("/api/client")
    async def read_client(request: Request) -> dict[str, str | None]:
        return {
            "host": request.client.host if request.client else None,
            "scheme": request.url.scheme,
        }

    @app.post("/api/echo")
    async def echo(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    @app.post("/api/mutation", dependencies=[Depends(enforce_trusted_origin)])
    async def mutate() -> dict[str, bool]:
        return {"updated": True}

    return app


def assert_security_headers(response: httpx.Response) -> None:
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["permissions-policy"] == "camera=(), geolocation=(), microphone=()"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


@pytest.mark.asyncio
async def test_trusted_host_accepts_expected_host_and_rejects_forgery() -> None:
    app = security_app(build_test_settings())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        accepted = await client.get("/api/health")
        rejected = await client.get("/api/health", headers={"Host": "attacker.example"})

    assert accepted.status_code == 200
    assert rejected.status_code == 400
    assert "attacker.example" not in rejected.text
    assert REQUEST_ID_HEADER in rejected.headers
    assert_security_headers(rejected)


@pytest.mark.asyncio
async def test_untrusted_peer_cannot_spoof_forwarded_client_or_scheme() -> None:
    app = security_app(build_test_settings(trusted_proxy_networks=("10.0.0.0/8",)))
    transport = httpx.ASGITransport(app=app, client=("203.0.113.9", 1234))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/client",
            headers={"X-Forwarded-For": "127.0.0.1", "X-Forwarded-Proto": "https"},
        )

    assert response.json() == {"host": "203.0.113.9", "scheme": "http"}


@pytest.mark.asyncio
async def test_trusted_proxy_resolves_first_untrusted_hop_and_https() -> None:
    app = security_app(build_test_settings(trusted_proxy_networks=("10.0.0.0/8",)))
    transport = httpx.ASGITransport(app=app, client=("10.0.0.2", 1234))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/client",
            headers={
                "X-Forwarded-For": "198.51.100.7, 10.0.0.3",
                "X-Forwarded-Proto": "https",
            },
        )
        malformed = await client.get(
            "/api/client",
            headers={"X-Forwarded-For": "not-an-ip"},
        )

    assert response.json() == {"host": "198.51.100.7", "scheme": "https"}
    assert malformed.status_code == 400
    assert malformed.json()["error"]["code"] == "invalid_forwarded_headers"


@pytest.mark.asyncio
async def test_declared_and_streamed_oversized_bodies_receive_safe_413() -> None:
    app = security_app(build_test_settings(max_request_body_bytes=1024))
    transport = httpx.ASGITransport(app=app)

    async def chunks() -> AsyncIterator[bytes]:
        yield b"a" * 700
        yield b"b" * 400

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        exact = await client.post("/api/echo", content=b"a" * 1024)
        declared = await client.post("/api/echo", content=b"a" * 1025)
        streamed = await client.post("/api/echo", content=chunks())

    assert exact.status_code == 200
    for rejected in (declared, streamed):
        assert rejected.status_code == 413
        assert rejected.json()["error"]["code"] == "payload_too_large"
        assert REQUEST_ID_HEADER in rejected.headers
        assert_security_headers(rejected)


@pytest.mark.asyncio
async def test_production_cookie_mutation_requires_exact_origin() -> None:
    configuration = production_settings()
    app = FastAPI()
    app.state.settings = configuration

    def mutation_request(origin: str | None) -> Request:
        headers = [(b"cookie", f"{configuration.session_cookie_name}={SESSION_TOKEN}".encode())]
        if origin is not None:
            headers.append((b"origin", origin.encode()))
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/mutation",
                "headers": headers,
                "app": app,
            }
        )

    with pytest.raises(ApplicationError) as missing:
        enforce_trusted_origin(mutation_request(None))
    with pytest.raises(ApplicationError) as wrong:
        enforce_trusted_origin(mutation_request("https://attacker.example"))
    enforce_trusted_origin(mutation_request("https://app.example.com"))

    assert missing.value.status_code == wrong.value.status_code == 403


@pytest.mark.asyncio
async def test_security_headers_cover_success_not_found_and_production_https() -> None:
    app = security_app(production_settings())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://app.example.com",
    ) as client:
        success = await client.get("/api/health")
        missing = await client.get("/api/unknown")

    for response in (success, missing):
        assert_security_headers(response)
        assert response.headers["strict-transport-security"] == (
            "max-age=31536000; includeSubDomains"
        )
