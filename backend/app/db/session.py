"""Async database engine, session factory, and request lifecycle."""

from __future__ import annotations

from collections.abc import (
    AsyncIterator,
    Callable,
)
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings

EngineBuilder = Callable[[str], AsyncEngine]
SessionFactory = async_sessionmaker[AsyncSession]
SessionFactoryBuilder = Callable[[AsyncEngine], SessionFactory]
ApplicationLifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]

ENGINE_STATE_KEY = "db_engine"
SESSION_FACTORY_STATE_KEY = "db_session_factory"


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
            await engine.dispose()

    return database_lifespan


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
