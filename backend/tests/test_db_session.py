"""Tests for async database resource and request-session lifecycles."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.config import AppEnvironment, Settings
from app.db.session import (
    ENGINE_STATE_KEY,
    LIFECYCLE_STATE_KEY,
    SESSION_FACTORY_STATE_KEY,
    ApplicationLifecycleState,
    create_database_lifespan,
    create_operational_lifespan,
    get_db_session,
)
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from starlette.requests import Request

DATABASE_URL = "postgresql+psycopg://app:secret@localhost:5432/penny_saved"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_url=DATABASE_URL,
    )


@pytest.fixture
def engine() -> MagicMock:
    return MagicMock(spec=AsyncEngine)


@pytest.fixture
def session() -> MagicMock:
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return mock_session


@pytest.fixture
def request_for_app() -> CallableRequest:
    return CallableRequest()


class CallableRequest:
    """Build minimal Starlette requests for dependency tests."""

    def __call__(self, app: FastAPI) -> Request:
        return Request({"type": "http", "app": app})


@pytest.mark.asyncio
async def test_lifespan_builds_one_engine_and_factory_on_application_state(
    settings: Settings,
    engine: MagicMock,
) -> None:
    app = FastAPI()
    session_factory = MagicMock()
    engine_builder = MagicMock(return_value=engine)
    session_factory_builder = MagicMock(return_value=session_factory)
    lifespan = create_database_lifespan(
        settings,
        engine_builder=engine_builder,
        session_factory_builder=session_factory_builder,
    )

    async with lifespan(app):
        assert getattr(app.state, ENGINE_STATE_KEY) is engine
        assert getattr(app.state, SESSION_FACTORY_STATE_KEY) is session_factory
        engine_builder.assert_called_once_with(DATABASE_URL)
        session_factory_builder.assert_called_once_with(engine)

    engine.dispose.assert_awaited_once_with()
    assert not hasattr(app.state, ENGINE_STATE_KEY)
    assert not hasattr(app.state, SESSION_FACTORY_STATE_KEY)


@pytest.mark.asyncio
async def test_lifespan_disposes_engine_when_factory_creation_fails(
    settings: Settings,
    engine: MagicMock,
) -> None:
    app = FastAPI()
    lifespan = create_database_lifespan(
        settings,
        engine_builder=MagicMock(return_value=engine),
        session_factory_builder=MagicMock(side_effect=RuntimeError("factory failed")),
    )

    with pytest.raises(RuntimeError, match="factory failed"):
        async with lifespan(app):
            pytest.fail("Lifespan should not start")

    engine.dispose.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_operational_lifespan_becomes_unready_before_resource_disposal(
    settings: Settings,
    engine: MagicMock,
) -> None:
    app = FastAPI()
    lifecycle_states_at_disposal: list[ApplicationLifecycleState] = []

    async def dispose() -> None:
        lifecycle_states_at_disposal.append(app.state.lifecycle_state)

    engine.dispose.side_effect = dispose
    resources = create_database_lifespan(
        settings,
        engine_builder=MagicMock(return_value=engine),
        session_factory_builder=MagicMock(return_value=MagicMock()),
    )
    lifespan = create_operational_lifespan(resources)

    async with lifespan(app):
        assert getattr(app.state, LIFECYCLE_STATE_KEY) is ApplicationLifecycleState.READY

    assert lifecycle_states_at_disposal == [ApplicationLifecycleState.STOPPING]
    assert app.state.metrics_registry.render().endswith("application_readiness 0\n")


@pytest.mark.asyncio
async def test_database_disposal_obeys_configured_shutdown_timeout(
    settings: Settings,
    engine: MagicMock,
) -> None:
    async def slow_dispose() -> None:
        await asyncio.sleep(0.02)

    timeout_settings = settings.model_copy(update={"graceful_shutdown_timeout_seconds": 0.001})
    engine.dispose.side_effect = slow_dispose
    lifespan = create_database_lifespan(
        timeout_settings,
        engine_builder=MagicMock(return_value=engine),
        session_factory_builder=MagicMock(return_value=MagicMock()),
    )

    with pytest.raises(TimeoutError):
        async with lifespan(FastAPI()):
            pass


@pytest.mark.asyncio
async def test_request_dependency_yields_and_closes_isolated_session(
    session: MagicMock,
    request_for_app: CallableRequest,
) -> None:
    app = FastAPI()
    session.in_transaction.return_value = False
    session_factory = MagicMock(return_value=session)
    setattr(app.state, SESSION_FACTORY_STATE_KEY, session_factory)
    dependency = get_db_session(request_for_app(app))

    yielded_session = await anext(dependency)
    await dependency.aclose()

    assert yielded_session is session
    session_factory.assert_called_once_with()
    session.rollback.assert_not_awaited()
    session.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_request_dependency_rolls_back_unfinished_transaction(
    session: MagicMock,
    request_for_app: CallableRequest,
) -> None:
    app = FastAPI()
    session.in_transaction.return_value = True
    setattr(app.state, SESSION_FACTORY_STATE_KEY, MagicMock(return_value=session))
    dependency = get_db_session(request_for_app(app))

    await anext(dependency)
    await dependency.aclose()

    session.rollback.assert_awaited_once_with()
    session.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_request_dependency_rolls_back_when_request_work_fails(
    session: MagicMock,
    request_for_app: CallableRequest,
) -> None:
    app = FastAPI()
    session.in_transaction.return_value = True
    setattr(app.state, SESSION_FACTORY_STATE_KEY, MagicMock(return_value=session))
    dependency = get_db_session(request_for_app(app))

    await anext(dependency)
    with pytest.raises(RuntimeError, match="request failed"):
        await dependency.athrow(RuntimeError("request failed"))

    session.rollback.assert_awaited_once_with()
    session.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_request_dependency_requires_active_application_lifespan(
    request_for_app: CallableRequest,
) -> None:
    dependency = get_db_session(request_for_app(FastAPI()))

    with pytest.raises(RuntimeError, match="outside app lifespan"):
        await anext(dependency)
