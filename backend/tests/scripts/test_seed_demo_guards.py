"""Safety, migration, clock, and transaction tests for demo seeding."""

from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from typing import cast

import pytest
from app.core.config import AppEnvironment, Settings
from app.core.time import FixedClock
from app.scripts.seed_demo import (
    SeedResult,
    SeedSafetyError,
    compare_migration_heads,
    run_seed,
    validate_seed_target,
)
from sqlalchemy import Connection, Engine


class _TransactionSpy:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> Connection:
        return cast(Connection, object())

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.rolled_back = exception_type is not None
        self.committed = exception_type is None


class _EngineSpy:
    def __init__(self) -> None:
        self.transaction = _TransactionSpy()
        self.disposed = False

    def begin(self) -> _TransactionSpy:
        return self.transaction

    def dispose(self) -> None:
        self.disposed = True


def _settings(
    *,
    app_env: AppEnvironment = AppEnvironment.DEVELOPMENT,
    database_url: str = "postgresql+psycopg://seed:seed@localhost:5432/penny_saved",
) -> Settings:
    frontend_origin = {
        AppEnvironment.TEST: None,
        AppEnvironment.DEVELOPMENT: "http://localhost:5173",
        AppEnvironment.PRODUCTION: "https://stopimpulsebuying.us",
    }[app_env]
    return Settings(
        app_env=app_env,
        database_url=database_url,
        frontend_origin=frontend_origin,
        session_cookie_secure=app_env == AppEnvironment.PRODUCTION,
        trusted_hosts=("stopimpulsebuying.us",)
        if app_env == AppEnvironment.PRODUCTION
        else ("localhost", "127.0.0.1"),
    )


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
def test_development_seed_accepts_only_loopback_postgresql(host: str) -> None:
    settings = _settings(database_url=f"postgresql+psycopg://seed:seed@{host}:5432/penny_saved")

    assert validate_seed_target(settings).database == "penny_saved"


def test_test_seed_requires_explicit_test_database() -> None:
    settings = _settings(
        app_env=AppEnvironment.TEST,
        database_url=("postgresql+psycopg://seed:seed@localhost:5432/penny_saved_test"),
    )

    assert validate_seed_target(settings).database == "penny_saved_test"


def test_production_is_rejected_before_engine_creation() -> None:
    settings = _settings(
        app_env=AppEnvironment.PRODUCTION,
        database_url="postgresql+psycopg://seed:seed@localhost:5432/penny_saved",
    )
    engine_created = False

    def engine_factory(_database_url: str):  # type: ignore[no-untyped-def]
        nonlocal engine_created
        engine_created = True
        raise AssertionError("Engine must not be created")

    with pytest.raises(SeedSafetyError, match="production"):
        run_seed(settings, engine_factory=engine_factory)

    assert not engine_created


@pytest.mark.parametrize(
    ("app_env", "database_url", "message"),
    [
        (
            AppEnvironment.DEVELOPMENT,
            "postgresql+psycopg://seed:seed@database.internal:5432/penny_saved",
            "loopback",
        ),
        (
            AppEnvironment.TEST,
            "postgresql+psycopg://seed:seed@localhost:5432/penny_saved",
            "_test",
        ),
    ],
)
def test_unsafe_seed_targets_are_rejected(
    app_env: AppEnvironment,
    database_url: str,
    message: str,
) -> None:
    with pytest.raises(SeedSafetyError, match=message):
        validate_seed_target(
            _settings(app_env=app_env, database_url=database_url),
        )


def test_migration_heads_must_match_exactly() -> None:
    compare_migration_heads({"0001"}, {"0001"})

    with pytest.raises(SeedSafetyError, match="database: base; code: 0001"):
        compare_migration_heads(set(), {"0001"})
    with pytest.raises(SeedSafetyError, match="database: 0002; code: 0001"):
        compare_migration_heads({"0002"}, {"0001"})


def test_run_seed_uses_injected_clock_inside_one_transaction() -> None:
    engine = _EngineSpy()
    fixed_time = datetime(2026, 7, 24, 15, 0, tzinfo=UTC)

    def seed_operation(_connection: Connection, clock: FixedClock) -> SeedResult:
        return SeedResult(seeded_at=clock.now())

    result = run_seed(
        _settings(),
        clock=FixedClock(fixed_time),
        engine_factory=lambda _database_url: cast(Engine, engine),
        head_verifier=lambda _connection: None,
        seed_operation=seed_operation,
    )

    assert result.seeded_at == fixed_time
    assert engine.transaction.committed
    assert not engine.transaction.rolled_back
    assert engine.disposed


def test_run_seed_rolls_back_when_operation_fails() -> None:
    engine = _EngineSpy()

    def failing_seed(_connection: Connection, _clock: FixedClock) -> SeedResult:
        raise RuntimeError("injected seed failure")

    with pytest.raises(RuntimeError, match="injected seed failure"):
        run_seed(
            _settings(),
            clock=FixedClock(datetime(2026, 7, 24, 15, 0, tzinfo=UTC)),
            engine_factory=lambda _database_url: cast(Engine, engine),
            head_verifier=lambda _connection: None,
            seed_operation=failing_seed,
        )

    assert not engine.transaction.committed
    assert engine.transaction.rolled_back
    assert engine.disposed
