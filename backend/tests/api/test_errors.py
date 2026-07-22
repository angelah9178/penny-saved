"""Standard error-envelope tests."""

import pytest
from app.main import create_app
from fastapi import Body
from httpx2 import ASGITransport, AsyncClient

from tests.api.test_health import make_test_settings


@pytest.mark.asyncio
async def test_unknown_route_uses_safe_standard_envelope() -> None:
    app = create_app(make_test_settings())

    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        response = await client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "The requested resource was not found.",
        }
    }


@pytest.mark.asyncio
async def test_validation_and_malformed_json_use_standard_envelopes() -> None:
    app = create_app(make_test_settings())

    @app.post("/api/test-body")
    async def accept_body(name: str = Body(embed=True, min_length=1)) -> dict[str, str]:
        return {"name": name}

    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        invalid = await client.post("/api/test-body", json={"name": ""})
        malformed = await client.post(
            "/api/test-body",
            content="{",
            headers={"Content-Type": "application/json"},
        )

    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"
    assert malformed.status_code == 400
    assert malformed.json() == {
        "error": {
            "code": "malformed_json",
            "message": "The request body is not valid JSON.",
        }
    }


@pytest.mark.asyncio
async def test_unexpected_error_is_safe_and_request_correlated() -> None:
    app = create_app(make_test_settings())

    @app.get("/api/test-error")
    async def raise_unexpected_error() -> None:
        raise RuntimeError("sensitive implementation detail")

    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://testserver",
        ) as client,
    ):
        response = await client.get("/api/test-error")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "An unexpected error occurred.",
        }
    }
    assert "sensitive" not in response.text
    assert "X-Request-ID" in response.headers
