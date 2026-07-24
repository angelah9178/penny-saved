"""Safe fixtures for tests that mutate a dedicated PostgreSQL database."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from unittest.mock import patch

import pytest
from alembic import command
from alembic.config import Config
from app.core.config import clear_settings_cache, get_settings
from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.engine import URL, make_url

AlembicRunner = Callable[[str, str | None], None]


def _database_target(url: URL) -> tuple[str | None, int | None, str | None]:
    return url.host, url.port, url.database


def _require_test_database_url() -> URL:
    raw_url = os.environ.get("TEST_DATABASE_URL")
    if not raw_url:
        pytest.fail(
            "Integration tests require an explicit TEST_DATABASE_URL; "
            "the development DATABASE_URL is never reused."
        )

    test_url = make_url(raw_url)
    if test_url.drivername != "postgresql+psycopg":
        pytest.fail("TEST_DATABASE_URL must use the postgresql+psycopg driver.")
    if not test_url.database or not test_url.database.endswith("_test"):
        pytest.fail("TEST_DATABASE_URL database name must end with '_test'.")

    development_url = make_url(get_settings().database_url)
    if _database_target(test_url) == _database_target(development_url):
        pytest.fail("TEST_DATABASE_URL must not target the development database.")
    return test_url


@pytest.fixture(scope="session")
def test_database_url() -> URL:
    """Return a validated, explicit URL for a disposable PostgreSQL database."""
    return _require_test_database_url()


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    """Load the repository's Alembic configuration."""
    return Config("alembic.ini")


@pytest.fixture(scope="session")
def run_migration(
    test_database_url: URL,
    alembic_config: Config,
) -> AlembicRunner:
    """Run one Alembic command against only the validated test database."""

    def run(action: str, revision: str | None = None) -> None:
        migration_command = getattr(command, action)
        environment = {
            "APP_ENV": "test",
            "DATABASE_URL": test_database_url.render_as_string(hide_password=False),
        }
        clear_settings_cache()
        try:
            with patch.dict(os.environ, environment):
                if revision is None:
                    migration_command(alembic_config)
                else:
                    migration_command(alembic_config, revision)
        finally:
            clear_settings_cache()

    return run


@pytest.fixture(autouse=True)
def database_at_migration_head(run_migration: AlembicRunner) -> None:
    """Ensure every integration test begins with the current schema."""
    run_migration("upgrade", "head")


@pytest.fixture
def database_engine(test_database_url: URL) -> Iterator[Engine]:
    """Create a short-lived engine for the dedicated test database."""
    engine = create_engine(test_database_url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_connection(database_engine: Engine) -> Iterator[Connection]:
    """Rollback all data written by one schema test."""
    with database_engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()
