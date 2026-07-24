"""Live PostgreSQL tests for the initial Alembic migration."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import Engine, inspect

AlembicRunner = Callable[[str, str | None], None]


def test_empty_database_upgrade_downgrade_and_reupgrade(
    database_engine: Engine,
    run_migration: AlembicRunner,
) -> None:
    run_migration("downgrade", "base")
    with database_engine.connect() as connection:
        assert inspect(connection).get_table_names() == ["alembic_version"]

    run_migration("upgrade", "head")
    with database_engine.connect() as connection:
        assert set(inspect(connection).get_table_names()) == {
            "alembic_version",
            "users",
            "sessions",
            "impulse_purchase_entries",
            "opportunity_cost_examples",
        }


def test_migration_head_matches_model_metadata(
    run_migration: AlembicRunner,
) -> None:
    # The autouse fixture has already upgraded the dedicated database to head.
    # Alembic raises CommandError if any model-to-schema upgrade operation exists.
    run_migration("check", None)
