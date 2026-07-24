"""PostgreSQL fixtures shared by demo-seed integration tests."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from app.models.user import User
from sqlalchemy import Connection, create_engine
from sqlalchemy.engine import make_url


@pytest.fixture
def seed_connection() -> Iterator[Connection]:
    """Use only the explicit disposable PostgreSQL test database."""
    raw_url = os.environ.get("TEST_DATABASE_URL")
    if not raw_url:
        pytest.fail("Demo seed tests require TEST_DATABASE_URL.")
    url = make_url(raw_url)
    if not url.database or not url.database.endswith("_test"):
        pytest.fail("TEST_DATABASE_URL database name must end with '_test'.")

    engine = create_engine(url)
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(User.__table__.delete())
        try:
            yield connection
        finally:
            transaction.rollback()
    engine.dispose()
