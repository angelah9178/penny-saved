"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import AppEnvironment, Settings, get_settings
from app.db.session import ApplicationLifespan, create_database_lifespan

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

    app = FastAPI(
        title="A Penny Saved API",
        version="0.1.0",
        lifespan=resolved_lifespan,
        openapi_url="/openapi.json" if expose_api_docs else None,
        docs_url="/docs" if expose_api_docs else None,
        redoc_url="/redoc" if expose_api_docs else None,
    )
    app.state.settings = resolved_settings

    if resolved_settings.frontend_origin is not None:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[resolved_settings.frontend_origin],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(api_router, prefix=API_PREFIX)
    return app
