"""Async database engine, session factory, and request lifecycle."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import (
    AsyncIterator,
    Callable,
)
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from enum import StrEnum

from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.core.logging import LOGGER_NAME
from app.core.metrics import MetricsRegistry

EngineBuilder = Callable[[str], AsyncEngine]
SessionFactory = async_sessionmaker[AsyncSession]
SessionFactoryBuilder = Callable[[AsyncEngine], SessionFactory]
ApplicationLifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]

ENGINE_STATE_KEY = "db_engine"
SESSION_FACTORY_STATE_KEY = "db_session_factory"
LIFECYCLE_STATE_KEY = "lifecycle_state"
READINESS_STATE_KEY = "readiness_state"

logger = logging.getLogger(f"{LOGGER_NAME}.lifecycle")


class ApplicationLifecycleState(StrEnum):
    """Externally meaningful application process states."""

    STARTING = "starting"
    READY = "ready"
    STOPPING = "stopping"


class DependencyReadinessState(StrEnum):
    """Most recently observed required-dependency state."""

    UNKNOWN = "unknown"
    READY = "ready"
    UNAVAILABLE = "unavailable"


def build_engine(database_url: str) -> AsyncEngine:
    """Create the application's async SQLAlchemy engine."""
    return create_async_engine(database_url, pool_pre_ping=True)


def build_session_factory(engine: AsyncEngine) -> SessionFactory:
    """Create request-scoped sessions bound to the application engine."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        autoflush=False,
        expire_on_commit=False,
    )


def create_database_lifespan(
    settings: Settings,
    *,
    engine_builder: EngineBuilder = build_engine,
    session_factory_builder: SessionFactoryBuilder = build_session_factory,
) -> ApplicationLifespan:
    """Create a FastAPI lifespan that owns database resources."""

    @asynccontextmanager
    async def database_lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = engine_builder(settings.database_url)
        try:
            session_factory = session_factory_builder(engine)
            setattr(app.state, ENGINE_STATE_KEY, engine)
            setattr(app.state, SESSION_FACTORY_STATE_KEY, session_factory)
            yield
        finally:
            if hasattr(app.state, SESSION_FACTORY_STATE_KEY):
                delattr(app.state, SESSION_FACTORY_STATE_KEY)
            if hasattr(app.state, ENGINE_STATE_KEY):
                delattr(app.state, ENGINE_STATE_KEY)
            try:
                async with asyncio.timeout(settings.graceful_shutdown_timeout_seconds):
                    await engine.dispose()
            except TimeoutError:
                logger.error("application.database_disposal_timeout")
                raise

    return database_lifespan


def create_operational_lifespan(
    resource_lifespan: ApplicationLifespan,
) -> ApplicationLifespan:
    """Wrap resources with explicit startup, readiness, and shutdown transitions."""

    @asynccontextmanager
    async def operational_lifespan(app: FastAPI) -> AsyncIterator[None]:
        _transition_lifecycle(app, ApplicationLifecycleState.STARTING)
        setattr(app.state, READINESS_STATE_KEY, DependencyReadinessState.UNKNOWN)
        _metrics_registry(app).set_readiness(False)
        try:
            async with resource_lifespan(app):
                _transition_lifecycle(app, ApplicationLifecycleState.READY)
                try:
                    yield
                finally:
                    _transition_lifecycle(app, ApplicationLifecycleState.STOPPING)
                    _metrics_registry(app).set_readiness(False)
        except Exception:
            if (
                getattr(app.state, LIFECYCLE_STATE_KEY, None)
                is not ApplicationLifecycleState.STOPPING
            ):
                logger.exception("application.startup_failed")
            raise

    return operational_lifespan


def set_dependency_readiness(app: FastAPI, state: DependencyReadinessState) -> None:
    """Record and log only dependency-readiness transitions."""
    previous = getattr(app.state, READINESS_STATE_KEY, DependencyReadinessState.UNKNOWN)
    if previous is state:
        return
    setattr(app.state, READINESS_STATE_KEY, state)
    _metrics_registry(app).set_readiness(state is DependencyReadinessState.READY)
    logger.log(
        logging.INFO if state is DependencyReadinessState.READY else logging.WARNING,
        "application.readiness_transition",
        extra={"context": {"from": previous.value, "to": state.value}},
    )


def _transition_lifecycle(app: FastAPI, state: ApplicationLifecycleState) -> None:
    previous = getattr(app.state, LIFECYCLE_STATE_KEY, None)
    if previous is state:
        return
    setattr(app.state, LIFECYCLE_STATE_KEY, state)
    logger.info(
        "application.lifecycle_transition",
        extra={
            "context": {
                "from": previous.value if previous is not None else "uninitialized",
                "to": state.value,
            }
        },
    )


def _metrics_registry(app: FastAPI) -> MetricsRegistry:
    registry: MetricsRegistry | None = getattr(app.state, "metrics_registry", None)
    if registry is None:
        registry = MetricsRegistry()
        app.state.metrics_registry = registry
    return registry


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield one isolated database session and clean up unfinished work."""
    session_factory: SessionFactory | None = getattr(
        request.app.state,
        SESSION_FACTORY_STATE_KEY,
        None,
    )
    if session_factory is None:
        raise RuntimeError("Database session factory is unavailable outside app lifespan")

    async with session_factory() as session:
        try:
            yield session
        finally:
            if session.in_transaction():
                await session.rollback()
