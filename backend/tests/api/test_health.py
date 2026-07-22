"""Application startup and health API tests."""

from uuid import UUID

import pytest
from app.core.config import Settings
from app.main import create_app
from httpx2 import ASGITransport, AsyncClient


def make_test_settings() -> Settings:
    return Settings(
        app_env="test",
        database_url=(
            "postgresql+psycopg://penny_saved_test:test-only@localhost:5432/penny_saved_test"
        ),
        frontend_origin="http://frontend.test",
    )


@pytest.mark.asyncio
async def test_application_starts_and_health_contract_is_explicit() -> None:
    app = create_app(make_test_settings())

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/api/health")

        assert app.state.engine is not None
        assert app.state.session_factory is not None

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    UUID(response.headers["X-Request-ID"])


@pytest.mark.asyncio
async def test_cors_allows_only_the_configured_credentialed_origin() -> None:
    app = create_app(make_test_settings())

    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        response = await client.options(
            "/api/health",
            headers={
                "Origin": "http://frontend.test",
                "Access-Control-Request-Method": "GET",
            },
        )
        rejected = await client.options(
            "/api/health",
            headers={
                "Origin": "http://untrusted.test",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://frontend.test"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers


@pytest.mark.asyncio
async def test_request_logs_do_not_include_cookie_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = create_app(make_test_settings())
    secret_cookie = "raw-secret-session-token"

    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        await client.get("/api/health", headers={"Cookie": f"session={secret_cookie}"})

    captured = capsys.readouterr()
    assert secret_cookie not in captured.out
    assert secret_cookie not in captured.err
