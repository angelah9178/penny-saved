"""FastAPI application factory and lifecycle."""

import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import create_engine, create_session_factory

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an independently configurable application instance."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level, resolved_settings.app_env)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(resolved_settings)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        logger.info("application_started", extra={"environment": resolved_settings.app_env})
        try:
            yield
        finally:
            await engine.dispose()
            logger.info("application_stopped", extra={"environment": resolved_settings.app_env})

    app = FastAPI(
        title="A Penny Saved API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[resolved_settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = str(uuid4())
        request.state.request_id = request_id
        started_at = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        finally:
            route = request.scope.get("route")
            route_path = getattr(route, "path", request.url.path)
            logger.info(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "route": route_path,
                    "status": status_code,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                },
            )
        response.headers["X-Request-ID"] = request_id
        return response

    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
