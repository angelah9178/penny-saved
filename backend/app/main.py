"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.errors import register_error_handlers
from app.api.router import api_router
from app.core.config import AppEnvironment, Settings, get_settings
from app.core.http_security import (
    RequestBodyLimitMiddleware,
    SecurityHeadersMiddleware,
    TrustedProxyMiddleware,
)
from app.core.logging import (
    REQUEST_ID_HEADER,
    RequestContextMiddleware,
    configure_logging,
)
from app.core.metrics import MetricsMiddleware, MetricsRegistry
from app.core.operations import METRICS_PATH
from app.db.session import ENGINE_STATE_KEY, ApplicationLifespan, create_database_lifespan

API_PREFIX = "/api"


def create_app(
    settings: Settings | None = None,
    *,
    lifespan: ApplicationLifespan | None = None,
) -> FastAPI:
    """Create one fully configured FastAPI application."""
    resolved_settings = settings or get_settings()
    resolved_lifespan = lifespan or create_database_lifespan(resolved_settings)
    expose_api_docs = resolved_settings.app_env != AppEnvironment.PRODUCTION
    configure_logging(
        resolved_settings.app_env,
        resolved_settings.log_level,
        log_format=resolved_settings.log_format,
    )

    app = FastAPI(
        title="A Penny Saved API",
        version="0.1.0",
        lifespan=resolved_lifespan,
        openapi_url="/openapi.json" if expose_api_docs else None,
        docs_url="/docs" if expose_api_docs else None,
        redoc_url="/redoc" if expose_api_docs else None,
    )
    app.state.settings = resolved_settings
    app.state.metrics_registry = MetricsRegistry()
    register_error_handlers(app)
    if resolved_settings.metrics_enabled:

        @app.get(METRICS_PATH, include_in_schema=False)
        async def get_metrics(request: Request) -> PlainTextResponse:
            engine = getattr(request.app.state, ENGINE_STATE_KEY, None)
            database_pool = getattr(engine, "pool", None)
            return PlainTextResponse(
                request.app.state.metrics_registry.render(database_pool=database_pool),
                media_type="text/plain; version=0.0.4",
            )

    if resolved_settings.frontend_origin is not None:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[resolved_settings.frontend_origin],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=[REQUEST_ID_HEADER],
        )

    allowed_hosts = list(resolved_settings.trusted_hosts)
    if resolved_settings.app_env is AppEnvironment.TEST:
        allowed_hosts.append("test")
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=allowed_hosts,
    )
    app.add_middleware(
        TrustedProxyMiddleware,
        trusted_networks=resolved_settings.trusted_proxy_networks,
    )
    app.add_middleware(
        RequestBodyLimitMiddleware,
        max_bytes=resolved_settings.max_request_body_bytes,
    )
    app.add_middleware(
        RequestContextMiddleware,
        environment=resolved_settings.app_env,
    )
    if resolved_settings.metrics_enabled:
        app.add_middleware(
            MetricsMiddleware,
            registry=app.state.metrics_registry,
        )
    app.add_middleware(
        SecurityHeadersMiddleware,
        environment=resolved_settings.app_env,
    )

    app.include_router(api_router, prefix=API_PREFIX)
    return app
