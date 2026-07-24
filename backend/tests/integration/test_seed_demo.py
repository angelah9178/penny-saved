"""End-to-end PostgreSQL tests for the complete demo seed."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from app.core.config import AppEnvironment, Settings
from app.core.security import hash_password
from app.core.time import FixedClock
from app.models.entry import EntryStatus, ImpulsePurchaseEntry
from app.models.opportunity_cost_example import OpportunityCostExample
from app.models.user import User
from app.scripts.seed_demo import (
    DEMO_ENTRIES,
    DEMO_OPPORTUNITY_COSTS,
    DEMO_USER_ID,
    run_seed,
    seed_demo,
)
from sqlalchemy import Connection, Engine, func, select
from sqlalchemy.engine import URL

NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)


@pytest.fixture
def empty_seed_database(database_engine: Engine) -> Iterator[Engine]:
    """Give an integration test a clean database and clean up afterward."""
    with database_engine.begin() as connection:
        connection.execute(User.__table__.delete())
    try:
        yield database_engine
    finally:
        with database_engine.begin() as connection:
            connection.execute(User.__table__.delete())


def _snapshot(connection: Connection, table) -> list[dict[str, object]]:  # type: ignore[no-untyped-def]
    return [dict(row) for row in connection.execute(select(table).order_by(table.c.id)).mappings()]


def test_complete_seed_is_idempotent_and_preserves_unrelated_data(
    empty_seed_database: Engine,
) -> None:
    other_user_id = UUID("70000000-0000-4000-8000-000000000001")
    manual_entry_id = UUID("70000000-0000-4000-8000-000000000002")
    manual_example_id = UUID("70000000-0000-4000-8000-000000000003")
    with empty_seed_database.begin() as connection:
        connection.execute(
            User.__table__.insert().values(
                id=other_user_id,
                email="unrelated@example.local",
                password_hash=hash_password("unrelated-password"),
                created_at=NOW,
                updated_at=NOW,
            )
        )
        connection.execute(
            ImpulsePurchaseEntry.__table__.insert().values(
                id=manual_entry_id,
                user_id=other_user_id,
                item_name="Unrelated manual entry",
                price_cents=1_234,
                reason_wanted="Must remain untouched.",
                status=EntryStatus.WAITING,
                comment=None,
                created_at=NOW,
                checked_in_at=None,
                updated_at=NOW,
            )
        )
        connection.execute(
            OpportunityCostExample.__table__.insert().values(
                id=manual_example_id,
                user_id=other_user_id,
                label="Unrelated example",
                unit_name="unrelated unit",
                dollar_value_cents=4_321,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        unrelated_before = {
            "user": _snapshot(connection, User.__table__),
            "entry": _snapshot(connection, ImpulsePurchaseEntry.__table__),
            "example": _snapshot(connection, OpportunityCostExample.__table__),
        }
        first_result = seed_demo(connection, FixedClock(NOW))
        first_demo = {
            "user": connection.execute(select(User.__table__).where(User.id == DEMO_USER_ID))
            .mappings()
            .one(),
            "entries": _snapshot(connection, ImpulsePurchaseEntry.__table__),
            "examples": _snapshot(connection, OpportunityCostExample.__table__),
        }
        second_result = seed_demo(connection, FixedClock(NOW))
        second_demo = {
            "user": connection.execute(select(User.__table__).where(User.id == DEMO_USER_ID))
            .mappings()
            .one(),
            "entries": _snapshot(connection, ImpulsePurchaseEntry.__table__),
            "examples": _snapshot(connection, OpportunityCostExample.__table__),
        }

        assert first_result == second_result
        assert first_demo == second_demo
        assert connection.scalar(select(func.count()).select_from(User)) == 2
        assert (
            connection.scalar(select(func.count()).select_from(ImpulsePurchaseEntry))
            == len(DEMO_ENTRIES) + 1
        )
        assert (
            connection.scalar(select(func.count()).select_from(OpportunityCostExample))
            == len(DEMO_OPPORTUNITY_COSTS) + 1
        )
        assert unrelated_before == {
            "user": [
                dict(
                    connection.execute(select(User.__table__).where(User.id == other_user_id))
                    .mappings()
                    .one()
                )
            ],
            "entry": [
                dict(
                    connection.execute(
                        select(ImpulsePurchaseEntry.__table__).where(
                            ImpulsePurchaseEntry.id == manual_entry_id
                        )
                    )
                    .mappings()
                    .one()
                )
            ],
            "example": [
                dict(
                    connection.execute(
                        select(OpportunityCostExample.__table__).where(
                            OpportunityCostExample.id == manual_example_id
                        )
                    )
                    .mappings()
                    .one()
                )
            ],
        }


def test_injected_mid_seed_failure_rolls_back_everything(
    empty_seed_database: Engine,
    test_database_url: URL,
) -> None:
    settings = Settings(
        app_env=AppEnvironment.TEST,
        database_url=test_database_url.render_as_string(hide_password=False),
    )

    def failing_seed(connection: Connection, clock: FixedClock):  # type: ignore[no-untyped-def]
        seed_demo(connection, clock)
        raise RuntimeError("injected failure after complete seed")

    with pytest.raises(RuntimeError, match="injected failure"):
        run_seed(
            settings,
            clock=FixedClock(NOW),
            seed_operation=failing_seed,
        )

    with empty_seed_database.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(User)) == 0
        assert connection.scalar(select(func.count()).select_from(ImpulsePurchaseEntry)) == 0
        assert connection.scalar(select(func.count()).select_from(OpportunityCostExample)) == 0
